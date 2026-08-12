from datetime import datetime, timezone
from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.Index(
            "uq_products_tenant_sku",
            "tenant_id",
            "sku",
            unique=True,
            postgresql_where=db.text("sku IS NOT NULL AND btrim(sku) <> ''"),
            sqlite_where=db.text("sku IS NOT NULL AND trim(sku) <> ''"),
        ),
        db.Index(
            "uq_products_tenant_barcode",
            "tenant_id",
            "barcode",
            unique=True,
            postgresql_where=db.text("barcode IS NOT NULL AND btrim(barcode) <> ''"),
            sqlite_where=db.text("barcode IS NOT NULL AND trim(barcode) <> ''"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    sku = db.Column(db.String(100), index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    current_price = db.Column(db.Numeric(12, 2), default=0.0, nullable=False)
    currency = db.Column(db.String(3), default="ILS", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    image_url = db.Column(db.String(500), nullable=True)
    barcode = db.Column(db.String(64), nullable=True, index=True)
    category = db.Column(db.String(100), nullable=True, index=True)
    category_source = db.Column(db.String(30), nullable=True)
    category_confidence = db.Column(db.Numeric(5, 4), nullable=True)
    category_reviewed = db.Column(db.Boolean, nullable=False, default=False)
    unit = db.Column(db.String(50), nullable=True)
    units_per_carton = db.Column(db.Integer, nullable=True)
    supplier_sku = db.Column(db.String(100), nullable=True)
    current_stock = db.Column(db.Integer, nullable=True)
    min_stock = db.Column(db.Integer, nullable=True)
    recommended_stock = db.Column(db.Integer, nullable=True)

    supplier = db.relationship("Supplier", back_populates="products")
    supplier_offers = db.relationship(
        "SupplierProductOffer", back_populates="product", cascade="all, delete-orphan"
    )
    classification_feedback = db.relationship(
        "ProductClassificationFeedback", back_populates="product", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "current_price": float(self.current_price),
            "currency": self.currency,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "image_url": self.image_url,
            "barcode": self.barcode,
            "category": self.category,
            "category_source": self.category_source,
            "category_confidence": float(self.category_confidence) if self.category_confidence is not None else None,
            "category_reviewed": self.category_reviewed,
            "unit": self.unit,
            "units_per_carton": self.units_per_carton,
            "supplier_sku": self.supplier_sku,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "recommended_stock": self.recommended_stock,
        }
