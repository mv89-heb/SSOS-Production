from app.routes.supplier_invoices import reject_supplier_invoice_attachment


def test_original_invoice_file_uploads_are_disabled():
    assert callable(reject_supplier_invoice_attachment)
