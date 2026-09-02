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
        manager = User(tenant_id=tenant_id, email="import-approver@acme.test", full_name="Import Approver", role=ROLE_MANAGER, active=True)
        manager.set_password("Passw0rd1")
        db.session.add(manager)
        db.session.commit()
    approver_client = client.application.test_client()
    login = approver_client.post("/api/auth/login", json={"email": "import-approver@acme.test", "password": "Passw0rd1"})
    assert login.status_code == 200, login.get_json()
    return approver_client


def _ready_to_commit(client, data, **kwargs):
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    assert client.post(f"/api/imports/{session_id}/analyze").status_code == 200
    mapping = client.get(f"/api/imports/{session_id}/mapping").get_json()["mapping"]
    for col in mapping["columns"]:
        review = client.post(f"/api/imports/{session_id}/mapping", json={
            "decisions": [{"column_index": col["column_index"], "target": col["final_target"]}]
        })
        assert review.status_code == 200, review.get_json()
    approver_client = _approve_as_second_user(client)
    approved = approver_client.post(f"/api/imports/{session_id}/mapping/approve")
    assert approved.status_code == 200, approved.get_json()
    validated = client.post(f"/api/imports/{session_id}/validate")
    assert validated.status_code == 200, validated.get_json()
    return session_id


def test_commit_requires_validation(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _upload(logged_in_client_a, data, supplier_id=supplier_id).get_json()["session"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    mapping = logged_in_client_a.get(f"/api/imports/{session_id}/mapping").get_json()["mapping"]
    for col in mapping["columns"]:
        review = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={"decisions": [{"column_index": col["column_index"], "target": col["final_target"]}]})
        assert review.status_code == 200, review.get_json()
    approver_client = _approve_as_second_user(logged_in_client_a)
    assert approver_client.post(f"/api/imports/{session_id}/mapping/approve").status_code == 200
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 422


def test_commit_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee
    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    supplier_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    session_id = _ready_to_commit(client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]), supplier_id=supplier_id)
    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})
    assert client_a.post(f"/api/imports/{session_id}/commit").status_code == 403


def test_commit_creates_new_supplier_and_product_tall_format(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["בורקס גבינה", "20.85"]], merges=["A1:A1"]))
    assert logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"] == []
    assert logged_in_client_a.get("/api/catalog/products").get_json()["products"] == []
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201
    execution = resp.get_json()["execution"]
    assert execution["summary"]["suppliers_created"] == 1
    assert execution["summary"]["products_created"] == 1
    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    assert suppliers[0]["name"] == "גידרון"
    assert products[0]["name"] == "בורקס גבינה"
    assert products[0]["current_price"] == 20.85
    assert products[0]["supplier_id"] == suppliers[0]["id"]


def test_commit_uses_existing_supplier_no_duplicate(logged_in_client_a):
    existing = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"}).get_json()["supplier"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "עמית"], ["מוצר", 'לפני מע"מ'], ["X", "5"]], merges=["A1:A1"]))
    execution = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]
    assert execution["summary"]["suppliers_created"] == 0
    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert len(suppliers) == 1 and suppliers[0]["id"] == existing["id"]


def test_commit_updates_existing_product_price(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    product_id = logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Existing", "current_price": 5.0}).get_json()["product"]["id"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["Existing", "7.5"]]), supplier_id=supplier_id)
    execution = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]
    assert execution["summary"]["products_updated"] == 1
    assert execution["summary"]["products_created"] == 0
    assert execution["price_history"][0]["old_price"] == 5.0
    assert execution["price_history"][0]["new_price"] == 7.5
    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["id"] == product_id and product["current_price"] == 7.5


def test_commit_creates_supplier_offers_for_wide_format(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes([[None, "גידרון", "עמית", "ווגשל"], ["מוצר", 'לפני מע"מ', 'לפני מע"מ', 'לפני מע"מ'], ["בורקס גבינה", "20.85", "12.8", "14.64"]], merges=["B1:B1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]
    assert execution["summary"]["products_created"] == 1
    assert execution["summary"]["offers_created"] == 2
    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["current_price"] == 12.8
    offers = logged_in_client_a.get(f"/api/catalog/products/{product['id']}/offers").get_json()["offers"]
    assert sorted(o["price"] for o in offers) == [14.64, 20.85]


def test_commit_skips_row_with_no_resolvable_supplier_gracefully(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]))
    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert any(i["code"] == "missing_supplier" for i in validation["issues"])
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201
    assert resp.get_json()["execution"]["summary"]["products_created"] == 0


def test_cannot_commit_same_session_twice(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]]), supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert logged_in_client_a.post(f"/api/imports/{session_id}/commit").status_code == 422


def test_rollback_deletes_created_product_and_supplier(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    resp = logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert resp.status_code == 200
    assert resp.get_json()["execution"]["status"] == "ROLLED_BACK"
    assert logged_in_client_a.get("/api/catalog/products").get_json()["products"] == []
    assert logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"] == []


def test_rollback_restores_old_price_not_deletes_updated_product(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    product_id = logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Existing", "current_price": 5.0}).get_json()["product"]["id"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([["מוצר", "מחיר"], ["Existing", "9.99"]]), supplier_id=supplier_id)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    assert len(products) == 1 and products[0]["id"] == product_id and products[0]["current_price"] == 5.0


def test_rollback_preserves_pre_existing_supplier(logged_in_client_a):
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"}).get_json()["supplier"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "עמית"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert len(suppliers) == 1 and suppliers[0]["id"] == supplier["id"]


def test_cannot_rollback_twice(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback").status_code == 422


def test_can_recommit_after_rollback(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert logged_in_client_a.post(f"/api/imports/{session_id}/commit").status_code == 201


def test_commit_does_not_touch_unrelated_existing_data(logged_in_client_a):
    other_supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Unrelated Supplier"}).get_json()["supplier"]
    other_product = logged_in_client_a.post("/api/catalog/products", json={"supplier_id": other_supplier["id"], "name": "Unrelated Product", "current_price": 99.0}).get_json()["product"]
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["בורקס גבינה", "20.85"]], merges=["A1:A1"]))
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    unrelated = next(p for p in products if p["id"] == other_product["id"])
    assert unrelated["name"] == "Unrelated Product" and unrelated["current_price"] == 99.0
    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert any(s["id"] == other_supplier["id"] for s in suppliers)


def test_audit_log_records_commit_and_rollback(logged_in_client_a):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    actions = [log["action"] for log in logged_in_client_a.get("/api/audit").get_json()["logs"]]
    assert "import.committed" in actions and "import.rolled_back" in actions
    assert "catalog.supplier_created" in actions and "catalog.product_created" in actions


def test_execution_tenant_isolated(logged_in_client_a, logged_in_client_b):
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([[None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"]], merges=["A1:A1"]))
    assert logged_in_client_b.post(f"/api/imports/{session_id}/commit").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/execution").status_code == 404
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    assert logged_in_client_b.post(f"/api/imports/executions/{execution_id}/rollback").status_code == 404


def test_commit_sets_unit_and_category_on_created_product(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "יחידה", "קטגוריה", "מחיר"], ["בורקס גבינה", "קילו", "מאפים", "20.85"]])
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "גידרון"}).get_json()["supplier"]["id"]
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=supplier_id)
    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["unit"] == "קילו" and preview["category"] == "מאפים"
    assert logged_in_client_a.post(f"/api/imports/{session_id}/commit").status_code == 201
    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["unit"] == "קילו" and product["category"] == "מאפים"


def test_commit_does_not_overwrite_unit_on_existing_product_update(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={"supplier_id": supplier_id, "name": "Existing", "current_price": 5.0, "unit": "יחידה מותאמת"})
    session_id = _ready_to_commit(logged_in_client_a, _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["Existing", "קילו", "9.99"]]), supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["current_price"] == 9.99 and product["unit"] == "יחידה מותאמת"
