import io

import openpyxl


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_bytes(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, data, filename="template-scope.xlsx", supplier_id=None):
    form = {"file": (io.BytesIO(data), filename, XLSX_MIME)}
    if supplier_id is not None:
        form["supplier_id"] = str(supplier_id)
    return client.post("/api/imports/upload", data=form, content_type="multipart/form-data")


def test_template_for_supplier_a_cannot_be_applied_to_supplier_b(logged_in_client_a, app):
    supplier_a = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier A"}).get_json()["supplier"]
    supplier_b = logged_in_client_a.post("/api/catalog/suppliers", json={"name": "Supplier B"}).get_json()["supplier"]

    from app.extensions import db
    from app.models.import_mapping import ImportMappingTemplate

    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "10"]])
    response = _upload(logged_in_client_a, data, supplier_id=supplier_b["id"])
    assert response.status_code == 201
    session_id = response.get_json()["session"]["id"]
    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    assert logged_in_client_a.get(f"/api/imports/{session_id}/mapping").status_code == 200

    with app.app_context():
        tenant_id = logged_in_client_a.get("/api/auth/me").get_json()["user"]["tenant_id"]
        user_id = logged_in_client_a.get("/api/auth/me").get_json()["user"]["id"]
        template = ImportMappingTemplate(
            tenant_id=tenant_id,
            supplier_id=supplier_a["id"],
            name="Supplier A template",
            source_filename="template-scope.xlsx",
            column_mapping={
                "מוצר": {"target": "PRODUCT_NAME", "supplier_id": None, "supplier_name": None, "price_type": None},
                "מחיר": {"target": "PRICE", "supplier_id": supplier_a["id"], "supplier_name": "Supplier A", "price_type": None},
            },
            created_by=user_id,
        )
        db.session.add(template)
        db.session.commit()
        template_id = template.id

    response = logged_in_client_a.post(f"/api/imports/{session_id}/mapping/templates/{template_id}/apply")
    assert response.status_code == 409
    assert "different supplier" in response.get_json()["message"].lower()
