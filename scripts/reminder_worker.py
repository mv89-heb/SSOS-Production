"""Process due order reminders with locking, recurrence, escalation and push delivery."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.order import (
    Order,
    REMINDER_DUE,
    REMINDER_PENDING,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_SENT,
)
from app.models.user import ROLE_MANAGER, User
from app.services.audit_service import AuditService
from app.services.web_push_service import send_to_user

DEFAULT_NAG_MINUTES = 60


def _utc(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _dashboard_url(order):
    from flask import current_app
    return current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") + f"/dashboard/orders/{order.id}"


def _notify(user_id, tenant_id, title, message, action_url, notification_type, order_id, order_number):
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        message=message,
        status=STATUS_UNREAD,
        action_url=action_url,
        notification_type=notification_type,
    )
    db.session.add(notification)
    db.session.flush()
    AuditService.log_event(
        tenant_id,
        user_id,
        notification_type,
        title=title,
        metadata={"order_id": order_id, "order_number": order_number},
    )
    db.session.commit()
    send_to_user(
        user_id,
        {"title": title, "body": message, "url": action_url, "notification_id": notification.id, "order_id": order_id, "type": notification_type},
    )


def process_due_reminders() -> int:
    now = datetime.now(timezone.utc)
    due_orders = list(
        db.session.execute(
            select(Order)
            .where(
                Order.next_reminder_at.is_not(None),
                Order.next_reminder_at <= now,
                Order.reminder_state == REMINDER_PENDING,
                Order.status.notin_((STATUS_SENT, STATUS_COMPLETED, STATUS_CANCELLED)),
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()
    )

    processed = 0
    for order in due_orders:
        rules = order.reminder_rules_snapshot or {}
        recurrence = rules.get("recurrence")
        escalation = rules.get("escalation") or {}
        occurrences = int(rules.get("occurrences", 0)) + 1
        rules["occurrences"] = occurrences

        action_url = order.google_calendar_event_url or _dashboard_url(order)
        title = f"תזכורת להזמנה {order.order_number}"
        message = f"הגיע מועד המעקב אחר ההזמנה מול {order.supplier_name}."

        # All reminders are persistent by default: if no explicit recurrence
        # policy exists, keep nudging every hour until the user marks it done.
        if recurrence is None:
            recurrence = {"every_minutes": DEFAULT_NAG_MINUTES, "max_occurrences": 0}
            rules["recurrence"] = recurrence
        order.reminder_rules_snapshot = rules

        repeat_minutes = int(recurrence.get("every_minutes", 0) or 0)
        max_occurrences = int(recurrence.get("max_occurrences", 0) or 0)
        should_repeat = repeat_minutes >= 5 and (max_occurrences <= 0 or occurrences < max_occurrences)

        if should_repeat:
            order.next_reminder_at = now + timedelta(minutes=repeat_minutes)
            order.reminder_state = REMINDER_PENDING
            notification_type = "reminder_recurrence"
        else:
            order.reminder_state = REMINDER_DUE
            notification_type = "reminder_due"

        notification = Notification(
            tenant_id=order.tenant_id,
            user_id=order.user_id,
            title=title,
            message=message,
            status=STATUS_UNREAD,
            action_url=action_url,
            notification_type=notification_type,
        )
        db.session.add(notification)
        db.session.flush()
        AuditService.log_event(
            order.tenant_id,
            order.user_id,
            notification_type,
            title=title,
            metadata={"order_id": order.id, "order_number": order.order_number, "occurrence": occurrences, "recurring": should_repeat},
        )

        send_to_user(
            order.user_id,
            {"title": title, "body": message, "url": action_url, "notification_id": notification.id, "order_id": order.id, "type": notification_type},
        )

        escalation_after = int(escalation.get("after_occurrences", 0) or 0)
        if escalation_after and occurrences >= escalation_after and not rules.get("escalated"):
            managers = db.session.execute(
                select(User).where(User.tenant_id == order.tenant_id, User.active.is_(True), User.role == ROLE_MANAGER)
            ).scalars().all()
            for manager in managers:
                manager_url = action_url
                manager_message = f"הזמנה {order.order_number} עדיין דורשת טיפול של {order.supplier_name}."
                _notify(
                    manager.id,
                    order.tenant_id,
                    "התראת הסלמה על תזכורת",
                    manager_message,
                    manager_url,
                    "reminder_escalation",
                    order.id,
                    order.order_number,
                )
            rules["escalated"] = True

        processed += 1

    if processed:
        db.session.commit()
    return processed


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        count = process_due_reminders()
        print(f"Processed {count} due order reminder(s).")
