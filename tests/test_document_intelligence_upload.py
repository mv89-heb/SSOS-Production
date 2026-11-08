from io import BytesIO
from types import SimpleNamespace

from app.models.document_analysis import DocumentAnalysis
from app.models.user import User
from app.services.document_intelligence_service import DocumentIntelligenceService


def test_svg_upload_accepts_browser_octet_stream(logged_in_client_a, monkeypatch):
    def fake_create_analysis(self, filename, storage_path, mime_type):
        assert filename == "invoice.svg"
        assert mime_type == "image/svg+xml"
        return SimpleNamespace(to_dict=lambda: {"filename": filename, "mime_type": mime_type})

    monkeypatch.setattr(
        "app.routes.document_intelligence.DocumentIntelligenceService.create_analysis",
        fake_create_analysis,
    )

    response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"<svg><text>Invoice 123</text></svg>"), "invoice.svg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["analysis"]["mime_type"] == "image/svg+xml"


def test_analyze_deletes_temporary_document(logged_in_client_a, db, monkeypatch):
    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            assert path
            assert progress_callback is not None
            return SimpleNamespace(
                success=True,
                data={"document_type": "INVOICE", "items": [{"description": "Milk", "unit_price": 10}]},
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload_response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake pdf contents"), "invoice.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201, upload_response.get_json()

    analysis_id = upload_response.get_json()["analysis"]["id"]
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row is not None
    temp_path = row.storage_path
    assert temp_path

    analyze_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/analyze")
    assert analyze_response.status_code == 200, analyze_response.get_json()
    assert analyze_response.get_json()["analysis"]["status"] == "ANALYZED"

    db.session.expire_all()
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row.storage_path is None
    assert not __import__("os").path.exists(temp_path)



def test_rematch_refreshes_saved_analysis_without_calling_gemini(logged_in_client_a, db, monkeypatch):
    calls = {"generate": 0}

    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            calls["generate"] += 1
            return SimpleNamespace(
                success=True,
                data={
                    "document_type": "PRICE_LIST",
                    "supplier": {"name": "Test supplier"},
                    "items": [{"description": "צלחות קטן קרם", "unit_price": 7.5}],
                },
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload_response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake pdf contents"), "price-list.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201, upload_response.get_json()
    analysis_id = upload_response.get_json()["analysis"]["id"]

    analyze_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/analyze")
    assert analyze_response.status_code == 200, analyze_response.get_json()
    assert analyze_response.get_json()["analysis"]["status"] == "ANALYZED"
    assert calls["generate"] == 1

    db.session.expire_all()
    row = db.session.get(DocumentAnalysis, analysis_id)
    assert row.storage_path is None

    rematch_response = logged_in_client_a.post(f"/api/document-intelligence/{analysis_id}/rematch")
    assert rematch_response.status_code == 200, rematch_response.get_json()
    refreshed = rematch_response.get_json()["analysis"]
    assert refreshed["status"] == "ANALYZED"
    assert refreshed["extracted_data"]["matching_version"] == "deterministic-v2-multi-supplier"
    assert calls["generate"] == 1


def test_document_analysis_does_not_mutate_procurement_or_inventory(
    logged_in_client_a, db, make_order, monkeypatch
):
    from app.models.inventory_movement import InventoryMovement
    from app.models.order import Order
    from app.models.price_history import PriceHistory
    from app.models.product import Product
    from app.models.receipt import Receipt
    from app.models.receipt_item import ReceiptItem
    from app.models.supplier import Supplier
    from app.models.supplier_invoice import SupplierInvoice
    from app.models.supplier_offer import SupplierProductOffer

    order_response, supplier_id, product_id = make_order(logged_in_client_a)
    assert order_response.status_code == 201, order_response.get_json()
    product = db.session.get(Product, product_id)
    product.current_stock = 17
    db.session.commit()

    models = (
        Supplier,
        Product,
        SupplierProductOffer,
        PriceHistory,
        Order,
        Receipt,
        ReceiptItem,
        SupplierInvoice,
        InventoryMovement,
    )

    def business_snapshot():
        db.session.expire_all()
        current_product = db.session.get(Product, product_id)
        return {
            "counts": {model.__name__: db.session.query(model).count() for model in models},
            "product": {
                "supplier_id": current_product.supplier_id,
                "current_price": str(current_product.current_price),
                "current_stock": current_product.current_stock,
                "unit": current_product.unit,
                "units_per_carton": current_product.units_per_carton,
            },
            "supplier_id": supplier_id,
        }

    before = business_snapshot()

    class FakeAI:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def generate_structured_from_file(path, schema, system_instruction=None, progress_callback=None):
            assert path
            return SimpleNamespace(
                success=True,
                data={
                    "document_type": "DELIVERY_NOTE",
                    "document_number": "DN-DRY-RUN-001",
                    "supplier": {"name": "Test Supplier"},
                    "items": [{
                        "description": "Test Product",
                        "quantity": 1,
                        "unit": "יחידה",
                        "unit_price": 10,
                    }],
                },
                provider="test",
                model="test-model",
                error=None,
            )

    monkeypatch.setattr(
        "app.services.document_intelligence_service.AIService.from_config",
        lambda config: FakeAI(),
    )

    upload_response = logged_in_client_a.post(
        "/api/document-intelligence/upload",
        data={"file": (BytesIO(b"fake delivery note"), "delivery-note.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201, upload_response.get_json()
    analysis_id = upload_response.get_json()["analysis"]["id"]

    analyze_response = logged_in_client_a.post(
        f"/api/document-intelligence/{analysis_id}/analyze"
    )
    assert analyze_response.status_code == 200, analyze_response.get_json()
    assert analyze_response.get_json()["analysis"]["status"] == "ANALYZED"

    after = business_snapshot()
    assert after == before


def test_bulk_rematch_refreshes_applied_and_unapplied_without_ai_or_procurement_changes(
    logged_in_client_a, db, monkeypatch
):
    user = User.query.filter_by(email="admin@acme.test").first()
    assert user is not None
    rows = []
    for status in ("ANALYZED", "APPLIED"):
        row = DocumentAnalysis(
            tenant_id=user.tenant_id,
            uploaded_by=user.id,
            filename=f"{status.lower()}.pdf",
            mime_type="application/pdf",
            document_type="PRICE_LIST",
            status=status,
            extracted_data={"document_type": "PRICE_LIST", "items": [{"description": "מארז 50 יחידות"}]},
        )
        db.session.add(row)
        rows.append(row)
    db.session.commit()

    calls = {"enrich": 0}

    def fake_enrich(self, data):
        calls["enrich"] += 1
        data["items"][0]["derived_packaging"] = {
            "declared_pack_count": 50,
            "declared_pack_count_unit": "יחידות",
        }
        return data

    monkeypatch.setattr(
        "app.services.document_intelligence_service.ProductMatchingService.enrich_document",
        fake_enrich,
    )

    response = logged_in_client_a.post("/api/document-intelligence/rematch-all", json={"limit": 100})
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["eligible"] == 2
    assert len(payload["refreshed"]) == 2
    assert payload["failed_ids"] == []
    assert calls["enrich"] == 2

    db.session.expire_all()
    for row in rows:
        refreshed = db.session.get(DocumentAnalysis, row.id)
        assert refreshed.extracted_data["items"][0]["derived_packaging"]["declared_pack_count"] == 50
