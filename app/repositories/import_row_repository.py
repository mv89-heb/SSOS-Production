from sqlalchemy import select
from app.extensions import db
from app.models.import_row import ImportRow
from app.repositories.base_repository import BaseRepository


class ImportRowRepository(BaseRepository):
    model = ImportRow

    def get_by_session(self, import_session_id: int, limit: int = 100, offset: int = 0):
        stmt = (
            self._tenant_select()
            .where(ImportRow.import_session_id == import_session_id)
            .order_by(ImportRow.row_number.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(db.session.execute(stmt).scalars().all())

    def get_all_by_session(self, import_session_id: int):
        """Phase 3.2C: every staged row for a session, uncapped — used by
        Validation, which must process the whole file, not a UI page of it."""
        stmt = (
            self._tenant_select()
            .where(ImportRow.import_session_id == import_session_id)
            .order_by(ImportRow.row_number.asc())
        )
        return list(db.session.execute(stmt).scalars().all())

    def count_by_session(self, import_session_id: int) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(ImportRow).where(
            ImportRow.tenant_id == self.tenant_id,
            ImportRow.import_session_id == import_session_id,
        )
        return db.session.execute(stmt).scalar_one()

    def bulk_add(self, rows: list) -> None:
        db.session.add_all(rows)
        db.session.flush()
