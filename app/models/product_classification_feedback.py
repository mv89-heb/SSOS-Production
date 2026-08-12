from datetime import datetime, timezone

from app.extensions import db


class ProductClassificationFeedback(db.Model):
    __tablename__ = "product_classification_feedback"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    normalized_name = db.Column(db.String(255), nullable=False, index=True)
    predicted_category = db.Column(db.String(100), nullable=True)
    actual_category = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(30), nullable=False, default="USER")
    confidence = db.Column(db.Numeric(5, 4), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product", back_populates="classification_feedback")
