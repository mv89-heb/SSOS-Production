from datetime import datetime, timezone

from app.models.notification import Notification, STATUS_READ, STATUS_UNREAD
from app.repositories.notification_repository import NotificationRepository
from werkzeug.exceptions import NotFound


class NotificationService:
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.repo = NotificationRepository(tenant_id=tenant_id)

    def list_for_user(self, user_id: int, unread_only: bool = False):
        return self.repo.list_for_user(user_id, unread_only=unread_only)

    def create(self, user_id: int, title: str, message: str = "") -> Notification:
        notification = Notification(
            tenant_id=self.tenant_id,
            user_id=user_id,
            title=title,
            message=message,
            status=STATUS_UNREAD,
        )
        self.repo.add(notification)
        self.repo.commit()
        return notification

    def mark_read(self, notification_id: int, user_id: int) -> Notification:
        notification = self.repo.get_by_id(notification_id)
        if notification is None or notification.user_id != user_id:
            raise NotFound("Notification not found")
        notification.status = STATUS_READ
        notification.read_at = datetime.now(timezone.utc)
        self.repo.commit()
        return notification
