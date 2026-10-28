"""Notify authorized users about approved supplier invoices nearing or past due date.

This worker only creates notifications; it never approves invoices or records payments.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models.notification import Notification, STATUS_UNREAD
from app.models.supplier_invoice import SupplierInvoice, INVOICE_APPROVAL_APPROVED
from app.models.tenant import Tenant
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER
from app.services.web_push_service import send_to_user


DUE_SOON_DAYS = 3
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def process_supplier_invoice_due_reminders(today=None) -> int:
    today = today or datetime.now(ISRAEL_TZ).date()
    due_soon_until = today + timedelta(days=DUE_SOON_DAYS)
    invoices = db.session.scalars(
        select(SupplierInvoice)
        .join(Tenant, Tenant.id == SupplierInvoice.tenant_id)
        .where(
            Tenant.active.is_(True),
            SupplierInvoice.approval_status == INVOICE_APPROVAL_APPROVED,
            SupplierInvoice.due_date.is_not(None),
            SupplierInvoice.due_date <= due_soon_until,
        )
        .order_by(SupplierInvoice.due_date.asc(), SupplierInvoice.id.asc())
    ).all()

    created = 0
    push_events = []
    for invoice in invoices:
        balance = invoice.amount - invoice.paid_amount
        if balance <= 0:
            continue

        overdue = invoice.due_date < today
        if overdue:
            occurrence = today.isoformat()
            dedupe_prefix = f"supplier-invoice-overdue:{invoice.id}:{occurrence}"
            title = "🔴 חשבונית ספק באיחור"
            days = (today - invoice.due_date).days
            timing = f"באיחור של {days} ימים"
        else:
            occurrence = invoice.due_date.isoformat()
            dedupe_prefix = f"supplier-invoice-due-soon:{invoice.id}:{occurrence}"
            title = "🔔 חשבונית ספק מתקרבת לתשלום"
            days = (invoice.due_date - today).days
            timing = "מועד התשלום היום" if days == 0 else f"מועד התשלום בעוד {days} ימים"

        users = db.session.scalars(
            select(User).where(
                User.tenant_id == invoice.tenant_id,
                User.active.is_(True),
                User.role.in_((ROLE_ADMIN, ROLE_MANAGER)),
            )
        ).all()
        for user in users:
            # Per-user keys prevent duplicates while allowing every authorized
            # manager/admin in the tenant to receive the reminder.
            dedupe_key = f"{dedupe_prefix}:user:{user.id}"
            exists = db.session.scalar(
                select(Notification.id).where(Notification.dedupe_key == dedupe_key).limit(1)
            )
            if exists is not None:
                continue

            supplier_name = invoice.supplier.name if invoice.supplier else f"#{invoice.supplier_id}"
            message = (
                f"חשבונית {invoice.invoice_number} של ספק {supplier_name}: {timing}. "
                f"יתרה לתשלום: {balance:.2f} {invoice.currency}."
            )
            action_url = current_app.config.get("FRONTEND_PUBLIC_URL", "").rstrip("/") + "/dashboard/supplier-invoices"
            notification = Notification(
                tenant_id=invoice.tenant_id,
                user_id=user.id,
                title=title,
                message=message,
                status=STATUS_UNREAD,
                action_url=action_url,
                notification_type="supplier_invoice_overdue" if overdue else "supplier_invoice_due_soon",
                dedupe_key=dedupe_key,
            )
            db.session.add(notification)
            db.session.flush()
            push_events.append((user.id, {
                "title": title,
                "body": message,
                "url": action_url,
                "notification_id": notification.id,
                "type": notification.notification_type,
            }))
            created += 1

    db.session.commit()
    for user_id, payload in push_events:
        try:
            send_to_user(user_id, payload)
        except Exception:
            current_app.logger.exception(
                "Supplier invoice due reminder push delivery failed for user %s", user_id
            )
    return created


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print(f"Created {process_supplier_invoice_due_reminders()} supplier invoice due reminder(s).")
