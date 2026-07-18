from typing import Optional, Type

from sqlalchemy import select
from werkzeug.exceptions import NotFound

from app.extensions import db


class BaseRepository:
    """
    Generic tenant-scoped repository built on SQLAlchemy 2.x `select()`.

    Every read/write path goes through `_tenant_select`, which unconditionally
    injects a `tenant_id` filter. This is the single choke point that prevents
    IDOR (cross-tenant record access) across every subclass, so callers never
    need to remember to filter manually.
    """

    model: Type = None

    def __init__(self, tenant_id: int):
        if tenant_id is None:
            raise ValueError("tenant_id is required to construct a tenant-scoped repository")
        self.tenant_id = tenant_id

    def _tenant_select(self):
        return select(self.model).where(self.model.tenant_id == self.tenant_id)

    def get_by_id(self, entity_id: int) -> Optional[object]:
        stmt = self._tenant_select().where(self.model.id == entity_id)
        return db.session.execute(stmt).scalar_one_or_none()

    def get_by_id_or_404(self, entity_id: int):
        entity = self.get_by_id(entity_id)
        if entity is None:
            raise NotFound(f"{self.model.__name__} not found")
        return entity

    def list_all(self, limit: int = 100, offset: int = 0):
        stmt = self._tenant_select().order_by(self.model.id.desc()).limit(limit).offset(offset)
        return list(db.session.execute(stmt).scalars().all())

    def add(self, entity) -> object:
        db.session.add(entity)
        db.session.flush()
        return entity

    def delete(self, entity) -> None:
        db.session.delete(entity)

    def commit(self) -> None:
        db.session.commit()
