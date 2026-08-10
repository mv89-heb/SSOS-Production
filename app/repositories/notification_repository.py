from sqlalchemy import select

from app.extensions import db
from app.models.notification import Notification
from app.repositories.base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    model = Notification

    def list_for_user(self, user_id: int, unread_only: bool = False):
        stmt = self._tenant_select().where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.status == "unread")
        stmt = stmt.order_by(Notification.id.desc())
        return list(db.session.execute(stmt).scalars().all())
