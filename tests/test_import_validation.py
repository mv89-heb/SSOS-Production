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


def _approve_as_second_user(client):
    from app.extensions import db
    from app.models.user import User, ROLE_MANAGER
    tenant_id = client.get("/api/auth/me").get_json()["user"]["tenant_id"]
    with client.application.app_context():
        manager = User(tenant_id=tenant_id, email="validation-approver@acme.test", full_name="Validation Approver", role=ROLE_MANAGER, active=True)
        manager.set_password("Passw0rd1")
        db.session.add(manager)
        db.session.commit()
    approver = client.application.test_client()
    login = approver.post("/api/auth/login", json={"email": "validation-approver@acme.test", "password": "Passw0rd1"})
    assert login.status_code == 200, login.get_json()
    return approver


def _full_pipeline(client, data, **kwargs):
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    assert client.post(f"/api/imports/{session_id}/analyze").status_code == 200
    mapping = client.get(f"/api/imports/{session_id}/mapping").get_json()["mapping"]
    for col in mapping["columns"]:
        review = client.post(f"/api/imports/{session_id}/mapping", json={"decisions": [{"column_index": col["column_index"], "target": col["final_target"]}]})
        assert review.status_code == 200, review.get_json()
    approver = _approve_as_second_user(client)
    approved = approver.post(f"/api/imports/{session_id}/mapping/approve")
    assert approved.status_code == 200, approved.get_json()
    return session_id


def test_valid_tall_import_creates_new_product(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Angel"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["חלה קלועה", "יחידה", "6.54"]])
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
    assert logged_in_client_a.post(f"/api/imports/{session_id}/validate").status_code == 422


def test_missing_product_name_is_error(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["", "10"]]))
    validation = logged_in_client_a.post(f"/api/imports/{session_id}/validate").get_json()["validation"]
    assert validation["summary"]["errors"] >= 1
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "missing_product_name" for i in issues)


def test_missing_unit_is_warning_not_error(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["X", "", "5"]]), supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert not any(i["severity"] == "ERROR" and i.get("code") == "missing_unit" for i in validation["issues"])
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "CREATE"


def test_missing_price_is_error(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", ""]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert any(i["code"] == "missing_price" for i in validation["issues"])
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "ERROR"


def test_zero_price_is_warning(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "0"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    zero = next(i for i in issues if i["code"] == "zero_price")
    assert zero["severity"] == "WARNING"


def test_negative_price_is_error(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "-5"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    neg = next(i for i in issues if i["code"] == "negative_price")
    assert neg["severity"] == "ERROR"
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "ERROR"


def test_invalid_price_text_is_error(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "abc"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "invalid_price" for i in issues)


def test_matches_existing_product_by_barcode_and_suggests_update(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Existing Cola", "current_price": 5.0, "barcode": "7290000111222"})
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["ברקוד", "מוצר", "מחיר"], ["7290000111222", "Cola Renamed", "6.5"]]), supplier_id=supplier_id)
    summary = logged_in_client_a.post(f"/api/imports/{session_id}/validate").get_json()["validation"]["summary"]
    assert summary["products"]["updated"] == 1 and summary["products"]["created"] == 0
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["product_action"] == "UPDATE" and preview["matched_product_id"] is not None
    assert preview["old_price"] == 5.0 and preview["price"] == 6.5


def test_matching_product_with_same_price_is_skipped(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Same Product", "current_price": 9.99})
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["Same Product", "9.99"]]), supplier_id=supplier_id)
    summary = logged_in_client_a.post(f"/api/imports/{session_id}/validate").get_json()["validation"]["summary"]
    assert summary["products"]["skipped"] == 1 and summary["products"]["updated"] == 0


def test_duplicate_product_within_file_flagged(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["Same Name", "1"], ["Same Name", "2"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert len(logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]) == 2


def test_similar_product_name_flagged_as_warning(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "בורקס גבינה משולש", "current_price": 20.0})
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["בורקס גבינה משולשת", "20.5"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "similar_product_name" for i in issues)


def test_unusual_price_change_flagged(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Volatile", "current_price": 10.0})
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["Volatile", "50"]]), supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "unusual_price_change" for i in issues)


def test_wide_format_cheapest_offer_becomes_primary(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes([[None, "גידרון", None, None, "עמית", "ווגשל"], ["מוצר", "יחידה", 'לפני מע"מ', "הנחה", 'לפני מע"מ', 'לפני מע"מ'], ["בורקס גבינה", "קילו", 20.85, 14.6, 12.8, 14.64]], merges=["B1:D1"])
    session_id = _full_pipeline(logged_in_client_a, data)
    summary = logged_in_client_a.post(f"/api/imports/{session_id}/validate").get_json()["validation"]["summary"]
    assert summary["suppliers"]["created"] == 0
    real_row = next(r for r in logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"] if r["product_name"] == "בורקס גבינה")
    assert real_row["price"] == 12.8 and len(real_row["offers"]) == 3
    assert {o["supplier_name"] for o in real_row["offers"]} == {"גידרון", "עמית", "ווגשל"}


def test_new_supplier_mentioned_twice_counted_once(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([[None, "חדש-ספק"], ["מוצר", 'לפני מע"מ'], ["A", "10"], ["B", "20"]], merges=["A1:A1"]))
    summary = logged_in_client_a.post(f"/api/imports/{session_id}/validate").get_json()["validation"]["summary"]
    assert summary["suppliers"]["created"] == 1


def test_unit_normalization_suggestion(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["X", 'ק"ג', "10"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    issues = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]["issues"]
    assert any(i["code"] == "unit_normalization_suggestion" for i in issues)


def test_revalidate_replaces_not_accumulates(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert len(logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"]) == 1


def test_get_validation_before_running_returns_404(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    assert logged_in_client_a.get(f"/api/imports/{session_id}/validation").status_code == 404


def test_validation_never_touches_catalog_tables(logged_in_client_a):
    before_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    before_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([[None, "גידרון", "עמית"], ["מוצר", 'לפני מע"מ', 'לפני מע"מ'], ["בורקס גבינה", "20.85", "12.8"]], merges=["B1:B1"]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert logged_in_client_a.get("/api/catalog/products").get_json()["products"] == before_products
    assert logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"] == before_suppliers


def test_audit_log_records_validation(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    actions = [log["action"] for log in logged_in_client_a.get("/api/audit").get_json()["logs"]]
    assert "import.validated" in actions


def test_validate_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee
    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    session_id = _full_pipeline(client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})
    assert client_a.post(f"/api/imports/{session_id}/validate").status_code == 403


def test_validation_tenant_isolated(logged_in_client_a, logged_in_client_b):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    assert logged_in_client_b.post(f"/api/imports/{session_id}/validate").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/validation").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/preview").status_code == 404


def test_same_supplier_multiple_price_columns_prefers_regular_over_discount(logged_in_client_a):
    session_id = _full_pipeline(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ', "הנחה"], ["X", "20.85", "14.6"]], merges=["B1:C1"]))
    logged_in_client_a.post(f"/api/imports/{session_id}/validate")
    row = next(r for r in logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"] if r["product_name"] == "X")
    assert row["price"] == 20.85
