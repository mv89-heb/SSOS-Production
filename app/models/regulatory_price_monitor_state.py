from datetime import datetime, timezone
from app.extensions import db


class RegulatoryPriceMonitorState(db.Model):
    """Singleton cursor for the scheduled official egg-price announcement watcher."""
    __tablename__ = "regulatory_price_monitor_state"

    id = db.Column(db.Integer, primary_key=True)
    last_article_url = db.Column(db.String(1000), nullable=True)
    last_article_title = db.Column(db.String(500), nullable=True)
    last_published_at = db.Column(db.String(30), nullable=True)
    last_checked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "last_article_url": self.last_article_url,
            "last_article_title": self.last_article_title,
            "last_published_at": self.last_published_at,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_error": self.last_error,
        }
