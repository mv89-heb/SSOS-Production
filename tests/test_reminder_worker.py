from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models.notification import Notification
from app.models.order import (
    Order,
    REMINDER_DUE,
    REMINDER_PENDING,
    STATUS_CANCELLED,
    STATUS_DRAFT,
)
from app.models.tenant import Tenant
from app.models.user import ROLE_ADMIN, ROLE_MANAGER, User


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _seed_order(db_session, *, next_reminder_at, rules=None, status=STATUS_DRAFT):
    tenant = Tenant(name="Reminder Tenant", slug="reminder-tenant")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="reminder-owner@test.local",
        full_name="Reminder Owner",
        password_hash="test-hash",
        role=ROLE_ADMIN,
        active=True,
    )
    manager = User(
        tenant_id=tenant.id,
        email="reminder-manager@test.local",
        full_name="Reminder Manager",
        password_hash="test-hash",
        role=ROLE_MANAGER,
        active=True,
    )
    db_session.add_all([user, manager])
    db_session.flush()

    order = Order(
        tenant_id=tenant.id,
        user_id=user.id,
        order_number="ORD-REM-001",
        supplier_name="Test Supplier",
        status=status,
        reminder_state=REMINDER_PENDING,
        next_reminder_at=next_reminder_at,
        reminder_rules_snapshot=rules or {},
    )
    db_session.add(order)
    db_session.commit()
    return order, user, manager


def test_wait_skips_when_no_reminder_in_window(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    _seed_order(db.session, next_reminder_at=now + timedelta(minutes=10))
    slept = []
    monkeypatch.setattr(reminder_worker.time, "sleep", lambda seconds: slept.append(seconds))

    with app.app_context():
        reminder_worker._wait_for_nearby_reminders()

    assert slept == []


def test_waits_only_until_earliest_upcoming_reminder(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    _seed_order(db.session, next_reminder_at=now + timedelta(minutes=2))
    slept = []
    monkeypatch.setattr(reminder_worker.time, "sleep", lambda seconds: slept.append(seconds))

    with app.app_context():
        reminder_worker._wait_for_nearby_reminders()

    assert len(slept) == 1
    assert 100 <= slept[0] <= 125


def test_due_reminder_is_persisted_before_push(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    order, user, _ = _seed_order(
        db.session,
        next_reminder_at=now - timedelta(seconds=1),
        rules={"ai": {"urgency": "high", "score": 87, "reason": "Supplier follow-up is due."}},
    )
    monkeypatch.setattr(reminder_worker, "_wait_for_nearby_reminders", lambda: None)
    push_payloads = []

    def fake_push(user_id, payload):
        persisted = db.session.get(Order, order.id)
        notification = db.session.get(Notification, payload["notification_id"])
        assert persisted.reminder_state == REMINDER_DUE
        assert persisted.next_reminder_at is None
        assert notification is not None
        push_payloads.append((user_id, payload))

    monkeypatch.setattr(reminder_worker, "send_to_user", fake_push)

    with app.app_context():
        processed = reminder_worker.process_due_reminders()
        refreshed = db.session.get(Order, order.id)

    assert processed == 1
    assert refreshed.reminder_state == REMINDER_DUE
    assert refreshed.next_reminder_at is None
    assert len(push_payloads) == 1
    assert push_payloads[0][0] == user.id


def test_cancelled_reminder_is_not_processed(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    order, _, _ = _seed_order(
        db.session,
        next_reminder_at=now - timedelta(minutes=1),
        status=STATUS_CANCELLED,
    )
    monkeypatch.setattr(reminder_worker, "_wait_for_nearby_reminders", lambda: None)
    monkeypatch.setattr(reminder_worker, "send_to_user", lambda *_args, **_kwargs: pytest.fail("push should not be sent"))

    with app.app_context():
        processed = reminder_worker.process_due_reminders()
        refreshed = db.session.get(Order, order.id)

    assert processed == 0
    assert refreshed.reminder_state == REMINDER_PENDING
    assert db.session.query(Notification).count() == 0


def test_recurring_reminder_schedules_next_occurrence(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    order, _, _ = _seed_order(
        db.session,
        next_reminder_at=now - timedelta(seconds=1),
        rules={"recurrence": {"every_minutes": 15, "max_occurrences": 2}},
    )
    monkeypatch.setattr(reminder_worker, "_wait_for_nearby_reminders", lambda: None)
    monkeypatch.setattr(reminder_worker, "send_to_user", lambda *_args, **_kwargs: None)

    with app.app_context():
        processed = reminder_worker.process_due_reminders()
        refreshed = db.session.get(Order, order.id)

    assert processed == 1
    assert refreshed.reminder_state == REMINDER_PENDING
    assert refreshed.next_reminder_at is not None
    assert _aware(refreshed.next_reminder_at) > datetime.now(timezone.utc) + timedelta(minutes=14)
    assert refreshed.reminder_rules_snapshot["occurrences"] == 1


def test_escalation_notifies_active_managers(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    order, _, manager = _seed_order(
        db.session,
        next_reminder_at=now - timedelta(seconds=1),
        rules={"escalation": {"after_occurrences": 1}},
    )
    monkeypatch.setattr(reminder_worker, "_wait_for_nearby_reminders", lambda: None)
    pushed = []
    monkeypatch.setattr(reminder_worker, "send_to_user", lambda user_id, payload: pushed.append((user_id, payload)))

    with app.app_context():
        processed = reminder_worker.process_due_reminders()
        refreshed = db.session.get(Order, order.id)
        notifications = db.session.query(Notification).all()

    assert processed == 1
    assert refreshed.reminder_rules_snapshot["escalated"] is True
    assert any(n.notification_type == "reminder_escalation" and n.user_id == manager.id for n in notifications)
    assert len(pushed) == 2


def test_push_failure_does_not_rollback_reminder(app, db, monkeypatch):
    from scripts import reminder_worker

    now = datetime.now(timezone.utc)
    order, _, _ = _seed_order(db.session, next_reminder_at=now - timedelta(seconds=1))
    monkeypatch.setattr(reminder_worker, "_wait_for_nearby_reminders", lambda: None)

    def failing_push(*_args, **_kwargs):
        raise RuntimeError("push unavailable")

    monkeypatch.setattr(reminder_worker, "send_to_user", failing_push)

    with app.app_context():
        processed = reminder_worker.process_due_reminders()
        refreshed = db.session.get(Order, order.id)
        notifications = db.session.query(Notification).count()

    assert processed == 1
    assert refreshed.reminder_state == REMINDER_DUE
    assert notifications == 1
