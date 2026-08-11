import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.import_execution import ImportExecution, EXECUTION_STATUS_COMMITTED


def test_database_rejects_second_committed_execution_for_same_session(logged_in_client_a):
    data = (
        b"\x50\x4b\x03\x04"  # not used; endpoint setup is replaced below
    )

    # Build a real execution through the existing end-to-end import test flow
    # without duplicating the large XLSX helper here.
    from test_import_execution import _xlsx_bytes, _ready_to_commit

    session_id = _ready_to_commit(
        logged_in_client_a,
        _xlsx_bytes([["\u05de\u05d5\u05e6\u05e8", "\u05de\u05d7\u05d9\u05e8"], ["X", "1"]]),
        supplier_id=logged_in_client_a.post(
            "/api/catalog/suppliers", json={"name": "Integrity Supplier"}
        ).get_json()["supplier"]["id"],
    )
    response = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert response.status_code == 201

    execution = response.get_json()["execution"]

    duplicate = ImportExecution(
        tenant_id=1,
        import_session_id=session_id,
        import_validation_id=execution["import_validation_id"],
        status=EXECUTION_STATUS_COMMITTED,
        snapshot_suppliers_before=0,
        snapshot_products_before=0,
        snapshot_offers_before=0,
        suppliers_created=0,
        products_created=0,
        products_updated=0,
        offers_created=0,
        created_supplier_ids=[],
        created_product_ids=[],
        created_offer_ids=[],
        price_history=[],
        skipped_rows=[],
        executed_by=1,
    )
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.flush()

    db.session.rollback()
