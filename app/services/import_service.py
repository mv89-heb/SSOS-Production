import os
import csv

from app.repositories.import_session_repository import ImportSessionRepository
from app.repositories.import_row_repository import ImportRowRepository
from app.repositories.supplier_repository import SupplierRepository
from app.models.import_session import ImportSession, STATUS_UPLOADED, STATUS_FAILED
from app.services.audit_service import AuditService
from app.utils.header_detection import detect_header


class ImportParseError(Exception):
    """Raised when a file can't be parsed at all (bad format, corrupt,
    unsupported extension, or zero usable rows)."""


class ImportService:
    """
    Phase 3.1 — Import Staging Layer. Deliberately does exactly one thing:
    take an uploaded Excel/CSV file and store every row verbatim as JSON,
    completely unmodified, in its own ImportSession. Nothing here reads
    from or writes to products/suppliers/supplier_product_offers — this is
    staging only. Mapping (wide/tall format interpretation), validation,
    duplicate detection, and the eventual commit-to-production step are
    later phases, deliberately not implemented yet.
    """

    def __init__(self, tenant_id: int, user_id: int):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_repo = ImportSessionRepository(tenant_id)
        self.row_repo = ImportRowRepository(tenant_id)
        self.supplier_repo = SupplierRepository(tenant_id)

    def list_sessions(self, limit: int = 50):
        return self.session_repo.list_recent(limit=limit)

    def get_session(self, session_id: int) -> ImportSession:
        return self.session_repo.get_by_id_or_404(session_id)

    def get_session_rows(self, session_id: int, limit: int = 100, offset: int = 0):
        self.session_repo.get_by_id_or_404(session_id)  # tenant ownership check
        return self.row_repo.get_by_session(session_id, limit=limit, offset=offset)

    def create_session_and_parse(
        self, filename: str, storage_path: str, supplier_id: int = None, sheet_name: str = None
    ) -> ImportSession:
        """Creates the ImportSession, parses the file, and stores every row
        as an ImportRow. On any parse failure the session is marked FAILED
        with the reason recorded — it is never left half-written, and
        nothing is ever written outside import_sessions/import_rows."""
        if supplier_id is not None:
            self.supplier_repo.get_by_id_or_404(supplier_id)  # tenant ownership check

        session = self.session_repo.model(
            tenant_id=self.tenant_id,
            filename=filename,
            storage_path=storage_path,
            supplier_id=supplier_id,
            uploaded_by=self.user_id,
            status=STATUS_UPLOADED,
        )
        self.session_repo.add(session)  # flush -> session.id populated

        try:
            headers, data_rows, data_rows_values, resolved_sheet_name = self._parse_file(storage_path, sheet_name)
            if not data_rows:
                raise ImportParseError("No data rows found in file")
        except ImportParseError as exc:
            session.status = STATUS_FAILED
            session.error_message = str(exc)
            AuditService.log_event(
                self.tenant_id, self.user_id, "import.failed",
                f"Failed to parse {filename}: {exc}",
                {"import_session_id": session.id},
            )
            return session

        row_entities = [
            self.row_repo.model(
                tenant_id=self.tenant_id,
                import_session_id=session.id,
                row_number=i + 1,
                raw_data=row,
                raw_values=values,
            )
            for i, (row, values) in enumerate(zip(data_rows, data_rows_values))
        ]
        self.row_repo.bulk_add(row_entities)

        session.column_headers = headers
        session.row_count = len(data_rows)
        # Phase 3.2B needs to know which sheet was actually staged here, to
        # link the Mapping workspace to the matching ImportAnalysis row
        # (Analysis covers every sheet; staging only ever covers one).
        session.staged_sheet_name = resolved_sheet_name
        # Status intentionally stays UPLOADED: raw rows are now staged and
        # ready for the Mapping Engine step, which is a later phase.

        AuditService.log_event(
            self.tenant_id, self.user_id, "import.session_created",
            f"Uploaded {filename} ({len(data_rows)} rows)",
            {"import_session_id": session.id, "row_count": len(data_rows)},
        )
        return session

    # ------------------------------------------------------------------
    # Parsing — format-specific readers, all funneling into _rows_to_dicts
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_file(path: str, sheet_name: str = None):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xlsx":
            return ImportService._parse_xlsx(path, sheet_name)
        if ext == ".xls":
            return ImportService._parse_xls(path, sheet_name)
        if ext == ".csv":
            return ImportService._parse_csv(path)
        raise ImportParseError(f"Unsupported file extension: {ext}")

    @staticmethod
    def _parse_xlsx(path: str, sheet_name: str = None):
        try:
            import openpyxl
        except ImportError as exc:
            raise ImportParseError("openpyxl is required to read .xlsx files") from exc

        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except Exception as exc:
            raise ImportParseError(f"Could not open .xlsx file: {exc}") from exc

        sheet = sheet_name if sheet_name in wb.sheetnames else wb.sheetnames[0]
        ws = wb[sheet]
        headers, data_rows, data_rows_values = ImportService._rows_to_dicts(ws.iter_rows(values_only=True))
        return headers, data_rows, data_rows_values, sheet

    @staticmethod
    def _parse_xls(path: str, sheet_name: str = None):
        try:
            import xlrd
        except ImportError as exc:
            raise ImportParseError("xlrd is required to read legacy .xls files") from exc

        try:
            wb = xlrd.open_workbook(path)
        except Exception as exc:
            raise ImportParseError(f"Could not open .xls file: {exc}") from exc

        resolved_name = sheet_name if sheet_name in wb.sheet_names() else wb.sheet_names()[0]
        ws = wb.sheet_by_name(resolved_name)

        def _row_gen():
            for r in range(ws.nrows):
                yield tuple(ws.cell_value(r, c) for c in range(ws.ncols))

        headers, data_rows, data_rows_values = ImportService._rows_to_dicts(_row_gen())
        return headers, data_rows, data_rows_values, resolved_name

    @staticmethod
    def _parse_csv(path: str):
        try:
            # utf-8-sig transparently strips a BOM if Excel added one on export.
            with open(path, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
        except UnicodeDecodeError as exc:
            raise ImportParseError(f"Could not read CSV as UTF-8: {exc}") from exc
        except OSError as exc:
            raise ImportParseError(f"Could not open .csv file: {exc}") from exc

        headers, data_rows, data_rows_values = ImportService._rows_to_dicts(iter(rows))
        return headers, data_rows, data_rows_values, "CSV"

    @staticmethod
    def _rows_to_dicts(rows_iter):
        """Turns raw rows into (headers, [{header: value, ...}, ...], [[value, ...], ...]).

        Header detection now comes from app.utils.header_detection.detect_header
        — the SAME function ImportAnalysisService already used and had
        tested since Phase 3.2A — instead of this file's own "first
        non-empty row is the header" rule. That old rule is exactly why a
        two-tier header (a merged supplier-name row above a real column-
        label row — common in real supplier price lists) got its second
        header row staged as if it were a product: it only ever removed
        ONE row, no matter how many header tiers the file actually had.
        detect_header() correctly identifies the FULL header block
        (however many tiers), so this now removes all of it. For a file
        with a single header row — the common case — detect_header always
        returns tier_count=1, so nothing changes: same header row picked,
        same data start, byte-for-byte the same result as before.

        Column names come from the LAST header tier — the one closest to
        the data (e.g. "יחידה"/"מחיר"), not a sparse merged group-label row
        — matching what Analysis's own _build_header_labels already does,
        so a multi-tier file's Staging headers and Analysis headers now
        agree instead of diverging.

        Duplicate header names (very common in these real price lists —
        e.g. the same "לפני מע\"מ" label repeated once per supplier column)
        are disambiguated with a " (2)", " (3)"... suffix so no column's
        data is ever silently overwritten — losslessness matters more than
        clean naming at this stage; a human names things properly in the
        Mapping Engine step.

        Fully empty rows (after the header block) are skipped. Every cell
        value is coerced to a plain string (or "" for a missing/None cell)
        so raw_data is uniformly JSON-serializable regardless of source
        type (Excel can hand back int/float/datetime; CSV always hands
        back str).

        Returns BOTH a header->value dict per row (for human-readable
        display) AND a plain positional list per row (same values, same
        order as `headers`) — the list exists because dict key order isn't
        reliably preserved through JSON storage. Phase 3.2C's Validation
        aligns by column position via the list, never by matching header
        text between Staging and Analysis.
        """
        rows_list = list(rows_iter)

        if not any(row and any(cell not in (None, "") for cell in row) for row in rows_list):
            return [], [], []

        header_start_1based, tier_count, _reason = detect_header(rows_list)
        header_idx = header_start_1based - 1  # 0-based index of the header block's first row
        label_row_idx = header_idx + tier_count - 1  # last tier — closest to the data
        label_row = rows_list[label_row_idx] if label_row_idx < len(rows_list) else []

        headers = []
        seen = {}
        for i, cell in enumerate(label_row):
            name = str(cell).strip() if cell not in (None, "") else f"עמודה {i + 1}"
            if name in seen:
                seen[name] += 1
                name = f"{name} ({seen[name]})"
            else:
                seen[name] = 1
            headers.append(name)

        data_rows = []
        data_rows_values = []
        for row in rows_list[header_idx + tier_count:]:
            if not row or all(cell in (None, "") for cell in row):
                continue
            row_dict = {}
            row_values = []
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else None
                str_value = "" if value is None else str(value)
                row_dict[header] = str_value
                row_values.append(str_value)
            data_rows.append(row_dict)
            data_rows_values.append(row_values)

        return headers, data_rows, data_rows_values
