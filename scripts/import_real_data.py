#!/usr/bin/env python3
"""
One-time CLI import script.

Loads a real supplier price-list file directly into the database this
process is configured against — via the standard DATABASE_URL
environment variable, the SAME config.py the Flask app itself uses. No
special-casing, no new logic: this reuses the EXACT service layer the
HTTP API uses (ImportService -> ImportAnalysisService ->
ImportMappingService -> ImportValidationService -> ImportExecutionService)
in the same order the routes call them. It is the CLI equivalent of
walking through POST /api/imports/upload -> /analyze -> /mapping ->
/mapping/approve -> /validate -> /commit as an existing admin/manager.

USAGE — run this wherever DATABASE_URL points at your real database
(e.g. Render Shell, or locally with DATABASE_URL exported to your Neon
connection string):

    DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" \\
        python scripts/import_real_data.py \\
        --file "/path/to/מחירים - ספקי מזון.xls" \\
        --sheet "גידרון" \\
        --user-email admin@yourcompany.com

Requires an EXISTING admin/manager user, identified by --user-email.
This script does NOT create a tenant or user — if none exists yet in
the target database, create one first (see scripts/create_admin.py).
"""
import argparse
import os
import shutil
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.repositories.user_repository import UserRepository
from app.services.import_service import ImportService
from app.services.import_analysis_service import ImportAnalysisService, ImportAnalysisError
from app.services.import_mapping_service import ImportMappingService, ImportMappingError
from app.services.import_validation_service import ImportValidationService, ImportValidationError
from app.services.import_execution_service import ImportExecutionService, ImportExecutionError


def main():
    parser = argparse.ArgumentParser(description="One-time real-data import into this process's configured database.")
    parser.add_argument("--file", required=True, help="Path to the Excel/CSV price list to import.")
    parser.add_argument("--sheet", default=None, help="Sheet name (for .xlsx/.xls). Defaults to the first sheet.")
    parser.add_argument("--user-email", required=True, help="Email of an EXISTING manager/admin user to run this import as.")
    parser.add_argument("--supplier-id", type=int, default=None, help="Optional: set if the whole file is one supplier's price list.")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: file not found: {args.file}")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        # Never print the full URL (it may contain a password) — just enough
        # to let you confirm this is really pointed at the database you expect.
        safe_target = db_url.split("@")[-1] if "@" in db_url else db_url
        print(f"Target database: ...@{safe_target}")

        user = UserRepository.get_by_email_any_tenant(args.user_email)
        if user is None:
            print(f"ERROR: no user found with email {args.user_email} in this database.")
            print("This script does not create tenants/users — create one first "
                  "(see scripts/create_admin.py) or pass an existing admin's email.")
            sys.exit(1)
        if user.role not in ("admin", "manager"):
            print(f"ERROR: user {args.user_email} has role '{user.role}' — need admin or manager to commit an import.")
            sys.exit(1)

        tenant_id = user.tenant_id
        print(f"Running as: {user.full_name} <{user.email}> (role={user.role}, tenant_id={tenant_id})")

        # Stage the file the same way the upload route does — a persistent
        # copy under UPLOAD_FOLDER/imports/, since Analysis re-opens
        # session.storage_path later in the pipeline.
        ext = os.path.splitext(args.file)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], "imports", unique_name)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        shutil.copy2(args.file, save_path)
        filename = os.path.basename(args.file)

        # --- 1. Upload / stage --------------------------------------------------
        import_service = ImportService(tenant_id, user.id)
        session = import_service.create_session_and_parse(
            filename=filename, storage_path=save_path, supplier_id=args.supplier_id, sheet_name=args.sheet,
        )
        db.session.commit()
        print(f"\n[1/5] Staged: session_id={session.id}, status={session.status}, rows={session.row_count}")
        if session.status == "FAILED":
            print(f"ERROR: {session.error_message}")
            sys.exit(1)

        # --- 2. Analyze -----------------------------------------------------------
        analysis_service = ImportAnalysisService(tenant_id, user.id)
        try:
            analyses = analysis_service.analyze(session.id)
        except ImportAnalysisError as exc:
            db.session.rollback()
            print(f"ERROR during analysis: {exc}")
            sys.exit(1)
        db.session.commit()
        print(f"[2/5] Analyzed: {len(analyses)} sheet(s), workbook has {session.workbook_sheet_count} sheet(s) total")

        # --- 3. Mapping (auto-generated suggestions, approved as-is) --------------
        mapping_service = ImportMappingService(tenant_id, user.id)
        try:
            mapping, matching_templates = mapping_service.get_or_create_mapping(session.id)
        except ImportMappingError as exc:
            db.session.rollback()
            print(f"ERROR during mapping: {exc}")
            sys.exit(1)
        db.session.commit()

        mapped_cols = [c for c in mapping.columns if c.final_target != "IGNORE"]
        print(f"[3/5] Mapped: {len(mapping.columns)} column(s), {len(mapped_cols)} mapped to a real field")
        for c in mapped_cols:
            if not c.column_header.startswith("עמודה"):
                extra = f" -> {c.final_supplier_name}" if c.final_supplier_name else ""
                print(f"       col {c.column_index}: {c.column_header!r} => {c.final_target}{extra}")

        mapping = mapping_service.approve_mapping(mapping.id)
        db.session.commit()
        print(f"       Mapping approved (status={mapping.status})")

        # --- 4. Validate ------------------------------------------------------------
        validation_service = ImportValidationService(tenant_id, user.id)
        try:
            validation = validation_service.validate(session.id)
        except ImportValidationError as exc:
            db.session.rollback()
            print(f"ERROR during validation: {exc}")
            sys.exit(1)
        db.session.commit()
        print(
            f"[4/5] Validated: {validation.products_to_create} to create, "
            f"{validation.products_to_update} to update, {validation.products_to_skip} to skip, "
            f"{validation.suppliers_to_create} new supplier(s), "
            f"{validation.offers_to_create} offer(s) to create, "
            f"{validation.warning_count} warning(s), {validation.error_count} error(s)"
        )

        # --- 5. Commit ----------------------------------------------------------------
        execution_service = ImportExecutionService(tenant_id, user.id)
        try:
            execution = execution_service.commit(session.id)
        except ImportExecutionError as exc:
            db.session.rollback()
            print(f"ERROR during commit: {exc}")
            sys.exit(1)
        db.session.commit()

        print(f"\n[5/5] COMMITTED - execution_id={execution.id}, status={execution.status}")
        print(f"       Suppliers created: {execution.suppliers_created}")
        print(f"       Products created:  {execution.products_created}")
        print(f"       Products updated:  {execution.products_updated}")
        print(f"       Offers created:    {execution.offers_created}")
        if execution.skipped_rows:
            print(f"       Skipped rows ({len(execution.skipped_rows)}):")
            for s in execution.skipped_rows[:10]:
                print(f"         row {s['row_number']}: {s['reason']}")
            if len(execution.skipped_rows) > 10:
                print(f"         ... and {len(execution.skipped_rows) - 10} more")

        print(f"\nTo roll this back: POST /api/imports/executions/{execution.id}/rollback (as this same user)")


if __name__ == "__main__":
    main()
