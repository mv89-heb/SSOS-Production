from app.models.user import User, ROLE_EMPLOYEE
from app.services.inventory_calendar_service import InventoryCalendarService


def _login_employee(app, db, tenant_id):
    employee = User(
        tenant_id=tenant_id,
        email="weekly-count-employee@example.test",
        full_name="Warehouse Employee",
        role=ROLE_EMPLOYEE,
        active=True,
    )
    employee.set_password("Passw0rd1")
    db.session.add(employee)
    db.session.commit()
    client = app.test_client()
    response = client.post("/api/auth/login", json={
        "email": employee.email,
        "password": "Passw0rd1",
    })
    assert response.status_code == 200, response.get_json()
    return client


def test_overdue_employee_cannot_mutate_operational_data_but_can_submit_count(
    app, db, tenant_a_admin, monkeypatch
):
    registration, _ = tenant_a_admin
    tenant_id = registration["tenant"]["id"]
    monkeypatch.setattr(
        InventoryCalendarService,
        "count_status",
        lambda self: {
            "active_products": 12,
            "counted_products_last_7_days": 3,
            "completion_percent": 25.0,
            "completed": False,
            "due": True,
            "next_due_date": "2026-10-25",
            "window_start": "2026-10-19",
            "count_weekday": 6,
            "count_time": "08:00",
        },
    )
    client = _login_employee(app, db, tenant_id)

    blocked = client.post("/api/catalog/suppliers", json={"name": "Should be blocked"})
    assert blocked.status_code == 423
    assert blocked.get_json()["error"] == "weekly_inventory_count_required"

    # The weekly gate must not prevent the employee from reaching the count workflow.
    allowed = client.post("/api/inventory/count/bulk", json={"items": []})
    assert allowed.status_code != 423
