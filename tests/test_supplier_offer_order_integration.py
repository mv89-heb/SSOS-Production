from app.models.product import Product
from app.models.supplier import Supplier
from app.models.supplier_offer import SupplierProductOffer
from app.models.user import User
from app.services.order_service import OrderService


def _setup(db, tenant_id):
    primary = Supplier(tenant_id=tenant_id, name="Primary Supplier")
    alternate = Supplier(tenant_id=tenant_id, name="Alternate Supplier")
    db.session.add_all([primary, alternate])
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=primary.id,
        name="Milk",
        sku="MILK-OFFER",
        current_price=12,
        currency="ILS",
        unit="יחידה",
        active=True,
    )
    db.session.add(product)
    db.session.flush()
    offer = SupplierProductOffer(
        tenant_id=tenant_id,
        product_id=product.id,
        supplier_id=alternate.id,
        price=8,
        currency="ILS",
        unit="יחידה",
        active=True,
    )
    db.session.add(offer)
    db.session.commit()
    return primary, alternate, product, offer


def test_selected_supplier_offer_is_snapshotted_into_order(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user = db.session.query(User).filter(User.email == "admin@acme.test").one()
    _, alternate, product, offer = _setup(db, tenant_id)

    order = OrderService(tenant_id).create_order(
        user,
        {
            "supplier_id": alternate.id,
            "items": [{"product_id": product.id, "supplier_offer_id": offer.id, "quantity": 10}],
        },
    )
    db.session.flush()

    assert order.supplier_id == alternate.id
    assert len(order.order_items) == 1
    line = order.order_items[0]
    assert line.supplier_offer_id == offer.id
    assert float(line.unit_price) == 8.0
    assert line.offer_snapshot["id"] == offer.id
    assert float(line.offer_snapshot["price"]) == 8.0


def test_order_rejects_offer_from_wrong_supplier(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user = db.session.query(User).filter(User.email == "admin@acme.test").one()
    primary, alternate, product, offer = _setup(db, tenant_id)

    try:
        OrderService(tenant_id).create_order(
            user,
            {
                "supplier_id": primary.id,
                "items": [{"product_id": product.id, "supplier_offer_id": offer.id, "quantity": 1}],
            },
        )
    except Exception as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected supplier-offer mismatch to be rejected")


def test_order_falls_back_to_primary_supplier_price_only_without_offer(db, tenant_a_admin):
    tenant_id = tenant_a_admin[0]["tenant"]["id"]
    user = db.session.query(User).filter(User.email == "admin@acme.test").one()
    primary = Supplier(tenant_id=tenant_id, name="Primary Only")
    db.session.add(primary)
    db.session.flush()
    product = Product(
        tenant_id=tenant_id,
        supplier_id=primary.id,
        name="Bread",
        sku="BREAD-PRIMARY",
        current_price=5.5,
        currency="ILS",
        active=True,
    )
    db.session.add(product)
    db.session.commit()

    order = OrderService(tenant_id).create_order(
        user,
        {"supplier_id": primary.id, "items": [{"product_id": product.id, "quantity": 2}]},
    )
    assert float(order.order_items[0].unit_price) == 5.5
    assert order.order_items[0].supplier_offer_id is None
