from sqlalchemy import select
from app.extensions import db
from app.models.import_session import ImportSession
from app.repositories.base_repository import BaseRepository


class ImportSessionRepository(BaseRepository):
    model = ImportSession

    def list_recent(self, limit: int = 50):
        stmt = self._tenant_select().order_by(ImportSession.created_at.desc()).limit(limit)
        return list(db.session.execute(stmt).scalars().all())
