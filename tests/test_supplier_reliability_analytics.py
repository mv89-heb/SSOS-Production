from datetime import date, datetime, timezone

from app.models.order import Order, STATUS_COMPLETED
from app.models.order_item import OrderItem
from app.models.receipt import Receipt, RECEIPT_POSTED
from app.models.receipt_item import ReceiptItem
from app.models.supplier_credit_adjustment import SupplierCreditAdjustment, CREDIT_ADJUSTMENT_ACTIVE, CREDIT_ADJUSTMENT_VOIDED


def test_supplier_reliability_reports_late_delivery_shortage_and_sample_size_without_cross_tenant_data(
    logged_in_client_a, logged_in_client_b, make_order, db
):
    response, _, _ = make_order(
        logged_in_client_a, quantity=5, price=10.0,
        supplier_name="Reliability Supplier", product_name="Reliability Product",
        sku="RELIABILITY-001",
    )
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_COMPLETED
    order.planned_order_date = date(2026, 11, 5)
    order.created_at = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
    order_item = db.session.query(OrderItem).filter_by(order_id=order.id).one()
    receipt = Receipt(
        tenant_id=order.tenant_id,
        order_id=order.id,
        receipt_number="RELIABILITY-RECEIPT-001",
        status=RECEIPT_POSTED,
        received_by=order.user_id,
        received_at=datetime(2026, 11, 7, 10, 0, tzinfo=timezone.utc),
    )
    db.session.add(receipt)
    db.session.flush()
    db.session.add(ReceiptItem(
        tenant_id=order.tenant_id,
        receipt_id=receipt.id,
        order_item_id=order_item.id,
        quantity=5,
        damaged_quantity=1,
        damage_notes="מוצר סדוק",
    ))
    db.session.add(SupplierCreditAdjustment(
        tenant_id=order.tenant_id,
        order_id=order.id,
        supplier_id=order.supplier_id,
        reference_number="RELIABILITY-CREDIT-ACTIVE",
        adjustment_type="credit_note",
        adjustment_date=date(2026, 11, 12),
        amount=10,
        currency="ILS",
        status=CREDIT_ADJUSTMENT_ACTIVE,
    ))
    db.session.add(SupplierCreditAdjustment(
        tenant_id=order.tenant_id,
        order_id=order.id,
        supplier_id=order.supplier_id,
        reference_number="RELIABILITY-CREDIT-VOIDED",
        adjustment_type="credit_note",
        adjustment_date=date(2026, 11, 13),
        amount=5,
        currency="ILS",
        status=CREDIT_ADJUSTMENT_VOIDED,
        void_reason="בדיקת החרגה",
    ))

    other_response, _, _ = make_order(
        logged_in_client_b, quantity=5, price=10.0,
        supplier_name="Other Tenant Supplier", product_name="Other Tenant Product",
        sku="RELIABILITY-OTHER",
    )
    other_order = db.session.get(Order, other_response.get_json()["order"]["id"])
    other_order.status = STATUS_COMPLETED
    other_order.planned_order_date = date(2026, 11, 1)
    other_order.created_at = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
    db.session.commit()

    response = logged_in_client_a.get(
        "/api/procurement-analytics/spend?start_date=2026-11-01&end_date=2026-11-30"
    )
    assert response.status_code == 200, response.get_json()
    reliability = response.get_json()["supplier_reliability"]
    assert len(reliability) == 1
    metric = reliability[0]
    assert metric["supplier_name"] == "Reliability Supplier"
    assert metric["completed_orders"] == 1
    assert metric["delivery_sample_size"] == 1
    assert metric["late_orders"] == 1
    assert metric["late_rate_percent"] == 100.0
    assert metric["shortage_sample_size"] == 1
    assert metric["short_orders"] == 1
    assert metric["shortage_rate_percent"] == 100.0
    assert metric["credit_adjustment_data_available"] is True
    assert metric["credit_adjustment_frequency"] == 100.0
    assert metric["credit_adjustment_count"] == 1
    assert metric["orders_with_credit_adjustments"] == 1


def test_supplier_credit_adjustment_frequency_is_zero_when_no_active_records(
    logged_in_client_a, make_order, db
):
    response, _, _ = make_order(
        logged_in_client_a,
        supplier_name="No Credit Supplier",
        sku="NO-CREDIT-001",
    )
    order = db.session.get(Order, response.get_json()["order"]["id"])
    order.status = STATUS_COMPLETED
    order.created_at = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
    db.session.commit()

    result = logged_in_client_a.get(
        "/api/procurement-analytics/spend?start_date=2026-11-01&end_date=2026-11-30"
    )
    assert result.status_code == 200, result.get_json()
    metric = next(
        row for row in result.get_json()["supplier_reliability"]
        if row["supplier_name"] == "No Credit Supplier"
    )
    assert metric["credit_adjustment_data_available"] is True
    assert metric["credit_adjustment_frequency"] == 0.0
    assert metric["credit_adjustment_count"] == 0
    assert metric["orders_with_credit_adjustments"] == 0
