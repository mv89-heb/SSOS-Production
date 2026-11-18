from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.order import Order, STATUS_APPROVED, STATUS_DRAFT, STATUS_SENT
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoicePayment


def _create_order(client, make_order, db, *, status, total, created_at, currency="ILS"):
    response, _, _ = make_order(client, quantity=1, price=float(total))
    assert response.status_code == 201, response.get_json()
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = status
    order.final_total = Decimal(str(total))
    order.currency = currency
    order.created_at = created_at
    db.session.commit()
    return order


def test_spend_summary_separates_ordered_invoiced_and_paid_by_currency_and_tenant(
    logged_in_client_a, logged_in_client_b, make_order, db
):
    nov_5 = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
    nov_7 = datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc)
    order_a = _create_order(
        logged_in_client_a, make_order, db, status=STATUS_APPROVED,
        total="120.50", created_at=nov_5, currency="ILS",
    )
    _create_order(
        logged_in_client_a, make_order, db, status=STATUS_DRAFT,
        total="999", created_at=nov_5, currency="ILS",
    )
    _create_order(
        logged_in_client_a, make_order, db, status=STATUS_SENT,
        total="50", created_at=nov_7, currency="USD",
    )
    _create_order(
        logged_in_client_b, make_order, db, status=STATUS_APPROVED,
        total="777", created_at=nov_5, currency="ILS",
    )

    invoice = SupplierInvoice(
        tenant_id=order_a.tenant_id,
        order_id=order_a.id,
        supplier_id=order_a.supplier_id,
        invoice_number="ANALYTICS-INV-001",
        invoice_date=date(2026, 11, 6),
        due_date=date(2026, 12, 6),
        amount=Decimal("100.25"),
        currency="ILS",
    )
    db.session.add(invoice)
    db.session.flush()
    db.session.add(SupplierInvoicePayment(
        tenant_id=order_a.tenant_id,
        invoice_id=invoice.id,
        amount=Decimal("40.00"),
        payment_date=date(2026, 11, 8),
        reference="BANK-REF-001",
    ))
    db.session.commit()

    response = logged_in_client_a.get(
        "/api/procurement-analytics/spend?start_date=2026-11-01&end_date=2026-11-30"
    )
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["ordered"]["totals_by_currency"] == {"ILS": 120.5, "USD": 50.0}
    assert result["invoiced"]["totals_by_currency"] == {"ILS": 100.25}
    assert result["paid"]["totals_by_currency"] == {"ILS": 40.0}
    assert all(
        document["amount"] != 777
        for group in result["ordered"]["by_supplier"]
        for document in group["documents"]
    )
    assert all(
        document["amount"] != 999
        for group in result["ordered"]["by_supplier"]
        for document in group["documents"]
    )
    assert result["definitions"]["currency"].startswith("Totals are separated")


def test_spend_summary_rejects_invalid_and_oversized_date_ranges(logged_in_client_a):
    invalid = logged_in_client_a.get(
        "/api/procurement-analytics/spend?start_date=not-a-date&end_date=2026-11-30"
    )
    assert invalid.status_code == 400
    oversized = logged_in_client_a.get(
        "/api/procurement-analytics/spend?start_date=2020-01-01&end_date=2026-11-30"
    )
    assert oversized.status_code == 400
