import pytest
from werkzeug.exceptions import Conflict

from app.models.supplier import Supplier
from app.models.user import ROLE_ADMIN, ROLE_EMPLOYEE, User
from app.services.admin_service import AdminService


def test_admin_cannot_delete_self(app, admin_user):
    with app.app_context():
        service = AdminService(admin_user.tenant_id, admin_user.id)
        with pytest.raises(Conflict):
            service.delete_user(admin_user.id)


def test_admin_can_deactivate_employee(app, admin_user, employee_user):
    with app.app_context():
        service = AdminService(admin_user.tenant_id, admin_user.id)
        user = service.deactivate_user(employee_user.id)
        assert user.active is False


def test_last_active_admin_is_protected(app, admin_user):
    with app.app_context():
        service = AdminService(admin_user.tenant_id, admin_user.id)
        with pytest.raises(Conflict):
            service.deactivate_user(admin_user.id)


def test_supplier_with_products_is_deactivated_not_deleted(app, admin_user, supplier, product):
    with app.app_context():
        service = AdminService(admin_user.tenant_id, admin_user.id)
        updated = service.deactivate_supplier(supplier.id)
        assert updated.active is False
        assert product.active is False
