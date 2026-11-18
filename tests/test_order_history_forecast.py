from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.order import Order, STATUS_DRAFT, STATUS_SENT, STATUS_SUBMITTED
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.order_history_forecast_service import OrderHistoryForecastService


def test_supplier_forecast_uses_issued_orders_and_excludes_drafts(db, tenant_a_admin, monkeypatch):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="History Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="History Product",
        sku="HISTORY-001",
        unit="יחידה",
        current_stock=9999,
        min_stock=1,
        active=True,
    )
    db.session.add(product)
    db.session.flush()

    # Four consecutive weeks from the cycle anchor: the fourth week is boosted.
    order_dates = [
        date(2020, 1, 6),
        date(2020, 1, 13),
        date(2020, 1, 20),
        date(2020, 1, 27),
    ]
    for index, order_date in enumerate(order_dates):
        order = Order(
            tenant_id=tenant_id,
            user_id=tenant_a_admin[0]["user"]["id"],
            supplier_id=supplier.id,
            order_number=f"HIST-{index}",
            supplier_name=supplier.name,
            status=STATUS_SENT,
            planned_order_date=None if index == 3 else order_date,
            created_at=datetime.combine(order_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=Decimal("10"),
            unit_price=Decimal("1"),
            currency="ILS",
            product_snapshot={"unit": "יחידה"},
        ))

    submitted = Order(
        tenant_id=tenant_id,
        user_id=tenant_a_admin[0]["user"]["id"],
        supplier_id=supplier.id,
        order_number="HIST-SUBMITTED",
        supplier_name=supplier.name,
        status=STATUS_SUBMITTED,
        planned_order_date=date(2020, 1, 13),
        created_at=datetime(2020, 1, 13, tzinfo=timezone.utc),
    )
    db.session.add(submitted)
    db.session.flush()
    db.session.add(OrderItem(
        tenant_id=tenant_id,
        order_id=submitted.id,
        product_id=product.id,
        quantity=Decimal("300"),
        unit_price=Decimal("1"),
        currency="ILS",
    ))

    draft = Order(
        tenant_id=tenant_id,
        user_id=tenant_a_admin[0]["user"]["id"],
        supplier_id=supplier.id,
        order_number="HIST-DRAFT",
        supplier_name=supplier.name,
        status=STATUS_DRAFT,
        planned_order_date=date(2020, 1, 13),
        created_at=datetime(2020, 1, 13, tzinfo=timezone.utc),
    )
    db.session.add(draft)
    db.session.flush()
    db.session.add(OrderItem(
        tenant_id=tenant_id,
        order_id=draft.id,
        product_id=product.id,
        quantity=Decimal("500"),
        unit_price=Decimal("1"),
        currency="ILS",
    ))
    db.session.commit()

    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "4")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "1")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "1.4")

    result = OrderHistoryForecastService(tenant_id).supplier_forecast(
        supplier.id,
        start_date=date(2020, 1, 6),
        end_date=date(2020, 2, 2),
        target_date=date(2020, 1, 27),
    )

    assert result["order_count"] == 4
    assert len(result["products"]) == 1
    forecast = result["products"][0]
    assert forecast["normal_weekly_average"] == 10
    assert forecast["boosted_weekly_forecast"] == 14
    assert forecast["recommended_quantity"] == 14
    assert forecast["data_ready"] is True
    assert forecast["order_count"] == 4
    # Stale stock values must not affect an order-history forecast.
    assert forecast["recommended_quantity"] != 0


def test_supplier_forecast_is_tenant_scoped_and_does_not_infer_from_stock(
    db, tenant_a_admin, tenant_b_admin
):
    tenant_a = tenant_a_admin[0]["tenant"]["id"]
    tenant_b = tenant_b_admin[0]["tenant"]["id"]
    supplier_b = Supplier(tenant_id=tenant_b, name="Other Tenant Supplier")
    db.session.add(supplier_b)
    db.session.commit()

    result = OrderHistoryForecastService(tenant_a).supplier_forecast(
        supplier_b.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 11, 18),
    )
    assert result["products"] == []
    assert result["order_count"] == 0


def test_supplier_forecast_normalizes_cartons_to_stock_units(db, tenant_a_admin, monkeypatch):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Unit Conversion Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="Mixed Unit Product",
        sku="HISTORY-MIXED-001",
        unit="יחידה",
        units_per_carton=12,
        current_stock=0,
        active=True,
    )
    db.session.add(product)
    db.session.flush()

    order_rows = [
        (date(2020, 1, 6), Decimal("2"), {
            "unit": "קרטון", "quantity_unit": "carton",
            "stock_unit": "יחידה", "units_per_carton": 12,
        }),
        (date(2020, 1, 13), Decimal("36"), {
            "unit": "יחידה", "quantity_unit": None,
            "stock_unit": "יחידה", "units_per_carton": 12,
        }),
    ]
    for index, (order_date, quantity, snapshot) in enumerate(order_rows):
        order = Order(
            tenant_id=tenant_id,
            user_id=tenant_a_admin[0]["user"]["id"],
            supplier_id=supplier.id,
            order_number=f"MIXED-{index}",
            supplier_name=supplier.name,
            status=STATUS_SENT,
            planned_order_date=order_date,
            created_at=datetime.combine(order_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=Decimal("1"),
            currency="ILS",
            product_snapshot=snapshot,
        ))
    db.session.commit()

    monkeypatch.setenv("SSOS_BOOSTED_CYCLE_WEEKS", "4")
    monkeypatch.setenv("SSOS_BOOSTED_WEEKS", "1")
    monkeypatch.setenv("SSOS_BOOSTED_WEEK_MULTIPLIER", "1.4")

    result = OrderHistoryForecastService(tenant_id).supplier_forecast(
        supplier.id,
        start_date=date(2020, 1, 6),
        end_date=date(2020, 2, 2),
        target_date=date(2020, 1, 27),
    )

    forecast = result["products"][0]
    # Two cartons × 12 pieces plus 36 pieces, averaged across three normal weeks.
    assert forecast["unit"] == "יחידה"
    assert forecast["normal_weekly_average"] == 20
    assert forecast["recommended_quantity"] == 28
    assert forecast["data_ready"] is True
    assert forecast["unit_conversion_issues"] == 0


def test_supplier_forecast_blocks_carton_rows_without_pack_snapshot(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Missing Pack Supplier")
    db.session.add(supplier)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=supplier.id,
        name="Unknown Pack Product",
        sku="HISTORY-PACK-001",
        unit="יחידה",
        units_per_carton=None,
        current_stock=0,
        active=True,
    )
    db.session.add(product)
    db.session.flush()

    for index, order_date in enumerate((date(2020, 1, 6), date(2020, 1, 13))):
        order = Order(
            tenant_id=tenant_id,
            user_id=tenant_a_admin[0]["user"]["id"],
            supplier_id=supplier.id,
            order_number=f"PACK-{index}",
            supplier_name=supplier.name,
            status=STATUS_SENT,
            planned_order_date=order_date,
            created_at=datetime.combine(order_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            tenant_id=tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=Decimal("2"),
            unit_price=Decimal("1"),
            currency="ILS",
            product_snapshot={
                "unit": "קרטון", "quantity_unit": "carton",
                "stock_unit": "יחידה", "units_per_carton": None,
            },
        ))
    db.session.commit()

    result = OrderHistoryForecastService(tenant_id).supplier_forecast(
        supplier.id,
        start_date=date(2020, 1, 6),
        end_date=date(2020, 2, 2),
        target_date=date(2020, 1, 27),
    )

    forecast = result["products"][0]
    assert forecast["data_ready"] is False
    assert forecast["recommended_quantity"] == 0
    assert forecast["unit_conversion_issues"] == 2
    assert forecast["readiness_reason"] == "unit_conversion_requires_review"
