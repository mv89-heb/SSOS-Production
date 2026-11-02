from datetime import datetime, timezone
from app.extensions import db


class RegulatedEggPrice(db.Model):
    """Official consumer ceiling price for a regulated 12-egg pack."""
    __tablename__ = "regulated_egg_prices"
    __table_args__ = (
        db.UniqueConstraint("effective_date", "size_code", name="uq_regulated_egg_price_effective_size"),
        db.CheckConstraint("size_code IN ('M', 'L', 'XL')", name="ck_regulated_egg_price_size"),
        db.CheckConstraint("max_consumer_price > 0", name="ck_regulated_egg_price_positive"),
        db.Index("ix_regulated_egg_price_effective", "effective_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    size_code = db.Column(db.String(2), nullable=False)
    pack_size = db.Column(db.Integer, nullable=False, default=12)
    max_consumer_price = db.Column(db.Numeric(10, 2), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    published_at = db.Column(db.Date, nullable=True)
    change_percent = db.Column(db.Numeric(6, 3), nullable=True)
    source_url = db.Column(db.String(1000), nullable=False)
    source_title = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "size_code": self.size_code,
            "pack_size": self.pack_size,
            "max_consumer_price": float(self.max_consumer_price),
            "effective_date": self.effective_date.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "change_percent": float(self.change_percent) if self.change_percent is not None else None,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
