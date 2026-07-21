from app.extensions import db
from app.models.import_validation import ImportValidation, ImportPreview, ImportIssue
from app.repositories.base_repository import BaseRepository


class ImportValidationRepository(BaseRepository):
    model = ImportValidation

    def get_latest_by_session(self, import_session_id: int):
        stmt = (
            self._tenant_select()
            .where(ImportValidation.import_session_id == import_session_id)
            .order_by(ImportValidation.created_at.desc())
            .limit(1)
        )
        return db.session.execute(stmt).scalar_one_or_none()

    def delete_previous_for_session(self, import_session_id: int) -> None:
        """Idempotent re-run — clears prior validation runs for this
        session before a new one is stored (mirrors ImportAnalysis)."""
        stmt = self._tenant_select().where(ImportValidation.import_session_id == import_session_id)
        for old in db.session.execute(stmt).scalars().all():
            db.session.delete(old)
        db.session.flush()


class ImportPreviewRepository(BaseRepository):
    model = ImportPreview

    def bulk_add(self, rows: list) -> None:
        db.session.add_all(rows)
        db.session.flush()

    def get_by_validation(self, import_validation_id: int, limit: int = 200, offset: int = 0):
        stmt = (
            self._tenant_select()
            .where(ImportPreview.import_validation_id == import_validation_id)
            .order_by(ImportPreview.row_number.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.session.execute(stmt).scalars().all())

    def get_all_by_validation(self, import_validation_id: int):
        """Phase 3.2D: every preview row for a validation, uncapped — used
        by Import Execution, which must commit the whole file, not a UI page."""
        stmt = (
            self._tenant_select()
            .where(ImportPreview.import_validation_id == import_validation_id)
            .order_by(ImportPreview.row_number.asc())
        )
        return list(db.session.execute(stmt).scalars().all())


class ImportIssueRepository(BaseRepository):
    model = ImportIssue

    def bulk_add(self, rows: list) -> None:
        db.session.add_all(rows)
        db.session.flush()

    def get_by_validation(self, import_validation_id: int):
        stmt = (
            self._tenant_select()
            .where(ImportIssue.import_validation_id == import_validation_id)
            .order_by(ImportIssue.row_number.asc())
        )
        return list(db.session.execute(stmt).scalars().all())
