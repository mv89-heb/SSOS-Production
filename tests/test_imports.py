import io
import csv
import openpyxl


def _xlsx_bytes(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _csv_bytes(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_upload_xlsx_stages_raw_rows(logged_in_client_a):
    data = _xlsx_bytes([
        ["מוצר", "יחידה", "מחיר"],
        ["בורקס גבינה", "קילו", "20.85"],
        ["אצבעות גבינה", "קילו", "25"],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "test.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    session = resp.get_json()["session"]
    assert session["status"] == "UPLOADED"
    assert session["row_count"] == 2
    assert session["column_headers"] == ["מוצר", "יחידה", "מחיר"]

    rows_resp = logged_in_client_a.get(f"/api/imports/{session['id']}/rows")
    assert rows_resp.status_code == 200
    rows = rows_resp.get_json()["rows"]
    assert len(rows) == 2
    assert rows[0]["raw_data"] == {"מוצר": "בורקס גבינה", "יחידה": "קילו", "מחיר": "20.85"}
    assert rows[0]["row_number"] == 1
    assert rows[1]["raw_data"]["מוצר"] == "אצבעות גבינה"


def test_upload_csv_stages_raw_rows(logged_in_client_a):
    data = _csv_bytes([
        ["Product", "Price"],
        ["Cola 1.5L", "6.5"],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "test.csv", "text/csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    session = resp.get_json()["session"]
    assert session["row_count"] == 1

    rows = logged_in_client_a.get(f"/api/imports/{session['id']}/rows").get_json()["rows"]
    assert rows[0]["raw_data"] == {"Product": "Cola 1.5L", "Price": "6.5"}


def test_upload_source_data_is_not_modified(logged_in_client_a):
    """אין לשנות את המקור — every cell value must survive verbatim (as a
    string), including values that look numeric or have odd whitespace."""
    data = _xlsx_bytes([
        ["מוצר", "מחיר", "הערות"],
        ["  מוצר עם רווחים  ", "0", ""],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "test.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    session = resp.get_json()["session"]
    rows = logged_in_client_a.get(f"/api/imports/{session['id']}/rows").get_json()["rows"]
    assert rows[0]["raw_data"]["מוצר"] == "  מוצר עם רווחים  "
    assert rows[0]["raw_data"]["מחיר"] == "0"
    assert rows[0]["raw_data"]["הערות"] == ""


def test_wide_format_duplicate_headers_are_not_lost(logged_in_client_a):
    """Real files (e.g. גידרון) repeat the same header ("לפני מע\"מ") once
    per supplier column — the raw capture must not let one column's data
    silently overwrite another's."""
    data = _xlsx_bytes([
        ["מוצר", "לפני מע\"מ", "לפני מע\"מ", "לפני מע\"מ"],
        ["בורקס גבינה", "20.85", "12.8", "14.64"],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "wide.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    session = resp.get_json()["session"]
    assert len(session["column_headers"]) == 4  # all 4 columns kept, none dropped

    rows = logged_in_client_a.get(f"/api/imports/{session['id']}/rows").get_json()["rows"]
    values = list(rows[0]["raw_data"].values())
    assert sorted(values) == sorted(["בורקס גבינה", "20.85", "12.8", "14.64"])


def test_upload_with_supplier_id_tall_format(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "אנג'ל"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["חלה קלועה", "6.54"]])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "angel.xlsx", XLSX_MIME), "supplier_id": str(supplier_id)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["session"]["supplier_id"] == supplier_id


def test_upload_rejects_cross_tenant_supplier_id(logged_in_client_a, logged_in_client_b):
    foreign_supplier_id = logged_in_client_b.post("/api/catalog/suppliers", json={"name": "B Supplier"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "x.xlsx", XLSX_MIME), "supplier_id": str(foreign_supplier_id)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_empty_file_marks_session_failed_not_500(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"]])  # header only, zero data rows
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "empty.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201  # the upload itself succeeds
    session = resp.get_json()["session"]
    assert session["status"] == "FAILED"
    assert session["error_message"]


def test_upload_rejects_disallowed_extension(logged_in_client_a):
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(b"not a real file"), "malware.exe", "application/octet-stream")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_upload"


def test_upload_rejects_missing_file(logged_in_client_a):
    resp = logged_in_client_a.post("/api/imports/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "no_file"


def test_upload_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    resp = client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "x.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403


def test_list_and_get_session_tenant_isolated(logged_in_client_a, logged_in_client_b):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "x.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    ).get_json()["session"]["id"]

    b_list = logged_in_client_b.get("/api/imports").get_json()["sessions"]
    assert session_id not in [s["id"] for s in b_list]

    assert logged_in_client_b.get(f"/api/imports/{session_id}").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/rows").status_code == 404


def test_import_upload_never_touches_catalog_tables(logged_in_client_a):
    """Hard guarantee check: uploading and staging a file must not create
    any Product, Supplier, or SupplierProductOffer rows — staging only."""
    before_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    before_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]

    data = _xlsx_bytes([
        ["מוצר", "גידרון", "עמית", "ווגשל"],
        ["בורקס גבינה", "20.85", "12.8", "14.64"],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "gidron.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["session"]["row_count"] == 1

    after_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    after_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert after_products == before_products
    assert after_suppliers == before_suppliers


def test_audit_log_records_import_session_created(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "x.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    logs = logged_in_client_a.get("/api/audit").get_json()["logs"]
    actions = [log["action"] for log in logs]
    assert "import.session_created" in actions


def test_two_tier_header_is_now_correctly_detected_and_excluded(logged_in_client_a):
    """Was: 'test_two_tier_header_is_captured_raw_but_misaligned_by_design',
    which pinned a real, documented limitation found against an actual
    uploaded file's 'גידרון' sheet: a two-row header — a sparse merged-cell
    supplier-name row above a real per-column sub-header row (יחידה/לפני
    מע"מ/הנחה...) — used to have its sub-header row misstaged as if it were
    a product, because Staging only ever removed ONE row no matter how
    many header tiers existed.

    Fixed by giving Staging (ImportService) and Analysis
    (ImportAnalysisService) a single shared header-detection function
    (app/utils/header_detection.py) instead of two independent,
    disagreeing implementations. That module's docstring calls this
    exact fix out as the deliberate, approved follow-up to the limitation
    this test used to pin — this test now pins the CORRECTED behavior.
    """
    data = _xlsx_bytes([
        [None, "גידרון", None, None, "עמית", "ווגשל"],
        ["מוצר", "יחידה", 'לפני מע"מ', "הנחה", 'לפני מע"מ', 'לפני מע"מ'],
        ["בורקס גבינה", "קילו", 20.85, 14.6, 12.8, 14.64],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "gidron_real.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    session = resp.get_json()["session"]
    assert session["status"] == "UPLOADED"
    # Both header rows (the sparse supplier-name row AND the real
    # sub-header row) are now correctly excluded — only the genuine
    # product row remains.
    assert session["row_count"] == 1
    rows = logged_in_client_a.get(f"/api/imports/{session['id']}/rows").get_json()["rows"]
    # Column labels now come from the LAST header tier (closest to the
    # data) instead of the sparse supplier-name row.
    assert rows[0]["raw_data"]['לפני מע"מ (2)'] == "12.8"  # עמית's column, correctly labeled and as real data
    assert rows[0]["raw_data"]["יחידה"] == "קילו"           # real unit value, not the literal word "יחידה"


def test_simple_single_header_file_unaffected_by_shared_header_detection(logged_in_client_a):
    """Explicit backward-compatibility regression test for the Header
    Detection fix (app/utils/header_detection.py): a simple file with one
    header row must be staged identically to before the fix — same header
    row picked, same data start, same row count. detect_header() always
    returns tier_count=1 for this shape (unchanged since Phase 3.2A), so
    the new code path collapses to exactly the old behavior."""
    data = _xlsx_bytes([
        ["Product", "Price", "Supplier"],
        ["Coke", "10", "Supplier A"],
        ["Pepsi", "12", "Supplier B"],
    ])
    resp = logged_in_client_a.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), "simple.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    session = resp.get_json()["session"]
    assert session["status"] == "UPLOADED"
    assert session["column_headers"] == ["Product", "Price", "Supplier"]
    assert session["row_count"] == 2

    rows = logged_in_client_a.get(f"/api/imports/{session['id']}/rows").get_json()["rows"]
    assert rows[0]["raw_data"] == {"Product": "Coke", "Price": "10", "Supplier": "Supplier A"}
    assert rows[1]["raw_data"] == {"Product": "Pepsi", "Price": "12", "Supplier": "Supplier B"}

    # Cross-check: Analysis's independent detector agrees this is a
    # single-tier header — confirms Staging and Analysis are now
    # consistent (both call the same shared function).
    analyze_resp = logged_in_client_a.post(f"/api/imports/{session['id']}/analyze")
    sheet = analyze_resp.get_json()["analysis"][0]
    assert sheet["header_tier_count"] == 1
