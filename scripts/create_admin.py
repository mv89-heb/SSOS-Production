from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.tenant import Tenant

app = create_app()

with app.app_context():

    tenant = Tenant(
        name="SSOS",
        slug="ssos",
        active=True
    )

    db.session.add(tenant)
    db.session.flush()

    user = User(
        tenant_id=tenant.id,
        email="admin@ssos.com",
        full_name="System Admin",
        role="admin",
        active=True
    )

    user.set_password("Admin1234")

    db.session.add(user)
    db.session.commit()

    print("Admin created")
