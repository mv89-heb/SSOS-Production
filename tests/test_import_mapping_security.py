import io
import openpyxl

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _mapping(client):
    workbook = io.BytesIO(_xlsx([["מוצר", "מחיר"], ["X", "1"]]))
    resp = client.post("/api/imports/upload", data={"file": (workbook, "security.xlsx", XLSX_MIME)}, content_type="multipart/form-data")
    assert resp.status_code == 201, resp.get_json()
    session_id = resp.get_json()["session"]["id"]
    assert client.post(f"/api/imports/{session_id}/analyze").status_code == 200
    mapping = client.get(f"/api/imports/{session_id}/mapping").get_json()["mapping"]
    return session_id, mapping


def _second_user(client):
    from app.extensions import db
    from app.models.user import User, ROLE_MANAGER
    tenant_id = client.get("/api/auth/me").get_json()["user"]["tenant_id"]
    with client.application.app_context():
        user = User(tenant_id=tenant_id, email="mapping-approver@acme.test", full_name="Mapping Approver", role=ROLE_MANAGER, active=True)
        user.set_password("Passw0rd1")
        db.session.add(user)
        db.session.commit()
    approver = client.application.test_client()
    login = approver.post("/api/auth/login", json={"email": "mapping-approver@acme.test", "password": "Passw0rd1"})
    assert login.status_code == 200
    return approver


def test_mapping_rejects_non_array_decisions(logged_in_client_a):
    session_id, _ = _mapping(logged_in_client_a)
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={"decisions": {"column_index": 0, "target": "IGNORE"}})
    assert resp.status_code == 400


def test_approved_mapping_cannot_be_edited(logged_in_client_a):
    session_id, mapping = _mapping(logged_in_client_a)
    for column in mapping["columns"]:
        review = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={"decisions": [{"column_index": column["column_index"], "target": column["final_target"]}]})
        assert review.status_code == 200, review.get_json()
    approver = _second_user(logged_in_client_a)
    approved = approver.post(f"/api/imports/{session_id}/mapping/approve")
    assert approved.status_code == 200, approved.get_json()
    column = mapping["columns"][0]
    resp = logged_in_client_a.post(f"/api/imports/{session_id}/mapping", json={"decisions": [{"column_index": column["column_index"], "target": "IGNORE"}]})
    assert resp.status_code == 409
