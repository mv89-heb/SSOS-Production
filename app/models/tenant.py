from datetime import datetime, timezone

from app.extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    slug = db.Column(db.String(150), nullable=False, unique=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    users = db.relationship("User", back_populates="tenant", lazy="selectin")
    orders = db.relationship("Order", back_populates="tenant", lazy="selectin")

    def __repr__(self):
        return f"<Tenant {self.slug}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
