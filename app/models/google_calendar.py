from datetime import datetime, timezone

from app.extensions import db


class GoogleCalendarConnection(db.Model):
    __tablename__ = "google_calendar_connections"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "user_id", name="uq_google_calendar_tenant_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    google_email = db.Column(db.String(255), nullable=True)
    refresh_token_encrypted = db.Column(db.Text, nullable=False)
    calendar_id = db.Column(db.String(255), nullable=False, default="primary")
    calendar_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User")
    tenant = db.relationship("Tenant")

    def to_dict(self):
        return {
            "id": self.id,
            "google_email": self.google_email,
            "calendar_id": self.calendar_id,
            "calendar_name": self.calendar_name,
            "connected": True,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
