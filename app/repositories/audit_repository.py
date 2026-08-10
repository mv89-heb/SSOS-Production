from sqlalchemy import select

from app.extensions import db
from app.models.audit import AuditLog
from app.repositories.base_repository import BaseRepository


class AuditRepository(BaseRepository):
    model = AuditLog

    def latest(self):
        stmt = self._tenant_select().order_by(AuditLog.id.desc()).limit(1)
        return db.session.execute(stmt).scalar_one_or_none()

    def all_ordered(self):
        stmt = self._tenant_select().order_by(AuditLog.id.asc())
        return list(db.session.execute(stmt).scalars().all())
