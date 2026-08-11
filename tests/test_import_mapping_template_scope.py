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


def test_template_for_supplier_a_cannot_be_applied_to_supplier_b(logged_in_client_a):
    supplier_a = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier A"}
    ).get_json()["supplier"]
    supplier_b = logged_in_client_a.post(
        "/api/catalog/suppliers", json={"name": "Supplier B"}
    ).get_json()["supplier"]

    # Mapping creation/approval is intentionally not exercised here; this is
    # a service-boundary regression test through the HTTP mapping endpoints.
    from app.extensions import db
    from app.models.import_mapping import ImportMapping
    from app.models.import_mapping import ImportMappingTemplate
    from app.models.import_session import STATUS_UPLOADED

    data = _xlsx_bytes([["מוצר", "מחיר"], ["X", "10"]])
    response = _upload(logged_in_client_a, data, supplier_id=supplier_b["id"])
    assert response.status_code == 201
    session_id = response.get_json()["session"]["id"]

    logged_in_client_a.post(f"/api/imports/{session_id}/analyze")
    mapping_response = logged_in_client_a.get(f"/api/imports/{session_id}/mapping")
    assert mapping_response.status_code == 200
    mapping_id = mapping_response.get_json()["mapping"]["id"]

    # Seed a maliciously reusable template directly so the test remains
    # focused on the service's scope validation rather than UI suggestion logic.
    template = ImportMappingTemplate(
        tenant_id=supplier_b["id"] and 1,
        supplier_id=supplier_a["id"],
        name="Supplier A template",
        source_filename="template-scope.xlsx",
        column_mapping={
            "מוצר": {"target": "PRODUCT_NAME", "supplier_id": None, "supplier_name": None, "price_type": None},
            "מחיר": {"target": "PRICE", "supplier_id": supplier_a["id"], "supplier_name": "Supplier A", "price_type": None},
        },
        created_by=1,
    )
    db.session.add(template)
    db.session.commit()

    response = logged_in_client_a.post(
        f"/api/imports/{session_id}/mapping/templates/{template.id}/apply"
    )
    assert response.status_code == 409
    assert "different supplier" in response.get_json()["message"].lower()
