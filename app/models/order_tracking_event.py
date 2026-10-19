from datetime import datetime, timezone

from app.extensions import db


class OrderTrackingEvent(db.Model):
    """Internal tenant-scoped manual log entry for supplier communications and follow-ups."""
    __tablename__ = "order_tracking_events"
    __table_args__ = (
        db.Index("ix_order_tracking_tenant_order_time", "tenant_id", "order_id", "occurred_at"),
        db.Index("ix_order_tracking_tenant_followup", "tenant_id", "next_follow_up_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    details = db.Column(db.Text, nullable=True)
    contact_name = db.Column(db.String(200), nullable=True)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    next_follow_up_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    order = db.relationship("Order")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "event_type": self.event_type,
            "summary": self.summary,
            "details": self.details,
            "contact_name": self.contact_name,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "next_follow_up_at": self.next_follow_up_at.isoformat() if self.next_follow_up_at else None,
            "created_by": self.created_by,
            "created_by_name": self.user.full_name if self.user else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
