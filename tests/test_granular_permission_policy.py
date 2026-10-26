from types import SimpleNamespace

from app.services.granular_permission_policy import (
    effective_permissions,
    has_permission,
)


def user(role="employee", active=True, authenticated=True, permissions=None):
    return SimpleNamespace(
        role=role,
        active=active,
        is_authenticated=authenticated,
        permissions=permissions,
    )


def test_employee_defaults_allow_preparation_but_reserve_approval_and_sending():
    permissions = effective_permissions(user("employee"))
    assert permissions["orders.view"] is True
    assert permissions["orders.create"] is True
    assert permissions["orders.edit"] is True
    assert permissions["orders.approve"] is False
    assert permissions["orders.mark_sent"] is False
    assert permissions["orders.complete"] is True
    assert permissions["orders.delete"] is False
    assert permissions["permissions.manage"] is False


def test_manager_defaults_allow_catalog_management_and_order_approval():
    permissions = effective_permissions(user("manager"))
    assert permissions["catalog.manage"] is True
    assert permissions["orders.approve"] is True
    assert permissions["orders.mark_sent"] is True
    assert permissions["users.manage"] is False
    assert permissions["permissions.manage"] is False


def test_admin_has_all_permissions():
    assert effective_permissions(user("admin"))["*"] is True
    assert has_permission("permissions.manage", user("admin")) is True


def test_boolean_overrides_apply_only_to_known_permissions():
    permissions = effective_permissions(user("employee", permissions={
        "orders.delete": True,
        "permissions.manage": True,
        "unknown.permission": True,
        "orders.create": "yes",
    }))
    assert permissions["orders.delete"] is True
    assert permissions["permissions.manage"] is False
    assert "unknown.permission" not in permissions
    assert permissions["orders.create"] is True


def test_inactive_or_unauthenticated_users_have_no_permissions():
    assert has_permission("orders.view", user(active=False)) is False
    assert has_permission("orders.view", user(authenticated=False)) is False


def test_per_user_override_changes_effective_access():
    employee = user("employee", permissions={
        "orders.approve": False,
        "catalog.manage": True,
    })
    assert has_permission("orders.approve", employee) is False
    assert has_permission("catalog.manage", employee) is True
