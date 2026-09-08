from datetime import datetime, timedelta, timezone


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_due_reminder_worker_repeats_until_completed(app, db, make_order, logged_in_client_a, monkeypatch):
    from app.models.notification import Notification, STATUS_UNREAD
    from app.models.order import Order, REMINDER_PENDING, REMINDER_COMPLETE
    from scripts.reminder_worker import process_due_reminders

    monkeypatch.setattr("scripts.reminder_worker.send_to_user", lambda *_args, **_kwargs: 1)

    response, _, _ = make_order(logged_in_client_a, supplier_name="Worker Supplier")
    assert response.status_code == 201, response.get_json()
    order_id = response.get_json()["order"]["id"]

    order = db.session.get(Order, order_id)
    order.reminder_state = REMINDER_PENDING
    order.next_reminder_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()

    assert process_due_reminders() == 1

    order = db.session.get(Order, order_id)
    assert order.reminder_state == REMINDER_PENDING
    assert _aware(order.next_reminder_at) > datetime.now(timezone.utc)
    first_next = _aware(order.next_reminder_at)

    notifications = db.session.query(Notification).filter_by(tenant_id=order.tenant_id, user_id=order.user_id).all()
    reminder_notifications = [item for item in notifications if "תזכורת להזמנה" in item.title]
    assert len(reminder_notifications) == 1
    assert reminder_notifications[0].status == STATUS_UNREAD

    order.next_reminder_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()

    assert process_due_reminders() == 1

    order = db.session.get(Order, order_id)
    assert order.reminder_state == REMINDER_PENDING
    assert _aware(order.next_reminder_at) > first_next

    reminder_notifications = [item for item in db.session.query(Notification).filter_by(tenant_id=order.tenant_id, user_id=order.user_id).all() if "תזכורת להזמנה" in item.title]
    assert len(reminder_notifications) == 2

    order.reminder_state = REMINDER_COMPLETE
    order.next_reminder_at = None
    db.session.commit()

    assert process_due_reminders() == 0
