from __future__ import annotations

from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.web_push_service import send_to_user


def notify(
    order,
    *,
    title: str,
    message: str,
    notification_type: str,
    action_url: str | None = None,
    audit_action: str | None = None,
    audit_title: str | None = None,
    audit_metadata: dict | None = None,
) -> None:
    service = NotificationService(tenant_id=order.tenant_id)
    notification = service.create(
        order.user_id,
        title=title,
        message=message,
        action_url=action_url,
        notification_type=notification_type,
        commit=False,
    )
    from app.extensions import db
    db.session.commit()

    push_url = action_url or order.google_calendar_event_url
    send_to_user(
        order.user_id,
        {
            "title": title,
            "body": message,
            "url": push_url,
            "notification_id": notification.id,
            "order_id": order.id,
            "type": notification_type,
        },
    )

    if audit_action:
        AuditService.log_event(
            order.tenant_id,
            order.user_id,
            audit_action,
            title=audit_title or title,
            metadata={"order_id": order.id, "order_number": order.order_number, **(audit_metadata or {})},
        )
        db.session.commit()
