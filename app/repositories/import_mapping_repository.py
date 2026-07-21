from sqlalchemy import select
from app.extensions import db
from app.models.import_mapping import ImportMapping, ImportMappingColumn, ImportMappingTemplate
from app.repositories.base_repository import BaseRepository


class ImportMappingRepository(BaseRepository):
    model = ImportMapping

    def get_by_session_and_sheet(self, import_session_id: int, sheet_name: str):
        stmt = self._tenant_select().where(
            ImportMapping.import_session_id == import_session_id,
            ImportMapping.sheet_name == sheet_name,
        )
        return db.session.execute(stmt).scalar_one_or_none()


class ImportMappingColumnRepository(BaseRepository):
    model = ImportMappingColumn

    def get_by_mapping(self, import_mapping_id: int):
        stmt = (
            self._tenant_select()
            .where(ImportMappingColumn.import_mapping_id == import_mapping_id)
            .order_by(ImportMappingColumn.column_index.asc())
        )
        return list(db.session.execute(stmt).scalars().all())

    def bulk_add(self, columns: list) -> None:
        db.session.add_all(columns)
        db.session.flush()


class ImportMappingTemplateRepository(BaseRepository):
    model = ImportMappingTemplate

    def list_all(self, limit: int = 50):
        stmt = self._tenant_select().order_by(ImportMappingTemplate.created_at.desc()).limit(limit)
        return list(db.session.execute(stmt).scalars().all())

    def get_by_supplier(self, supplier_id: int):
        stmt = self._tenant_select().where(ImportMappingTemplate.supplier_id == supplier_id)
        return list(db.session.execute(stmt).scalars().all())

    def get_by_source_filename(self, filename: str):
        stmt = self._tenant_select().where(ImportMappingTemplate.source_filename == filename)
        return list(db.session.execute(stmt).scalars().all())
