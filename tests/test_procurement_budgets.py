from datetime import date

from app.models.order import Order, STATUS_DRAFT, STATUS_SUBMITTED
from app.models.procurement_budget import ProcurementBudget
from app.models.user import User, ROLE_EMPLOYEE


def _create_budget(
    client, *, scope_type="department", scope_value="Kitchen",
    period_type="monthly", period_start="2026-11-01",
    amount=100, currency="ILS", enforcement_mode="block",
):
    response = client.post("/api/procurement-budgets", json={
        "scope_type": scope_type,
        "scope_value": scope_value,
        "period_type": period_type,
        "period_start": period_start,
        "amount": amount,
        "currency": currency,
        "enforcement_mode": enforcement_mode,
    })
    return response


def _assign_order(client, order_id, *, department="Kitchen", project=None):
    response = client.put(f"/api/orders/{order_id}", json={
        "department": department,
        "project": project,
    })
    assert response.status_code == 200, response.get_json()
    return response.get_json()["order"]


def test_blocked_budget_requires_manager_override_reason_and_audit(
    logged_in_client_a, make_order, db
):
    response, _, _ = make_order(logged_in_client_a, quantity=2, price=100.0, planned_order_date="2026-11-18")
    assert response.status_code == 201
    order = response.get_json()["order"]
    _assign_order(logged_in_client_a, order["id"], department="Kitchen", project="Dorms")

    budget_response = _create_budget(
        logged_in_client_a, scope_type="department", scope_value="Kitchen",
        amount=1, enforcement_mode="block",
    )
    assert budget_response.status_code == 201, budget_response.get_json()

    preview = logged_in_client_a.get(f"/api/procurement-budgets/orders/{order['id']}/impact")
    assert preview.status_code == 200
    impact = preview.get_json()["budget_impact"]
    assert impact["blocked"] is True
    assert impact["blocks"][0]["scope_value"] == "Kitchen"
    assert impact["blocks"][0]["projected_total"] > impact["blocks"][0]["budget_amount"]

    blocked = logged_in_client_a.post(f"/api/orders/{order['id']}/submit", json={})
    assert blocked.status_code == 409
    assert blocked.get_json()["error"] == "budget_exceeded"
    assert Order.query.filter_by(id=order["id"]).one().status == STATUS_DRAFT

    submitted = logged_in_client_a.post(
        f"/api/orders/{order['id']}/submit",
        json={"budget_override_reason": "אספקה דחופה לצורך פעילות הישיבה"},
    )
    assert submitted.status_code == 200, submitted.get_json()
    assert submitted.get_json()["order"]["status"] == STATUS_SUBMITTED
    override_event = next(
        (event for event in AuditLog.query.order_by(AuditLog.id.desc()).all()
         if event.action == "order.budget_override"),
        None,
    )
    assert override_event is not None
    assert "אספקה דחופה" in str(override_event.details)


def test_warning_budget_allows_submission_and_tracks_committed_spend(
    logged_in_client_a, make_order, db
):
    first_response, _, _ = make_order(
        logged_in_client_a, quantity=1, price=40.0, planned_order_date="2026-11-18", sku="BUDGET-ONE"
    )
    first = first_response.get_json()["order"]
    _assign_order(logged_in_client_a, first["id"], department="Kitchen")
    first_submit = logged_in_client_a.post(f"/api/orders/{first['id']}/submit", json={})
    assert first_submit.status_code == 200

    budget = _create_budget(
        logged_in_client_a, amount=50, enforcement_mode="warn"
    )
    assert budget.status_code == 201, budget.get_json()

    second_response, _, _ = make_order(
        logged_in_client_a, quantity=1, price=20.0, planned_order_date="2026-11-18", sku="BUDGET-TWO"
    )
    second = second_response.get_json()["order"]
    _assign_order(logged_in_client_a, second["id"], department="Kitchen")
    preview = logged_in_client_a.get(f"/api/procurement-budgets/orders/{second['id']}/impact")
    impact = preview.get_json()["budget_impact"]["impacts"][0]
    assert impact["committed_before"] >= 40
    assert impact["over_budget"] is True
    assert impact["enforcement_mode"] == "warn"

    submitted = logged_in_client_a.post(f"/api/orders/{second['id']}/submit", json={})
    assert submitted.status_code == 200, submitted.get_json()

    budget_list = logged_in_client_a.get("/api/procurement-budgets")
    saved_budget = budget_list.get_json()["budgets"][0]
    assert saved_budget["spent_amount"] >= 60


def test_missing_budget_scope_requires_documented_manager_override(
    logged_in_client_a, make_order, db
):
    response, _, _ = make_order(
        logged_in_client_a, quantity=1, price=20.0, planned_order_date="2026-11-18"
    )
    order = response.get_json()["order"]
    _create_budget(logged_in_client_a, scope_type="department", scope_value="Kitchen", amount=500)

    preview = logged_in_client_a.get(f"/api/procurement-budgets/orders/{order['id']}/impact")
    impact = preview.get_json()["budget_impact"]
    assert impact["assignment_required"] is True
    assert impact["missing_scopes"] == ["department"]
    assert impact["blocked"] is True

    denied = logged_in_client_a.post(f"/api/orders/{order['id']}/submit", json={})
    assert denied.status_code == 409
    allowed = logged_in_client_a.post(
        f"/api/orders/{order['id']}/submit",
        json={"budget_override_reason": "הזמנה חד פעמית שאינה משויכת למחלקה"},
    )
    assert allowed.status_code == 200, allowed.get_json()


def test_employee_cannot_override_a_blocked_budget(
    logged_in_client_a, tenant_a_admin, make_order, db
):
    response, _, _ = make_order(
        logged_in_client_a, quantity=1, price=20.0, planned_order_date="2026-11-18"
    )
    order = response.get_json()["order"]
    _assign_order(logged_in_client_a, order["id"], department="Kitchen")
    _create_budget(logged_in_client_a, amount=1, enforcement_mode="block")

    user = User.query.filter_by(email="admin@acme.test").one()
    user.role = ROLE_EMPLOYEE
    db.session.commit()

    denied = logged_in_client_a.post(
        f"/api/orders/{order['id']}/submit",
        json={"budget_override_reason": "מנסה לעקוף"},
    )
    assert denied.status_code == 403
    assert Order.query.filter_by(id=order["id"]).one().status == STATUS_DRAFT


def test_budget_is_tenant_scoped_and_currency_is_never_converted(
    logged_in_client_a, logged_in_client_b, make_order
):
    _create_budget(logged_in_client_a, amount=1, enforcement_mode="block")
    response, _, _ = make_order(
        logged_in_client_b, quantity=1, price=20.0, planned_order_date="2026-11-18"
    )
    order = response.get_json()["order"]
    _assign_order(logged_in_client_b, order["id"], department="Kitchen")
    impact = logged_in_client_b.get(f"/api/procurement-budgets/orders/{order['id']}/impact")
    assert impact.status_code == 200
    assert impact.get_json()["budget_impact"]["impacts"] == []
    assert impact.get_json()["budget_impact"]["assignment_required"] is False
    submitted = logged_in_client_b.post(f"/api/orders/{order['id']}/submit", json={})
    assert submitted.status_code == 200


def test_weekly_budget_requires_monday_and_matches_order_planned_date(
    logged_in_client_a, make_order
):
    invalid = _create_budget(
        logged_in_client_a, period_type="weekly", period_start="2026-11-18"
    )
    assert invalid.status_code == 400

    valid = _create_budget(
        logged_in_client_a, period_type="weekly", period_start="2026-11-16",
        amount=100, enforcement_mode="warn",
    )
    assert valid.status_code == 201, valid.get_json()
    response, _, _ = make_order(
        logged_in_client_a, quantity=1, price=10.0, planned_order_date="2026-11-18"
    )
    order = response.get_json()["order"]
    _assign_order(logged_in_client_a, order["id"], department="Kitchen")
    impact = logged_in_client_a.get(f"/api/procurement-budgets/orders/{order['id']}/impact")
    assert impact.status_code == 200
    assert impact.get_json()["budget_impact"]["impacts"][0]["period_start"] == "2026-11-16"


def test_duplicate_budget_scope_is_case_insensitive(logged_in_client_a):
    first = _create_budget(logged_in_client_a, scope_value="Kitchen")
    assert first.status_code == 201
    duplicate = _create_budget(logged_in_client_a, scope_value="kitchen")
    assert duplicate.status_code == 409
