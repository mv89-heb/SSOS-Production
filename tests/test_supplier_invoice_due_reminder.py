from datetime import date, timedelta
from decimal import Decimal

from app.models.notification import Notification
from app.models.order import Order
from app.models.supplier import Supplier
from app.models.supplier_invoice import (
    INVOICE_APPROVAL_APPROVED,
    INVOICE_APPROVAL_PENDING,
    SupplierInvoice,
    SupplierInvoicePayment,
)
from app.models.tenant import Tenant
from app.models.user import ROLE_ADMIN, ROLE_EMPLOYEE, User


def _tenant_user(db, slug, email, role=ROLE_ADMIN):
    tenant = Tenant(name=f"Tenant {slug}", slug=slug, active=True)
    db.session.add(tenant)
    db.session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=email,
        role=role,
        active=True,
    )
    user.set_password("Test-password-123")
    db.session.add(user)
    db.session.flush()
    return tenant, user


def _invoice(db, tenant, user, invoice_number, due_date, approval_status=INVOICE_APPROVAL_APPROVED, amount="100.00"):
    supplier = Supplier(tenant_id=tenant.id, name=f"Supplier {invoice_number}", active=True)
    db.session.add(supplier)
    db.session.flush()
    order = Order(
        tenant_id=tenant.id,
        user_id=user.id,
        supplier_id=supplier.id,
        order_number=f"PO-{invoice_number}",
        supplier_name=supplier.name,
        status="sent",
        currency="ILS",
        items=[],
    )
    db.session.add(order)
    db.session.flush()
    invoice = SupplierInvoice(
        tenant_id=tenant.id,
        order_id=order.id,
        supplier_id=supplier.id,
        invoice_number=invoice_number,
        due_date=due_date,
        amount=Decimal(amount),
        currency="ILS",
        approval_status=approval_status,
    )
    db.session.add(invoice)
    db.session.flush()
    return invoice


def test_supplier_invoice_due_reminders_are_scoped_deduplicated_and_skip_ineligible_invoices(
    app, db, monkeypatch
):
    import scripts.supplier_invoice_due_reminder as worker

    pushed = []
    monkeypatch.setattr(worker, "send_to_user", lambda user_id, payload: pushed.append((user_id, payload)))

    today = date(2026, 10, 28)
    tenant_a, admin_a = _tenant_user(db, "invoice-reminder-a", "admin-a@example.test")
    tenant_b, admin_b = _tenant_user(db, "invoice-reminder-b", "admin-b@example.test")
    employee_a = User(
        tenant_id=tenant_a.id,
        email="employee-a@example.test",
        full_name="Employee A",
        role=ROLE_EMPLOYEE,
        active=True,
    )
    employee_a.set_password("Test-password-123")
    db.session.add(employee_a)
    db.session.flush()

    due_a = _invoice(db, tenant_a, admin_a, "DUE-A", today + timedelta(days=2))
    due_b = _invoice(db, tenant_b, admin_b, "DUE-B", today)
    _invoice(
        db,
        tenant_a,
        admin_a,
        "PENDING-A",
        today,
        approval_status=INVOICE_APPROVAL_PENDING,
    )
    paid = _invoice(db, tenant_a, admin_a, "PAID-A", today, amount="40.00")
    db.session.add(
        SupplierInvoicePayment(
            tenant_id=tenant_a.id,
            invoice_id=paid.id,
            amount=Decimal("40.00"),
            payment_date=today,
            reference="PAID-IN-FULL",
        )
    )
    db.session.commit()

    with app.app_context():
        created = worker.process_supplier_invoice_due_reminders(today=today)
        assert created == 2
        notifications = db.session.query(Notification).order_by(Notification.tenant_id).all()
        assert len(notifications) == 2
        assert {n.tenant_id for n in notifications} == {tenant_a.id, tenant_b.id}
        assert {n.user_id for n in notifications} == {admin_a.id, admin_b.id}
        notification_by_message = {n.message: n for n in notifications}
        due_a_notification = next(n for n in notifications if "DUE-A" in (n.message or ""))
        due_b_notification = next(n for n in notifications if "DUE-B" in (n.message or ""))
        assert due_a_notification.action_url.endswith(f"/dashboard/orders/{due_a.order_id}")
        assert due_b_notification.action_url.endswith(f"/dashboard/orders/{due_b.order_id}")
        assert all(n.dedupe_key for n in notifications)
        assert not any("PENDING-A" in (n.message or "") for n in notifications)
        assert not any("PAID-A" in (n.message or "") for n in notifications)

        # A repeated run for the same date must not duplicate notifications.
        assert worker.process_supplier_invoice_due_reminders(today=today) == 0
        assert db.session.query(Notification).count() == 2
        assert len(pushed) == 2
        assert all(payload["url"].endswith("/dashboard/orders/" + payload["url"].rsplit("/", 1)[-1]) for _, payload in pushed)
