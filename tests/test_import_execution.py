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


def _ready_to_commit(client, data, **kwargs):
    """upload -> analyze -> map -> approve -> validate -> returns session_id."""
    session_id = _upload(client, data, **kwargs).get_json()["session"]["id"]
    client.post(f"/api/imports/{session_id}/analyze")
    client.get(f"/api/imports/{session_id}/mapping")
    client.post(f"/api/imports/{session_id}/mapping/approve")
    client.post(f"/api/imports/{session_id}/validate")
    return session_id


# --- Commit prerequisites ---------------------------------------------------

def test_commit_requires_validation(logged_in_client_a):
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _upload(logged_in_client_a, data, supplier_id=supplier_id).get_json()["session"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    logged_in_client_a.get(f"/api/imports/{session_id}/mapping")
    logged_in_client_a.post(f"/api/imports/{session_id}/mapping/approve")
    # No /validate call
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 422


def test_commit_requires_manager_role(client_a, tenant_a_admin):
    from test_security import _register_employee

    tenant_data, creds = tenant_a_admin
    slug = tenant_data["tenant"]["slug"]
    client_a.post("/api/auth/login", json=creds)
    supplier_id = client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _ready_to_commit(client_a, data, supplier_id=supplier_id)

    _register_employee(client_a, slug)
    client_a.post("/api/auth/logout")
    client_a.post("/api/auth/login", json={"email": "worker@acme.test", "password": "Passw0rd1"})

    resp = client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 403


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
    assert execution["summary"]["suppliers_created"] == 0  # matched existing, not duplicated

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
    assert execution["summary"]["offers_created"] == 2  # 2 alternates besides the cheapest (primary)

    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["current_price"] == 12.8  # cheapest (עמית) became primary
    offers = logged_in_client_a.get(f"/api/catalog/products/{product['id']}/offers").get_json()["offers"]
    assert len(offers) == 2
    prices = sorted(o["price"] for o in offers)
    assert prices == [14.64, 20.85]


def test_commit_skips_row_with_no_resolvable_supplier_gracefully(logged_in_client_a):
    """A TALL-format row with no mapped supplier column and no session
    supplier is caught by Validation (missing_supplier error) and must
    never reach Execution's write path — regression test for a real crash
    found in manual testing."""
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])  # no supplier_id at upload
    session_id = _ready_to_commit(logged_in_client_a, data)  # supplier_id=None

    validation = logged_in_client_a.get(f"/api/imports/{session_id}/validation").get_json()["validation"]
    assert any(i["code"] == "missing_supplier" for i in validation["issues"])

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201  # doesn't crash
    execution = resp.get_json()["execution"]
    assert execution["summary"]["products_created"] == 0  # the row was correctly skipped, not written


# --- Double-commit protection ------------------------------------------------

def test_cannot_commit_same_session_twice(logged_in_client_a):
    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "1"]])
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=(
        logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    ))
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    second = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert second.status_code == 422


# --- Rollback ----------------------------------------------------------------

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

    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")

    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    assert len(products) == 1  # NOT deleted — it existed before the import
    assert products[0]["id"] == product_id
    assert products[0]["current_price"] == 5.0  # price restored


def test_rollback_preserves_pre_existing_supplier(logged_in_client_a):
    """A supplier that already existed before the import must never be
    deleted by rollback, even though the import also touched it."""
    supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "עמית"}).get_json()["supplier"]
    data = _xlsx_bytes([
        [None, "עמית"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]

    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")

    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert len(suppliers) == 1
    assert suppliers[0]["id"] == supplier["id"]  # still there


def test_cannot_rollback_twice(logged_in_client_a):
    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]

    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    second = logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")
    assert second.status_code == 422


def test_can_recommit_after_rollback(logged_in_client_a):
    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201


# --- Hard guarantee: doesn't touch data outside this import's scope ---------

def test_commit_does_not_touch_unrelated_existing_data(logged_in_client_a):
    """Explicit test for the user's own requirement: existing data must
    never break, and only the chosen file/supplier is affected."""
    other_supplier = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Unrelated Supplier"}).get_json()["supplier"]
    other_product = logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": other_supplier["id"], "name": "Unrelated Product", "current_price": 99.0,
    }).get_json()["product"]

    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["בורקס גבינה", "20.85"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")

    products = logged_in_client_a.get("/api/catalog/products").get_json()["products"]
    unrelated = next(p for p in products if p["id"] == other_product["id"])
    assert unrelated["name"] == "Unrelated Product"
    assert unrelated["current_price"] == 99.0  # untouched

    suppliers = logged_in_client_a.get("/api/catalog/suppliers").get_json()["suppliers"]
    assert any(s["id"] == other_supplier["id"] and s["name"] == "Unrelated Supplier" for s in suppliers)


# --- Audit trail ---------------------------------------------------------

def test_audit_log_records_commit_and_rollback(logged_in_client_a):
    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)
    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    logged_in_client_a.post(f"/api/imports/executions/{execution_id}/rollback")

    actions = [log["action"] for log in logged_in_client_a.get("/api/audit").get_json()["logs"]]
    assert "import.committed" in actions
    assert "import.rolled_back" in actions
    # The underlying catalog writes are ALSO in the same audit trail (via
    # CatalogService, not a parallel one) — traceable either way.
    assert "catalog.supplier_created" in actions
    assert "catalog.product_created" in actions


# --- Tenant isolation ---------------------------------------------------

def test_execution_tenant_isolated(logged_in_client_a, logged_in_client_b):
    data = _xlsx_bytes([
        [None, "גידרון"], ["מוצר", 'לפני מע"מ'], ["X", "10"],
    ], merges=["A1:A1"])
    session_id = _ready_to_commit(logged_in_client_a, data)

    assert logged_in_client_b.post(f"/api/imports/{session_id}/commit").status_code == 404
    assert logged_in_client_b.get(f"/api/imports/{session_id}/execution").status_code == 404

    execution_id = logged_in_client_a.post(f"/api/imports/{session_id}/commit").get_json()["execution"]["id"]
    assert logged_in_client_b.post(f"/api/imports/executions/{execution_id}/rollback").status_code == 404


def test_commit_sets_unit_and_category_on_created_product(logged_in_client_a):
    """Regression test for a real bug found doing an actual end-to-end
    import: Validation correctly extracted unit/category per row, but
    never persisted them onto ImportPreview, so Execution had nothing to
    pass to CatalogService.create_product — every imported product
    silently got unit=None regardless of the source file."""
    data = _xlsx_bytes([
        ["מוצר", "יחידה", "קטגוריה", "מחיר"],
        ["בורקס גבינה", "קילו", "מאפים", "20.85"],
    ])
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "גידרון"}).get_json()["supplier"]["id"]
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=supplier_id)

    preview = logged_in_client_a.get(f"/api/imports/{session_id}/preview").get_json()["rows"][0]
    assert preview["unit"] == "קילו"
    assert preview["category"] == "מאפים"

    resp = logged_in_client_a.post(f"/api/imports/{session_id}/commit")
    assert resp.status_code == 201

    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["unit"] == "קילו"
    assert product["category"] == "מאפים"


def test_commit_does_not_overwrite_unit_on_existing_product_update(logged_in_client_a):
    """UPDATE stays price-only by design — an existing product's hand-
    curated unit/category must survive a price-only re-import."""
    supplier_id = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "S"}).get_json()["supplier"]["id"]
    logged_in_client_a.post("/api/catalog/products", json={
        "supplier_id": supplier_id, "name": "Existing", "current_price": 5.0, "unit": "יחידה מותאמת",
    })
    data = _xlsx_bytes([["מוצר", "יחידה", "מחיר"], ["Existing", "קילו", "9.99"]])
    session_id = _ready_to_commit(logged_in_client_a, data, supplier_id=supplier_id)
    logged_in_client_a.post(f"/api/imports/{session_id}/commit")

    product = logged_in_client_a.get("/api/catalog/products").get_json()["products"][0]
    assert product["current_price"] == 9.99
    assert product["unit"] == "יחידה מותאמת"  # untouched, not overwritten to "קילו"
