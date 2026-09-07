from datetime import datetime, timedelta, timezone


def test_due_reminder_worker_creates_notification_once(app, db, make_order, logged_in_client_a):
    from app.models.notification import Notification, STATUS_UNREAD
    from app.models.order import Order, REMINDER_DUE, REMINDER_PENDING
    from scripts.reminder_worker import process_due_reminders

    response, _, _ = make_order(logged_in_client_a, supplier_name="Worker Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    order = db.session.get(Order, order_id)
    order.reminder_state = REMINDER_PENDING
    order.next_reminder_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()

    assert process_due_reminders() == 1

    order = db.session.get(Order, order_id)
    assert order.reminder_state == REMINDER_DUE

    notifications = db.session.query(Notification).filter_by(
        tenant_id=order.tenant_id,
        user_id=order.user_id,
    ).all()
    reminder_notifications = [item for item in notifications if item.title == f"תזכורת להזמנה {order.order_number}"]
    assert len(reminder_notifications) == 1
    assert reminder_notifications[0].status == STATUS_UNREAD

    assert process_due_reminders() == 0
    notifications = db.session.query(Notification).filter_by(
        tenant_id=order.tenant_id,
        user_id=order.user_id,
    ).all()
    reminder_notifications = [item for item in notifications if item.title == f"תזכורת להזמנה {order.order_number}"]
    assert len(reminder_notifications) == 1
