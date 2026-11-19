from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User
from app.services.inventory_calendar_service import InventoryCalendarService
from scripts.inventory_count_reminder import process_inventory_count_reminders


def test_weekly_reminder_describes_assigned_group_and_is_deduplicated(
    app, db, tenant_a_admin, monkeypatch
):
    registration, _ = tenant_a_admin
    tenant_id = registration["tenant"]["id"]
    user = db.session.scalar(select(User).where(User.tenant_id == tenant_id))
    assert user is not None

    monkeypatch.setattr(
        InventoryCalendarService,
        "count_status",
        lambda self: {
            "active_products": 900,
            "assigned_products": 225,
            "completion_percent": 25.0,
            "due": True,
            "next_due_date": "2026-11-22",
        },
    )
    monkeypatch.setattr(
        "scripts.inventory_count_reminder.send_to_user",
        lambda *args, **kwargs: None,
    )

    assert process_inventory_count_reminders() == 1
    notification = db.session.scalar(
        select(Notification).where(
            Notification.tenant_id == tenant_id,
            Notification.user_id == user.id,
            Notification.notification_type == "inventory_count_due",
        )
    )
    assert notification is not None
    assert "25.0%" in notification.message
    assert "225 המוצרים שהוקצו לשבוע זה" in notification.message
    assert "ספירה מלאה" not in notification.message

    # A repeated worker run must not create a duplicate reminder for the same week.
    assert process_inventory_count_reminders() == 0
