import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.import_execution import ImportExecution, EXECUTION_STATUS_COMMITTED


def test_database_rejects_second_committed_execution_for_same_session(logged_in_client_a):
    # Build a real execution through the existing end-to-end import helpers.
    from test_import_execution import _xlsx_bytes, _ready_to_commit

    supplier_id = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Integrity Supplier"}
    ).get_json()["supplier"]["id"]
    session_id = _ready_to_commit(
        logged_in_client_a,
        _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]),
        supplier_id=supplier_id,
    )

    response = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert response.status_code == 201
    execution_id = response.get_json()["execution"]["id"]

    existing = db.session.get(ImportExecution, execution_id)
    assert existing is not None

    duplicate = ImportExecution(
        tenant_id=existing.tenant_id,
        import_session_id=existing.import_session_id,
        import_validation_id=existing.import_validation_id,
        status=EXECUTION_STATUS_COMMITTED,
        snapshot_suppliers_before=existing.snapshot_suppliers_before,
        snapshot_products_before=existing.snapshot_products_before,
        snapshot_offers_before=existing.snapshot_offers_before,
        suppliers_created=0,
        products_created=0,
        products_updated=0,
        offers_created=0,
        created_supplier_ids=[],
        created_product_ids=[],
        created_offer_ids=[],
        price_history=[],
        skipped_rows=[],
        executed_by=existing.executed_by,
    )
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.flush()

    db.session.rollback()
