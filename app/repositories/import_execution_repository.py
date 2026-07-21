from app.extensions import db
from app.models.import_execution import ImportExecution
from app.repositories.base_repository import BaseRepository


class ImportExecutionRepository(BaseRepository):
    model = ImportExecution

    def get_latest_by_session(self, import_session_id: int):
        stmt = (
            self._tenant_select()
            .where(ImportExecution.import_session_id == import_session_id)
            .order_by(ImportExecution.executed_at.desc())
            .limit(1)
        )
        return db.session.execute(stmt).scalar_one_or_none()
