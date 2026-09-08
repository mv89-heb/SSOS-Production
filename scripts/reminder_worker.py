"""Process due order reminders with locking, recurrence, escalation and push delivery."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.order import Order, REMINDER_DUE, REMINDER_PENDING, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_SENT
from app.models.user import ROLE_MANAGER, User
from app.services.audit_service import AuditService
from app.services.web_push_service import send_to_user

DEFAULT_NAG_MINUTES = 60


def _dashboard_url(order):
    from flask import current_app
    return current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") + f"/dashboard/orders/{order.id}"


def _urgency_text(rules: dict) -> tuple[str, str]:
    ai = rules.get("ai") or {}
    urgency = str(ai.get("urgency") or "normal")
    score = ai.get("score")
    labels = {"critical": "🔴 דחיפות קריטית", "high": "🟠 דחיפות גבוהה", "normal": "🟡 דחיפות רגילה", "low": "🟢 דחיפות נמוכה"}
    return labels.get(urgency, labels["normal"]), f" (ציון {score})" if score is not None else ""


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

            escalation_after = int(escalation.get("after_occurrences", 0) or 0)
            if escalation_after and occurrences >= escalation_after and not rules.get("escalated"):
                managers = db.session.execute(
                    select(User).where(User.tenant_id == order.tenant_id, User.active.is_(True), User.role == ROLE_MANAGER)
                ).scalars().all()
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
                rules["escalated"] = True
                order.reminder_rules_snapshot = rules

            processed += 1

        if processed:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise

    # Database state is now durable before push delivery. A push failure must
    # never roll back the reminder or cause a duplicate notification on retry.
    for user_id, payload in push_events:
        try:
            send_to_user(user_id, payload)
        except Exception:
            # Push is best-effort; the in-app Notification remains available.
            from flask import current_app
            current_app.logger.exception("Reminder push delivery failed for user %s", user_id)

    return processed


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        count = process_due_reminders()
        print(f"Processed {count} due order reminder(s).")
