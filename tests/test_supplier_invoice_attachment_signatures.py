import io

from app.models.supplier_invoice import SupplierInvoice


def test_supplier_invoice_model_does_not_store_original_file_bytes():
    assert not hasattr(SupplierInvoice, "attachment_data")


def test_original_invoice_file_upload_and_download_are_disabled(logged_in_client_a, make_order):
    order_response, _, _ = make_order(logged_in_client_a)
    assert order_response.status_code == 201, order_response.get_json()
    order_id = order_response.get_json()["order"]["id"]

    invoice_response = logged_in_client_a.post(
        f"/api/orders/{order_id}/invoices",
        json={"invoice_number": "HIST-TEST-1", "amount": 123.45},
    )
    assert invoice_response.status_code == 201, invoice_response.get_json()
    invoice_id = invoice_response.get_json()["invoice"]["id"]

    upload_response = logged_in_client_a.post(
        f"/api/supplier-invoices/{invoice_id}/attachment",
        data={"file": (io.BytesIO(b"%PDF-1.7 sample"), "invoice.pdf")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 410
    assert upload_response.get_json()["error"] == "original_file_storage_disabled"

    download_response = logged_in_client_a.get(f"/api/supplier-invoices/{invoice_id}/attachment")
    assert download_response.status_code == 410
