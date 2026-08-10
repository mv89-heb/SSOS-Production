from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_EMPLOYEE = "employee"
VALID_ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE)

# Coarse role ranking used for "at least this role" checks.
ROLE_RANK = {ROLE_EMPLOYEE: 1, ROLE_MANAGER: 2, ROLE_ADMIN: 3}


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)

    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_EMPLOYEE)
    active = db.Column(db.Boolean, default=True, nullable=False)

    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    tenant = db.relationship("Tenant", back_populates="users")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_role_at_least(self, minimum_role: str) -> bool:
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK.get(minimum_role, 99)

    # Flask-Login integration
    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.active

    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.email} tenant={self.tenant_id}>"
