from datetime import datetime, timezone

from app.extensions import db


class SavedOrderSearch(db.Model):
    __tablename__ = "saved_order_searches"
    __table_args__ = (
        db.UniqueConstraint(
            "tenant_id", "user_id", "name",
            name="uq_saved_order_searches_tenant_user_name",
        ),
        db.Index(
            "ix_saved_order_searches_tenant_user_updated",
            "tenant_id", "user_id", "updated_at",
        ),
        db.CheckConstraint("length(name) > 0", name="ck_saved_order_searches_name_nonempty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    filters = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "filters": self.filters or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
