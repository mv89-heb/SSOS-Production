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
    """Create a distinct manager in the same tenant and approve with it.

    Mapping approval intentionally enforces four-eyes control, so test helpers
    must not bypass that production rule by self-approving the creator's map.
    """
    from app.extensions import db
    from app.models.user import User, ROLE_MANAGER

    tenant_id = client.get("/api/auth/me").get_json()["user"]["tenant_id"]
    with client.application.app_context():
        manager = User(
            tenant_id=tenant_id,
            email="import-approver@acme.test",
            full_name="Import Approver",
            role=ROLE_MANAGER,
            active=True,
        )
        manager.set_password("Passw0rd1")
        db.session.add(manager)
        db.session.commit()

    approver_client = client.application.test_client()
    login = approver_client.post(
        "/api/auth/login",
        json={"email": "import-approver@acme.test", "password": "Passw0rd1"},
    )
    assert login.status_code == 200, login.get_json()
    return approver_client


def _ready_to_commit(client, data, **kwargs):
    """upload -> analyze -> map -> second-user approve -> validate."""
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    assert client.post(f"/api/imports/{session_id}/analyze").status_code == 200
    client.get(f"/api/imports/{session_id}/mapping")
    approver_client = _approve_as_second_user(client)
    approved = approver_client.post(f"/api/imports/{session_id}/mapping/approve")
    assert approved.status_code == 200, approved.get_json()
    validated = client.post(f"/api/imports/{session_id}/validate")
    assert validated.status_code == 200, validated.get_json()
    return session_id


# --- Commit prerequisites ---------------------------------------------------

def test_commit_requires_validation(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _upload(logged_in_client_a, data, supplier_id=supplier_id).get_json()["session"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    logged_in_client_a.get(f"/api/imports/{session_id}/mapping")
    approver_client = _approve_as_second_user(logged_in_client_a)
    assert approver_client.post(f"/api/imports/{session_id}/mapping/approve").status_code == 200
    # No /validate call
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 422


# --- Real writes: the core deliverable --------------------------------------


def test_commit_creates_new_supplier_and_product_tall_format(logged_in_client_a):
    data = _xlsx_bytes([
        [None, "גידרון"],
        ["מוצר", 'לפני מע"מ'],
        ["בורקס גבינה", "20.85"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)

    before_suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    before_products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    assert before_suppliers == [] and before_products == []

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201
    execution = resp.get_json()["execution"]
    assert execution["summary"]["suppliers_created"] == 1
    assert execution["summary"]["products_created"] == 1
    assert execution["status"] == "COMMITTED"

    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    assert len(suppliers) == 1 and suppliers[0]["name"] == "גידרון"
    assert len(products) == 1
    assert products[0]["name"] == "בורקס גבינה"
    assert products[0]["current_price"] == 20.85
    assert products[0]["supplier_id"] == suppliers[0]["id"]


def test_commit_uses_existing_supplier_no_duplicate(logged_in_client_a):
    existing = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"}).get_json()["supplier"]
    data = _xlsx_bytes([
        [None, "עמית"],
        ["מוצר", 'לפני מע"מ'],
        ["X", "5"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    execution = resp.get_json()["execution"]
    assert execution["summary"]["suppliers_created"] == 0

    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["id"] == existing["id"]


def test_commit_updates_existing_product_price(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    product_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Existing", "current_price": 5.0,
    }).get_json()["product"]["id"]

    data = _xlsx_bytes([["מוצר", "מחיר"], ["Existing", "7.5"]])
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=supplier_id)

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    execution = resp.get_json()["execution"]
    assert execution["summary"]["products_updated"] == 1
    assert execution["summary"]["products_created"] == 0
    assert execution["price_history"][0]["old_price"] == 5.0
    assert execution["price_history"][0]["new_price"] == 7.5

    product = logged_in_client_a.get(f"/api/catalog/products").get_json()["products"][0]
    assert product["id"] == product_id
    assert product["current_price"] == 7.5


def test_commit_creates_supplier_offers_for_wide_format(logged_in_client_a):
    logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"})
    data = _xlsx_bytes(
        [
            [None, "גידרון", "עמית", "ווגשל"],
            ["מוצר", 'לפני מע"מ', 'לפני מע"מ', 'לפני מע"מ'],
            ["בורקס גבינה", "20.85", "12.8", "14.64"],
        ],
        merges=["B1:B1"],
    )
    session_id = _ready_to_commit(logged_in_client_a, data)

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    execution = resp.get_json()["execution"]
    assert execution["summary"]["products_created"] == 1
    assert execution["summary"]["offers_created"] == 2

    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["current_price"] == 12.8
    offers = logged_in_client_a.get(f"/api/catalog/products/{product['id']}/offers").get_json()["offers"]
    assert len(offers) == 2
    prices = sorted(o["price"] for o in offers)
    assert prices == [14.64, 20.85]


def test_commit_skips_row_with_no_resolvable_supplier_gracefully(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _ready_to_commit(logged_in_client_a, data)

    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert any(i["code"] == "missing_supplier" for i in validation["issues"])

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201
    execution = resp.get_json()["execution"]
    assert execution["summary"]["products_created"] == 0


def test_cannot_commit_same_session_twice(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=(
        logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    ))
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    second = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert second.status_code == 422


def test_rollback_deletes_created_product_and_supplier(logged_in_client_a):
    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]

    assert len(logged_in_client_a.get("/api/catalog/products").get_json()["products"]) == 1
    assert len(logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]) == 1

    resp = logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert resp.status_code == 200
    assert resp.get_json()["execution"]["status"] == "ROLLED_BACK"

    assert logged_in_client_a.get("/api/catalog/products").get_json()["products"] == []
    assert logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"] == []


def test_rollback_restores_old_price_not_deletes_updated_product(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    product_id = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Existing", "current_price": 5.0,
    }).get_json()["product"]["id"]

    data = _xlsx_bytes([["מוצר", "מחיר"], ["Existing", "9.99"]])
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=supplier_id)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]

    resp = logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert resp.status_code == 200
    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["id"] == product_id
    assert product["current_price"] == 5.0
