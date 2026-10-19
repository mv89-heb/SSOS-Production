from app.routes.supplier_invoices import _ALLOWED_ATTACHMENTS


def test_invoice_attachment_signatures_accept_real_pdf_jpeg_and_png_headers():
    assert _ALLOWED_ATTACHMENTS[".pdf"][1](b"%PDF-1.7 sample")
    assert _ALLOWED_ATTACHMENTS[".jpg"][1](b"\xff\xd8\xff\xe0sample")
    assert _ALLOWED_ATTACHMENTS[".jpeg"][1](b"\xff\xd8\xff\xe1sample")
    assert _ALLOWED_ATTACHMENTS[".png"][1](b"\x89PNG\r\n\x1a\nsample")


def test_invoice_attachment_signatures_reject_text_disguised_as_images():
    assert not _ALLOWED_ATTACHMENTS[".jpg"][1](b"\\xff\\xd8\\xff")
    assert not _ALLOWED_ATTACHMENTS[".jpeg"][1](b"not a jpeg")
    assert not _ALLOWED_ATTACHMENTS[".png"][1](b"\\x89PNG\\r\\n\\x1a\\n")
