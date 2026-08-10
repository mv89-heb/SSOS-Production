from app.extensions import db
from app.models.import_analysis import ImportAnalysis
from app.repositories.base_repository import BaseRepository


class ImportAnalysisRepository(BaseRepository):
    model = ImportAnalysis

    def get_by_session(self, import_session_id: int):
        stmt = (
            self._tenant_select()
            .where(ImportAnalysis.import_session_id == import_session_id)
            .order_by(ImportAnalysis.sheet_index.asc())
        )
        return list(db.session.execute(stmt).scalars().all())

    def delete_by_session(self, import_session_id: int) -> None:
        """Used to make re-running analysis idempotent — old findings for
        this session are cleared before the new ones are written."""
        for analysis in self.get_by_session(import_session_id):
            db.session.delete(analysis)
        db.session.flush()
