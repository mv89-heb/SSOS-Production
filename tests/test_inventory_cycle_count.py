from app.models.inventory_movement import InventoryMovement, MOVEMENT_COUNT
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_calendar_service import InventoryCalendarService


def test_weekly_cycle_assigns_subset_and_prioritizes_zero_stock(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    supplier = Supplier(tenant_id=tenant_id, name="Cycle Count Supplier")
    db.session.add(supplier)
    db.session.flush()
    products = []
    for index in range(12):
        product = Product(
            tenant_id=tenant_id,
            supplier_id=supplier.id,
            name=f"Cycle Product {index}",
            current_price=10,
            currency="ILS",
            active=True,
            current_stock=100,
            min_stock=10,
        )
        db.session.add(product)
        products.append(product)
    db.session.flush()
    priority = products[0]
    priority.current_stock = 0
    db.session.commit()

    status = InventoryCalendarService(tenant_id).count_status()

    assert status["active_products"] == 12
    assert status["assigned_products"] < status["active_products"]
    assert priority.id in status["due_product_ids"]
    assert status["rotation_cycle_weeks"] == 4
    assert status["due"] is True
