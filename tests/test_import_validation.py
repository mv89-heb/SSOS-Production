import io
import openpyxl


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_bytes(rows, merges=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    for merge_range in (merges or []):
        ws.merge_cells(merge_range)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _upload(client, data, filename="test.xlsx", supplier_id=None):
    form = {"file": (io.BytesIO(data), filename, XLSX_MIME)}
    if supplier_id is not None:
        form["supplier_id"] = str(supplier_id)
    return client.post("/api/imports/upload", data=form, content_type="multipart/form-data")


def _full_pipeline(client, data, **kwargs):
    """upload -> analyze -> get mapping -> approve -> returns session_id."""
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    client.post(f"/api/imports/{session_id}/analyze")
    client.get(f"/api/imports/{session_id}/mapping")
    client.post(f"/api/imports/{session_id}/mapping/approve")
    return session_id


# --- Valid import ------------------------------------------------------

def test_valid_tall_import_creates_new_product(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Angel"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([
        ["מוצר", "יחידה", "מחיר"],
        ["חלה קלועה", "יחידה", "6.54"],
    ])
    session_id = _full_pipeline(logged_in_client_a, data, supplier_id=supplier_id)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert resp.status_code == 200
    summary = resp.get_json()["validation"]["summary"]
    assert summary["products"]["created"] == 1
    assert summary["errors"] == 0

    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]
    assert preview[0]["product_action"] == "CREATE"
    assert preview[0]["product_name"] == "חלה קלועה"
    assert preview[0]["price"] == 6.54


def test_validate_requires_approved_mapping(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _upload(logged_in_client_a, data).get_json()["session"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    logged_in_client_a.get(f"/api/imports/{session_id}/mapping")

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert resp.status_code == 422


# --- Missing fields ------------------------------------------------------

def test_missing_product_name_is_error(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["", "10"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    validation = resp.get_json()["validation"]
    assert validation["summary"]["errors"] >= 1

    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "missing_product_name" for i in issues)


def test_missing_unit_is_warning_not_error(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "5"]])
    session_id = _full_pipeline(logged_in_client_a, data, supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    missing_unit = next(i for i in issues if i["code"] == "missing_unit")
    assert missing_unit["severity"] == "WARNING"
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "CREATE"  # a warning doesn't block the row


def test_missing_price_is_error(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", ""]])
    session_id = _full_pipeline(logged_in_client_a, data)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = resp.get_json()["validation"]  # trigger via response too
    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert any(i["code"] == "missing_price" for i in validation["issues"])
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "ERROR"


# --- Invalid prices --------------------------------------------------------

def test_zero_price_is_warning(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "0"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    zero = next(i for i in issues if i["code"] == "zero_price")
    assert zero["severity"] == "WARNING"


def test_negative_price_is_error(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "-5"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    neg = next(i for i in issues if i["code"] == "negative_price")
    assert neg["severity"] == "ERROR"
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "ERROR"


def test_invalid_price_text_is_error(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "abc"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "invalid_price" for i in issues)


# --- Duplicate products ----------------------------------------------------

def test_matches_existing_product_by_barcode_and_suggests_update(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Existing Cola", "current_price": 5.0, "barcode": "7290000111222",
    })
    data = _xlsx_bytes([
        ["ברקוד", "מוצר", "מחיר"],
        ["7290000111222", "Cola Renamed", "6.5"],
    ])
    session_id = _full_pipeline(logged_in_client_a, data, supplier_id=supplier_id)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    summary = resp.get_json()["validation"]["summary"]
    assert summary["products"]["updated"] == 1
    assert summary["products"]["created"] == 0

    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "UPDATE"
    assert preview["matched_product_id"] == supplier_id or preview["matched_product_id"] is not None
    assert preview["old_price"] == 5.0
    assert preview["price"] == 6.5


def test_matching_product_with_same_price_is_skipped(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Same Product", "current_price": 9.99,
    })
    data = _xlsx_bytes([["מוצר", "מחיר"], ["Same Product", "9.99"]])
    session_id = _full_pipeline(logged_in_client_a, data, supplier_id=supplier_id)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    summary = resp.get_json()["validation"]["summary"]
    assert summary["products"]["skipped"] == 1
    assert summary["products"]["updated"] == 0


def test_duplicate_product_within_file_flagged(logged_in_client_a):
    data = _xlsx_bytes([
        ["מוצר", "מחיר"],
        ["Same Name", "1"],
        ["Same Name", "2"],
    ])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "duplicate_in_file" for i in issues)


def test_similar_product_name_flagged_as_warning(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "בורקס גבינה משולש", "current_price": 20.0,
    })
    data = _xlsx_bytes([["מוצר", "מחיר"], ["בורקס גבינה משולשת", "20.5"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "similar_product_name" for i in issues)


def test_unusual_price_change_flagged(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Volatile", "current_price": 10.0,
    })
    data = _xlsx_bytes([["מוצר", "מחיר"], ["Volatile", "50"]])  # 5x jump
    session_id = _full_pipeline(logged_in_client_a, data, supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "unusual_price_change" for i in issues)


# --- Duplicate suppliers / WIDE format --------------------------------------

def test_wide_format_cheapest_offer_becomes_primary(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes(
        [
            [None, "גידרון", None, None, "עמית", "ווגשל"],
            ["מוצר", "יחידה", 'לפני מע"מ', "הנחה", 'לפני מע"מ', 'לפני מע"מ'],
            ["בורקס גבינה", "קילו", 20.85, 14.6, 12.8, 14.64],
        ],
        merges=["B1:D1"],
    )
    session_id = _full_pipeline(logged_in_client_a, data)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    summary = resp.get_json()["validation"]["summary"]
    assert summary["suppliers"]["created"] == 2  # גידרון, ווגשל are new; עמית already exists

    preview_rows = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]
    # The real row (row 3 — row 1/2 are the two-tier header artifact, a
    # known/documented limitation) has the cheapest offer as primary.
    real_row = next(r for r in preview_rows if r["product_name"] == "בורקס גבינה")
    assert real_row["price"] == 12.8  # עמית's price, the cheapest of the 4 offer columns
    # 3 distinct suppliers (גידרון, עמית, ווגשל), not 4 — גידרון's two price
    # columns (before_vat + discount) correctly dedupe to one offer now.
    assert len(real_row["offers"]) == 3
    supplier_names = {o["supplier_name"] for o in real_row["offers"]}
    assert supplier_names == {"גידרון", "עמית", "ווגשל"}


def test_new_supplier_mentioned_twice_counted_once(logged_in_client_a):
    data = _xlsx_bytes(
        [
            [None, "חדש-ספק"],
            ["מוצר", 'לפני מע"מ'],
            ["A", "10"],
            ["B", "20"],
        ],
        merges=["A1:A1"],
    )
    session_id = _full_pipeline(logged_in_client_a, data)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    summary = resp.get_json()["validation"]["summary"]
    assert summary["suppliers"]["created"] == 1  # not 2, even though it appears on 2 rows


# --- Unit normalization ------------------------------------------------------

def test_unit_normalization_suggestion(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["X", 'ק"ג', "10"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "unit_normalization_suggestion" for i in issues)


# --- Re-run is idempotent ----------------------------------------------------

def test_revalidate_replaces_not_accumulates(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    second = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]
    assert len(preview) == 1  # not 2


def test_get_validation_before_running_returns_404(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    resp = logged_in_client_a.get(f"/api/imports/{session_id}/validation")
    assert resp.status_code == 404


# --- Hard guarantee: validation never touches catalog tables ----------------

def test_validation_never_touches_catalog_tables(logged_in_client_a):
    before_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    before_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]

    data = _xlsx_bytes(
        [[None, "גידרון", "עמית"], ["מוצר", 'לפני מע"מ', 'לפני מע"מ'], ["בורקס גבינה", "20.85", "12.8"]],
        merges=["B1:B1"],
    )
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")

    after_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    after_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert after_products == before_products
    assert after_suppliers == before_suppliers


def test_audit_log_records_validation(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    actions = [log["action"] for log in logged_in_client_a.get("/api/audit").get_json()["logs"]]
    assert "import.validated" in actions


# --- Permissions / tenant isolation ------------------------------------------

def test_validate_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _full_pipeline(client_a, data)

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.post(f"/api/imports/{session_id}/validate")
    assert resp.status_code == 403


def test_validation_tenant_isolated(logged_in_client_a, logged_in_client_b):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _full_pipeline(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")

    assert logged_in_client_b.post(f"/api/imports/{session_id}/validate").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/validation").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/preview").status_code == 404


def test_same_supplier_multiple_price_columns_prefers_regular_over_discount(logged_in_client_a):
    """Regression test for a real bug found reviewing actual imported data:
    when one supplier has both a regular/before-VAT price column and a
    discount price column in the same WIDE row, the deduped offer must
    keep the regular price, not whichever happened to sort first."""
    data = _xlsx_bytes(
        [
            [None, "גידרון"],
            ["מוצר", 'לפני מע"מ', "הנחה"],
            ["X", "20.85", "14.6"],
        ],
        merges=["B1:C1"],
    )
    session_id = _full_pipeline(logged_in_client_a, data)
    validate_resp = logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]
    row = next(r for r in preview if r["product_name"] == "X")
    assert row["price"] == 20.85  # the regular/before_vat price, not the discount one
