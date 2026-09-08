"""Process due order reminders with locking, recurrence, escalation and push delivery."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import time

from flask import current_app
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.order import Order, REMINDER_DUE, REMINDER_PENDING, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_SENT
from app.models.user import ROLE_MANAGER, User
from app.services.audit_service import AuditService
from app.services.web_push_service import send_to_user

DEFAULT_NAG_MINUTES = 60
DEFAULT_EXECUTION_WINDOW_MINUTES = 5


def _dashboard_url(order):
    return current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") + f"/dashboard/orders/{order.id}"


def _urgency_text(rules: dict) -> tuple[str, str]:
    ai = rules.get("ai") or {}
    urgency = str(ai.get("urgency") or "normal")
    score = ai.get("score")
    labels = {"critical": "🔴 דחיפות קריטית", "high": "🟠 דחיפות גבוהה", "normal": "🟡 דחיפות רגילה", "low": "🟢 דחיפות נמוכה"}
    return labels.get(urgency, labels["normal"]), f" (ציון {score})" if score is not None else ""


def _execution_window_minutes() -> int:
    try:
        value = int(current_app.config.get("REMINDER_EXECUTION_WINDOW_MINUTES", DEFAULT_EXECUTION_WINDOW_MINUTES))
    except (TypeError, ValueError):
        value = DEFAULT_EXECUTION_WINDOW_MINUTES
    return max(0, value)


def _as_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime for both PostgreSQL and SQLite values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _wait_for_nearby_reminders() -> None:
    """Wait for the earliest reminder inside the configured execution window.

    Database timestamps remain authoritative. The worker never holds row locks
    while sleeping; after the wait, the due query re-checks state and status so
    a reminder cancelled or completed during the wait is not delivered.
    """
    window_minutes = _execution_window_minutes()
    if window_minutes <= 0:
        return

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=window_minutes)

    upcoming = db.session.execute(
        select(Order.next_reminder_at)
        .where(
            Order.next_reminder_at.is_not(None),
            Order.next_reminder_at > now,
            Order.next_reminder_at <= window_end,
            Order.reminder_state == REMINDER_PENDING,
            Order.status.notin_((STATUS_SENT, STATUS_COMPLETED, STATUS_CANCELLED)),
        )
        .order_by(Order.next_reminder_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    db.session.rollback()

    if upcoming is None:
        return

    upcoming = _as_utc(upcoming)
    wait_seconds = (upcoming - datetime.now(timezone.utc)).total_seconds()
    if wait_seconds <= 0:
        return

    time.sleep(min(wait_seconds, window_minutes * 60))


def process_due_reminders() -> int:
    # If a run starts shortly before the target, wait until the target instead
    # of firing early. If GitHub starts late, <= now catches the reminder.
    _wait_for_nearby_reminders()

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
    push_events = []

    try:
        for order in due_orders:
            rules = deepcopy(order.reminder_rules_snapshot or {})
            recurrence = rules.get("recurrence")
            escalation = rules.get("escalation") or {}
            occurrences = int(rules.get("occurrences", 0)) + 1
            rules["occurrences"] = occurrences

            action_url = order.google_calendar_event_url or _dashboard_url(order)
            urgency_label, score_text = _urgency_text(rules)
            title = f"{urgency_label} — תזכורת להזמנה {order.order_number}"
            reason = str((rules.get("ai") or {}).get("reason") or "")
            message = f"הגיע מועד המעקב אחר ההזמנה מול {order.supplier_name}."
            if reason:
                message += f" {reason}"
            message += f"{score_text}"

            if recurrence is None:
                recurrence = {"every_minutes": DEFAULT_NAG_MINUTES, "max_occurrences": 0}
                rules["recurrence"] = recurrence

            repeat_minutes = int(recurrence.get("every_minutes", 0) or 0)
            max_occurrences = int(recurrence.get("max_occurrences", 0) or 0)
            should_repeat = repeat_minutes >= 5 and (max_occurrences <= 0 or occurrences < max_occurrences)

            if should_repeat:
                order.next_reminder_at = now + timedelta(minutes=repeat_minutes)
                order.reminder_state = REMINDER_PENDING
                notification_type = "reminder_recurrence"
            else:
                order.reminder_state = REMINDER_DUE
                order.next_reminder_at = None
                notification_type = "reminder_due"

            escalation_after = int(escalation.get("after_occurrences", 0) or 0)
            should_escalate = escalation_after and occurrences >= escalation_after and not rules.get("escalated")
            if should_escalate:
                managers = db.session.execute(
                    select(User).where(User.tenant_id == order.tenant_id, User.active.is_(True), User.role == ROLE_MANAGER)
                ).scalars().all()
                rules["escalated"] = True
                for manager in managers:
                    manager_message = f"הזמנה {order.order_number} עדיין דורשת טיפול של {order.supplier_name}. {urgency_label}."
                    manager_notification = Notification(
                        tenant_id=order.tenant_id,
                        user_id=manager.id,
                        title="התראת הסלמה על תזכורת",
                        message=manager_message,
                        status=STATUS_UNREAD,
                        action_url=action_url,
                        notification_type="reminder_escalation",
                    )
                    db.session.add(manager_notification)
                    db.session.flush()
                    AuditService.log_event(
                        order.tenant_id,
                        manager.id,
                        "reminder_escalation",
                        title="התראת הסלמה על תזכורת",
                        metadata={"order_id": order.id, "order_number": order.order_number},
                    )
                    push_events.append((manager.id, {"title": "התראת הסלמה על תזכורת", "body": manager_message, "url": action_url, "notification_id": manager_notification.id, "order_id": order.id, "type": "reminder_escalation"}))

            order.reminder_rules_snapshot = rules

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
                metadata={
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "occurrence": occurrences,
                    "recurring": should_repeat,
                    "urgency": (rules.get("ai") or {}).get("urgency"),
                    "urgency_score": (rules.get("ai") or {}).get("score"),
                },
            )
            push_events.append((order.user_id, {"title": title, "body": message, "url": action_url, "notification_id": notification.id, "order_id": order.id, "type": notification_type}))
            processed += 1

        if processed:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise

    # Database state is durable before push delivery. Push is best-effort and
    # can never roll back the reminder or cause a duplicate DB notification.
    for user_id, payload in push_events:
        try:
            send_to_user(user_id, payload)
        except Exception:
            current_app.logger.exception("Reminder push delivery failed for user %s", user_id)

    return processed


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        count = process_due_reminders()
        print(f"Processed {count} due order reminder(s).")
