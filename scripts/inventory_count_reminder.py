"""Create one durable reminder when a weekly physical inventory count is due."""
from datetime import datetime, timezone

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.tenant import Tenant
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER
from app.services.inventory_calendar_service import InventoryCalendarService
from app.services.web_push_service import send_to_user


def process_inventory_count_reminders() -> int:
    processed = 0
    push_events = []
    tenants = db.session.scalars(select(Tenant).where(Tenant.active.is_(True))).all()
    for tenant in tenants:
        status = InventoryCalendarService(tenant.id).count_status()
        if not status["due"]:
            continue
        due_date = status["next_due_date"]
        dedupe_key = f"inventory-count:{tenant.id}:{due_date}"
        exists = db.session.execute(select(Notification.id).where(Notification.dedupe_key == dedupe_key).limit(1)).scalar_one_or_none()
        if exists is not None:
            continue
        users = db.session.scalars(
            select(User).where(
                User.tenant_id == tenant.id,
                User.active.is_(True),
                User.role.in_((ROLE_ADMIN, ROLE_MANAGER)),
            )
        ).all()
        if not users:
            continue
        title = "🔔 הגיע הזמן לספירת מלאי"
        message = f"הגיע מועד הספירה השבועית. הושלמו {status['completion_percent']}% מהמוצרים ב-7 הימים האחרונים."
        action_url = f"{__import__('flask').current_app.config.get('FRONTEND_PUBLIC_URL', '').rstrip('/')}/dashboard/inventory"
        for user in users:
            notification = Notification(
                tenant_id=tenant.id,
                user_id=user.id,
                title=title,
                message=message,
                status=STATUS_UNREAD,
                action_url=action_url,
                notification_type="inventory_count_due",
                dedupe_key=dedupe_key,
            )
            db.session.add(notification)
            db.session.flush()
            push_events.append((user.id, {"title": title, "body": message, "url": action_url, "notification_id": notification.id, "type": "inventory_count_due"}))
            processed += 1
    db.session.commit()
    for user_id, payload in push_events:
        try:
            send_to_user(user_id, payload)
        except Exception:
            db.session.rollback()
            continue
    return processed


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print(f"Created {process_inventory_count_reminders()} inventory count reminder(s).")
