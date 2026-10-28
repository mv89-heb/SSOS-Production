from decimal import Decimal

from app.routes.historical_document_import import _date, _decimal, _norm, _supplier_from_extraction


def test_historical_import_date_and_decimal_parsing_preserve_unknown_values():
    assert _date("2024-05-17") is not None
    assert _date("not-a-date") is None
    assert _date(None) is None
    assert _decimal("125.40") == Decimal("125.40")
    assert _decimal(None) is None
    assert _decimal("not-a-price") is None


def test_historical_import_supplier_matching_does_not_invent_supplier():
    name, supplier_id, multi_supplier = _supplier_from_extraction({
        "supplier": {"name": "ספק לדוגמה"},
        "supplier_matching": {"supplier_id": 17, "decision": "AUTO_MATCH"},
        "supplier_sections": [{"supplier": {"name": "ספק לדוגמה"}, "supplier_matching": {"supplier_id": 17, "decision": "AUTO_MATCH"}}],
    })
    assert name == "ספק לדוגמה"
    assert supplier_id == 17
    assert multi_supplier is False

    name, supplier_id, multi_supplier = _supplier_from_extraction({
        "supplier": {},
        "supplier_sections": [
            {"supplier": {"name": "ספק א"}},
            {"supplier": {"name": "ספק ב"}},
        ],
    })
    assert name is None
    assert supplier_id is None
    assert multi_supplier is True


def test_historical_import_supplier_normalization_is_deterministic():
    assert _norm("  ספק   א בע״מ ") == "ספק א בע״מ"



def test_historical_import_finalize_is_idempotent_and_does_not_create_operational_records(
    logged_in_client_a, db, monkeypatch
):
    from io import BytesIO
    from types import SimpleNamespace

    from sqlalchemy import select, func

    from app.models.document_analysis import DocumentAnalysis
    from app.models.historical_document_import import HistoricalPurchaseOrder
    from app.models.order import Order
    from app.models.receipt import Receipt
    from app.models.supplier_invoice import SupplierInvoice

    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            return SimpleNamespace(
                success=True,
                data={
                    "document_type": "INVOICE",
                    "supplier": {"name": "ספק היסטורי לדוגמה"},
                    "document_number": "HIST-INV-2024-001",
                    "document_date": "2024-05-12",
                    "currency": "ILS",
                    "totals": {"total": 125.50},
                    "items": [{"description": "מוצר היסטורי", "quantity": 5, "unit_price": 25.10}],
                },
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake historical invoice"), "historical-invoice.pdf")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201, upload.get_json()
    analysis_id = upload.get_json()["analysis"]["id"]
    analyzed = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/analyze")
    assert analyzed.status_code == 200, analyzed.get_json()

    batch_response = logged_in_client_a.post(
        "/api/historical-document-import/batches", json={"name": "בדיקת ייבוא היסטורי"}
    )
    assert batch_response.status_code == 201, batch_response.get_json()
    batch_id = batch_response.get_json()["batch"]["id"]

    add_response = logged_in_client_a.post(
        f"/api/historical-document-import/batches/{batch_id}/documents",
        json={"analysis_id": analysis_id, "order_reference": "OLD-PO-2024-001"},
    )
    assert add_response.status_code == 201, add_response.get_json()
    document = add_response.get_json()["document"]
    assert document["needs_review"] is False

    first_finalize = logged_in_client_a.post(
        f"/api/historical-document-import/batches/{batch_id}/finalize", json={}
    )
    assert first_finalize.status_code == 200, first_finalize.get_json()
    assert len(first_finalize.get_json()["orders"]) == 1

    second_finalize = logged_in_client_a.post(
        f"/api/historical-document-import/batches/{batch_id}/finalize", json={}
    )
    assert second_finalize.status_code == 200, second_finalize.get_json()
    assert second_finalize.get_json()["already_finalized"] is True
    assert len(second_finalize.get_json()["batch"]["orders"]) == 1

    assert db.session.scalar(select(func.count()).select_from(Order)) == 0
    assert db.session.scalar(select(func.count()).select_from(Receipt)) == 0
    assert db.session.scalar(select(func.count()).select_from(SupplierInvoice)) == 0
    assert db.session.scalar(select(func.count()).select_from(HistoricalPurchaseOrder)) == 1

    db.session.expire_all()
    analysis = db.session.get(DocumentAnalysis, analysis_id)
    assert analysis is not None
    assert analysis.storage_path is None


def test_historical_import_batch_is_tenant_scoped(logged_in_client_a, logged_in_client_b):
    created = logged_in_client_a.post(
        "/api/historical-document-import/batches", json={"name": "Private batch"}
    )
    assert created.status_code == 201, created.get_json()
    batch_id = created.get_json()["batch"]["id"]

    hidden = logged_in_client_b.get(f"/api/historical-document-import/batches/{batch_id}")
    assert hidden.status_code == 404
