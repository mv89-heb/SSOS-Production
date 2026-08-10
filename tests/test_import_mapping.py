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


def _upload(client, data, filename="test.xlsx"):
    return client.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(data), filename, XLSX_MIME)},
        content_type="multipart/form-data",
    )


def _upload_analyze_and_map(client, data, **kwargs):
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    client.post(f"/api/imports/{session_id}/analyze")
    resp = client.get(f"/api/imports/{session_id}/mapping")
    return session_id, resp


# --- Tall format --------------------------------------------------------

def test_tall_format_mapping_suggestions(logged_in_client_a):
    data = _xlsx_bytes([
        ["מוצר", "יחידה", "מחיר"],
        ["חלה קלועה", "יחידה", "6.54"],
    ])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    assert resp.status_code == 200
    cols = {c["column_header"]: c for c in resp.get_json()["mapping"]["columns"]}
    assert cols["מוצר"]["suggested_target"] == "PRODUCT_NAME"
    assert cols["יחידה"]["suggested_target"] == "UNIT"
    assert cols["מחיר"]["suggested_target"] == "PRICE"
    # TALL format: no supplier attribution on a plain price column
    assert cols["מחיר"]["suggested_supplier_id"] is None


# --- Wide format ---------------------------------------------------------

def test_wide_format_mapping_suggests_supplier_offer(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes(
        [
            [None, "גידרון", None, None, "עמית", "ווגשל"],
            ["מוצר", "יחידה", 'לפני מע"מ', "הנחה", 'לפני מע"מ', 'לפני מע"מ'],
            ["בורקס גבינה", "קילו", 20.85, 14.6, 12.8, 14.64],
        ],
        merges=["B1:D1"],
    )
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    cols = resp.get_json()["mapping"]["columns"]
    by_header = {c["column_header"]: c for c in cols}

    gidron_col = by_header['לפני מע"מ']
    assert gidron_col["suggested_target"] == "SUPPLIER_OFFER"
    assert gidron_col["suggested_supplier_name"] == "גידרון"
    assert gidron_col["suggested_price_type"] == "before_vat"

    amit_col = by_header['לפני מע"מ (2)']
    assert amit_col["suggested_target"] == "SUPPLIER_OFFER"
    assert amit_col["suggested_supplier_name"] == "עמית"
    assert amit_col["suggested_supplier_id"] is not None  # matched real catalog supplier

    discount_col = by_header["הנחה"]
    assert discount_col["suggested_target"] == "SUPPLIER_OFFER"
    assert discount_col["suggested_price_type"] == "discount"


# --- Manual override -------------------------------------------------------

def test_manual_override_changes_target_and_marks_reviewed(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "הערה"], ["X", "note"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    mapping_id = resp.get_json()["mapping"]["id"]
    note_col = next(c for c in resp.get_json()["mapping"]["columns"] if c["column_header"] == "הערה")
    assert note_col["suggested_target"] == "IGNORE"
    assert note_col["user_reviewed"] is False

    update = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{"column_index": note_col["column_index"], "target": "CATEGORY"}]
    })
    assert update.status_code == 200
    updated = next(c for c in update.get_json()["mapping"]["columns"] if c["column_header"] == "הערה")
    assert updated["final_target"] == "CATEGORY"
    assert updated["user_reviewed"] is True
    assert updated["changed_from_suggestion"] is True


def test_override_supplier_name_without_id_clears_stale_supplier_id(logged_in_client_a):
    """Regression test for a real bug found in manual testing: setting
    supplier_name alone (a manual/new supplier not in the catalog) must
    clear any supplier_id left over from the original suggestion, or the
    name and id end up pointing at two different suppliers."""
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes(
        [[None, "עמית"], ["מוצר", 'לפני מע"מ'], ["X", "10"]],
        merges=["A1:A1"],
    )
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = next(c for c in resp.get_json()["mapping"]["columns"] if c["column_header"] == 'לפני מע"מ')
    assert col["suggested_supplier_id"] is not None  # matched the real "עמית" supplier

    update = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{
            "column_index": col["column_index"], "target": "SUPPLIER_OFFER",
            "supplier_name": "עמית ידני", "price_type": "before_vat",
        }]
    })
    updated = next(c for c in update.get_json()["mapping"]["columns"] if c["column_header"] == 'לפני מע"מ')
    assert updated["final_supplier_id"] is None
    assert updated["final_supplier_name"] == "עמית ידני"


def test_override_rejects_invalid_target(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = resp.get_json()["mapping"]["columns"][0]
    update = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{"column_index": col["column_index"], "target": "NOT_A_REAL_TARGET"}]
    })
    assert update.status_code in (400, 422)


def test_supplier_offer_requires_price_type(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "עמודה"], ["X", "5"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = next(c for c in resp.get_json()["mapping"]["columns"] if c["column_header"] == "עמודה")
    update = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{"column_index": col["column_index"], "target": "SUPPLIER_OFFER", "supplier_name": "X"}]
    })
    assert update.status_code in (400, 422)


def test_override_rejects_cross_tenant_supplier_id(logged_in_client_a, logged_in_client_b):
    foreign_supplier_id = logged_in_client_b.post(
        "/api/catalog/suppliers", json={"name": "Foreign"}
    ).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = next(c for c in resp.get_json()["mapping"]["columns"] if c["column_header"] == "מחיר")
    update = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{
            "column_index": col["column_index"], "target": "SUPPLIER_OFFER",
            "supplier_id": foreign_supplier_id, "price_type": "regular",
        }]
    })
    assert update.status_code == 404


# --- Approve ---------------------------------------------------------------

def test_approve_mapping_sets_status_and_approver(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, _ = _upload_analyze_and_map(logged_in_client_a, data)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/mapping/approve")
    assert resp.status_code == 200
    mapping = resp.get_json()["mapping"]
    assert mapping["status"] == "APPROVED"
    assert mapping["approved_by"] is not None
    assert mapping["approved_at"] is not None


# --- Save / reload template --------------------------------------------------

def test_save_and_reuse_template(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes(
        [[None, "עמית"], ["מוצר", 'לפני מע"מ'], ["X", "10"]],
        merges=["A1:A1"],
    )
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)

    save_resp = logged_in_client_a.post(f"/api/imports/{session_id}/mapping/templates", json={"name": "Amit Template"})
    assert save_resp.status_code == 201
    template = save_resp.get_json()["template"]
    assert template["name"] == "Amit Template"
    assert 'לפני מע"מ' in template["column_mapping"]

    # A second, similar upload should surface this template as a match by
    # (normalized) filename, and applying it should pre-fill decisions.
    session_id_2, resp_2 = _upload_analyze_and_map(logged_in_client_a, data, filename="test.xlsx")
    templates_list = logged_in_client_a.get(f"/api/imports/{session_id_2}/mapping/templates")
    assert templates_list.status_code == 200
    assert any(t["id"] == template["id"] for t in templates_list.get_json()["templates"])

    apply_resp = logged_in_client_a.post(
        f"/api/imports/{session_id_2}/mapping/templates/{template['id']}/apply"
    )
    assert apply_resp.status_code == 200
    applied_col = next(
        c for c in apply_resp.get_json()["mapping"]["columns"] if c["column_header"] == 'לפני מע"מ'
    )
    assert applied_col["final_target"] == "SUPPLIER_OFFER"
    assert applied_col["user_reviewed"] is True


def test_matching_templates_surfaced_on_get_mapping(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]], )
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data, filename="repeat.xlsx")
    mapping_id = resp.get_json()["mapping"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping/templates", json={"name": "Repeat Template"})

    session_id_2, resp_2 = _upload_analyze_and_map(logged_in_client_a, data, filename="repeat.xlsx")
    body = logged_in_client_a.get(f"/api/imports/{session_id_2}/mapping").get_json()
    assert any(t["name"] == "Repeat Template" for t in body["matching_templates"])


# --- Product / supplier field mapping vocabulary ----------------------------

def test_product_and_barcode_fields_mapped(logged_in_client_a):
    data = _xlsx_bytes([
        ["ברקוד", "מוצר", 'מק"ט', "קטגוריה"],
        ["7290000111222", "קולה", "COLA-1", "משקאות"],
    ])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    cols = {c["column_header"]: c["suggested_target"] for c in resp.get_json()["mapping"]["columns"]}
    assert cols["ברקוד"] == "BARCODE"
    assert cols["מוצר"] == "PRODUCT_NAME"
    assert cols['מק"ט'] == "PRODUCT_CODE"
    assert cols["קטגוריה"] == "CATEGORY"


# --- Idempotency: GET twice doesn't regenerate/duplicate --------------------

def test_get_mapping_twice_returns_same_mapping_not_duplicate(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp1 = _upload_analyze_and_map(logged_in_client_a, data)
    resp2 = logged_in_client_a.get(f"/api/imports/{session_id}/mapping")
    assert resp1.get_json()["mapping"]["id"] == resp2.get_json()["mapping"]["id"]


def test_get_mapping_preserves_prior_decisions(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = resp.get_json()["mapping"]["columns"][0]
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{"column_index": col["column_index"], "target": "IGNORE"}]
    })
    reget = logged_in_client_a.get(f"/api/imports/{session_id}/mapping")
    reloaded_col = reget.get_json()["mapping"]["columns"][0]
    assert reloaded_col["final_target"] == "IGNORE"
    assert reloaded_col["user_reviewed"] is True


# --- Hard guarantee: mapping never touches catalog tables --------------------

def test_mapping_never_touches_catalog_tables(logged_in_client_a):
    before_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    before_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]

    data = _xlsx_bytes(
        [[None, "גידרון", "עמית"], ["מוצר", 'לפני מע"מ', 'לפני מע"מ'], ["בורקס גבינה", "20.85", "12.8"]],
        merges=["B1:B1"],
    )
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping/approve")
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping/templates", json={"name": "T"})

    after_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    after_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert after_products == before_products
    assert after_suppliers == before_suppliers


def test_audit_log_records_mapping_lifecycle(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)
    col = resp.get_json()["mapping"]["columns"][0]
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={
        "decisions": [{"column_index": col["column_index"], "target": "IGNORE"}]
    })
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping/approve")

    actions = [log["action"] for log in logged_in_client_a.get("/api/audit").get_json()["logs"]]
    assert "import.mapping_created" in actions
    assert "import.mapping_updated" in actions
    assert "import.mapping_approved" in actions


# --- Permissions / tenant isolation ------------------------------------------

def test_mapping_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _upload(client_a, data).get_json()["session"]["id"]
    client_a.post(f"/api/imports/{session_id}/analyze")

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    assert client_a.get(f"/api/imports/{session_id}/mapping").status_code == 403


def test_mapping_tenant_isolated(logged_in_client_a, logged_in_client_b):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id, resp = _upload_analyze_and_map(logged_in_client_a, data)

    assert logged_in_client_b.get(f"/api/imports/{session_id}/mapping").status_code == 404
    assert logged_in_client_b.post(f"/api/imports/{session_id}/mapping", json={"decisions": []}).status_code == 404
    assert logged_in_client_b.post(f"/api/imports/{session_id}/mapping/approve").status_code == 404
