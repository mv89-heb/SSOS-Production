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
    resp = client.post(
        "/api/imports/upload",
        data={"file": (io.BytesIO(_xlsx([["מוצר", "מחיר"], ["X", "1"]]), "security.xlsx", XLSX_MIME)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, resp.get_json()
    session_id = resp.get_json()["session"]["id"]
    client.post(f"/api/imports/{session_id}/analyze")
    mapping = client.get(f"/api/imports/{session_id}/mapping").get_json()["mapping"]
    return session_id, mapping


def test_mapping_rejects_non_array_decisions(logged_in_client_a):
    session_id, _ = _mapping(logged_in_client_a)
    resp = logged_in_client_a.post(
        f"/api/imports/{session_id}/mapping",
        json={"decisions": {"column_index": 0, "target": "IGNORE"}},
    )
    assert resp.status_code == 400


def test_approved_mapping_cannot_be_edited(logged_in_client_a):
    session_id, mapping = _mapping(logged_in_client_a)
    approved = logged_in_client_a.post(f"/api/imports/{session_id}/mapping/approve")
    assert approved.status_code == 200

    column = mapping["columns"][0]
    resp = logged_in_client_a.post(
        f"/api/imports/{session_id}/mapping",
        json={"decisions": [{"column_index": column["column_index"], "target": "IGNORE"}]},
    )
    assert resp.status_code == 409
