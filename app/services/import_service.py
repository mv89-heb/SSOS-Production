from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Any

from flask import abort, current_app
from sqlalchemy import select

from app.extensions import db
from app.models.import_session import ImportSession, ImportSessionRow
from app.models.supplier import Supplier
from app.services.audit_service import AuditService


class ImportService:
    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id

    def _get(self, session_id: int):
        session = db.session.execute(select(ImportSession).where(ImportSession.id == session_id, ImportSession.tenant_id == self.tenant_id)).scalar_one_or_none()
        if session is None:
            abort(404, description="Import session not found")
        return session

    def list_sessions(self):
        return db.session.execute(select(ImportSession).where(ImportSession.tenant_id == self.tenant_id).order_by(ImportSession.created_at.desc()).limit(100)).scalars().all()

    def get_session(self, session_id: int):
        return self._get(session_id)

    def get_session_rows(self, session_id: int, limit: int = 100, offset: int = 0):
        self._get(session_id)
        return db.session.execute(select(ImportSessionRow).where(ImportSessionRow.import_session_id == session_id, ImportSessionRow.tenant_id == self.tenant_id).order_by(ImportSessionRow.row_number.asc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500))).scalars().all()

    def _supplier(self, supplier_id: int | None):
        if supplier_id is None:
            return None
        supplier = db.session.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == self.tenant_id)).scalar_one_or_none()
        if supplier is None:
            abort(404, description="Supplier not found")
        return supplier

    @staticmethod
    def _bounded_rows(rows, max_rows: int, max_columns: int):
        bounded = []
        for row in rows:
            values = list(row)
            if len(values) > max_columns:
                raise ValueError(f"Import contains more than {max_columns} columns")
            bounded.append(values)
            if len(bounded) > max_rows:
                raise ValueError(f"Import contains more than {max_rows} rows")
        return bounded

    def _parse_csv(self, storage_path: str):
        max_rows = int(current_app.config["MAX_IMPORT_ROWS"])
        max_columns = int(current_app.config["MAX_IMPORT_COLUMNS"])
        with open(storage_path, "r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            return self._bounded_rows(csv.reader(handle), max_rows, max_columns)

    def _parse_excel(self, storage_path: str, sheet_name: str | None):
        import pandas as pd
        max_rows = int(current_app.config["MAX_IMPORT_ROWS"])
        max_columns = int(current_app.config["MAX_IMPORT_COLUMNS"])
        sheets = pd.read_excel(storage_path, sheet_name=sheet_name or None, header=None)
        selected = list(sheets.items()) if isinstance(sheets, dict) else [(sheet_name or "Sheet1", sheets)]
        all_rows = []
        sheet_names = []
        for name, frame in selected:
            sheet_names.append(str(name))
            if frame.shape[1] > max_columns:
                raise ValueError(f"Import contains more than {max_columns} columns")
            all_rows.extend(frame.itertuples(index=False, name=None))
            if len(all_rows) > max_rows:
                raise ValueError(f"Import contains more than {max_rows} rows")
        return self._bounded_rows(all_rows, max_rows, max_columns), sheet_names

    def create_session_and_parse(self, *, filename: str, storage_path: str, supplier_id: int | None = None, sheet_name: str | None = None):
        self._supplier(supplier_id)
        session = ImportSession(tenant_id=self.tenant_id, uploaded_by=self.user_id, filename=filename, storage_path=storage_path, supplier_id=supplier_id, status="PROCESSING")
        db.session.add(session)
        db.session.flush()
        try:
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".csv":
                rows = self._parse_csv(storage_path)
                sheet_names = [filename]
            elif ext in {".xlsx", ".xls"}:
                rows, sheet_names = self._parse_excel(storage_path, sheet_name)
            else:
                raise ValueError("Unsupported import file type")
        except Exception as exc:
            session.status = "FAILED"
            session.error_message = f"Failed to parse {filename}: {exc}"
            AuditService.log_event(self.tenant_id, self.user_id, "import_failed", title="Import parsing failed", metadata={"import_session_id": session.id})
            # Keep the original upload available for the read-only Analysis phase.
            # Failed/empty staging sessions are still valid analysis inputs.
            return session

        row_entities = []
        for index, row in enumerate(rows, start=1):
            row_entities.append(ImportSessionRow(tenant_id=self.tenant_id, import_session_id=session.id, row_number=index, raw_data={str(i): value for i, value in enumerate(row)}))
        db.session.add_all(row_entities)
        session.status = "STAGED"
        session.error_message = None
        session.metadata_json = {"sheet_names": sheet_names, "row_count": len(rows)}
        AuditService.log_event(self.tenant_id, self.user_id, "import_staged", title="Import staged", metadata={"import_session_id": session.id, "row_count": len(rows)})
        return session
