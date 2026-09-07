"""Process due order reminders and create in-app notifications.

Run once per invocation (Render Cron executes this every minute).
"""
from datetime import datetime, timezone

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
        )
        .scalars()
        .all()
    )

    processed = 0
    for order in due_orders:
        order.reminder_state = REMINDER_DUE
        db.session.add(
            Notification(
                tenant_id=order.tenant_id,
                user_id=order.user_id,
                title=f"תזכורת להזמנה {order.order_number}",
                message=f"הגיע מועד המעקב אחר ההזמנה מול {order.supplier_name}.",
                status=STATUS_UNREAD,
            )
        )
        processed += 1

    if processed:
        db.session.commit()
    return processed


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        count = process_due_reminders()
        print(f"Processed {count} due order reminder(s).")
