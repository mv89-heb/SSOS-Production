from datetime import datetime, timezone

from app.extensions import db


class HistoricalImportBatch(db.Model):
    """One-time tenant-scoped import of historical supplier documents."""

    __tablename__ = "historical_import_batches"
    __table_args__ = (
        db.Index("ix_historical_import_batches_tenant_created", "tenant_id", "created_at"),
        db.Index("ix_historical_import_batches_tenant_status", "tenant_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="review", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finalized_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    finalized_at = db.Column(db.DateTime(timezone=True), nullable=True)

    documents = db.relationship("HistoricalDocumentRecord", back_populates="batch", cascade="all, delete-orphan", order_by="HistoricalDocumentRecord.id")
    orders = db.relationship("HistoricalPurchaseOrder", back_populates="batch", cascade="all, delete-orphan", order_by="HistoricalPurchaseOrder.id")

    def to_dict(self, include_documents=False):
        result = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finalized_by": self.finalized_by,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "document_count": len(self.documents),
            "order_count": len(self.orders),
            "orders": [order.to_dict() for order in self.orders],
        }
        if include_documents:
            result["documents"] = [document.to_dict() for document in self.documents]
        return result


class HistoricalPurchaseOrder(db.Model):
    """Isolated historical order record; never participates in operational workflows."""

    __tablename__ = "historical_purchase_orders"
    __table_args__ = (
        db.Index("ix_historical_purchase_orders_tenant_date", "tenant_id", "order_date"),
        db.Index("ix_historical_purchase_orders_tenant_supplier", "tenant_id", "supplier_id"),
        db.Index("ix_historical_purchase_orders_batch", "batch_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("historical_import_batches.id", ondelete="CASCADE"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_name = db.Column(db.String(255), nullable=False)
    order_reference = db.Column(db.String(160), nullable=True)
    order_date = db.Column(db.Date, nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    total_amount = db.Column(db.Numeric(12, 2), nullable=True)
    items = db.Column(db.JSON, nullable=False, default=list)
    source_document_ids = db.Column(db.JSON, nullable=False, default=list)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    batch = db.relationship("HistoricalImportBatch", back_populates="orders")
    documents = db.relationship("HistoricalDocumentRecord", back_populates="historical_order")

    def to_dict(self):
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "order_reference": self.order_reference,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "currency": self.currency,
            "total_amount": float(self.total_amount) if self.total_amount is not None else None,
            "items": self.items or [],
            "source_document_ids": self.source_document_ids or [],
            "document_count": len(self.documents),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "historical_only": True,
        }


class HistoricalDocumentRecord(db.Model):
    """Extracted document metadata and fields; original bytes are never stored here."""

    __tablename__ = "historical_document_records"
    __table_args__ = (
        db.UniqueConstraint("tenant_id", "batch_id", "analysis_id", name="uq_historical_document_analysis"),
        db.Index("ix_historical_document_tenant_type_number", "tenant_id", "document_type", "document_number"),
        db.Index("ix_historical_document_tenant_supplier_date", "tenant_id", "supplier_id", "document_date"),
        db.Index("ix_historical_document_batch", "batch_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("historical_import_batches.id", ondelete="CASCADE"), nullable=False)
    analysis_id = db.Column(db.Integer, db.ForeignKey("document_analyses.id"), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    source_filename = db.Column(db.String(255), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_name = db.Column(db.String(255), nullable=True)
    document_number = db.Column(db.String(160), nullable=True)
    document_date = db.Column(db.Date, nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    total_amount = db.Column(db.Numeric(12, 2), nullable=True)
    extracted_data = db.Column(db.JSON, nullable=False, default=dict)
    order_reference = db.Column(db.String(160), nullable=True)
    needs_review = db.Column(db.Boolean, nullable=False, default=False)
    review_reasons = db.Column(db.JSON, nullable=False, default=list)
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey("historical_document_records.id"), nullable=True)
    historical_order_id = db.Column(db.Integer, db.ForeignKey("historical_purchase_orders.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    batch = db.relationship("HistoricalImportBatch", back_populates="documents")
    historical_order = db.relationship("HistoricalPurchaseOrder", back_populates="documents")
    analysis = db.relationship("DocumentAnalysis")
    duplicate_of = db.relationship("HistoricalDocumentRecord", remote_side=[id], uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "analysis_id": self.analysis_id,
            "document_type": self.document_type,
            "source_filename": self.source_filename,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier_name,
            "document_number": self.document_number,
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "currency": self.currency,
            "total_amount": float(self.total_amount) if self.total_amount is not None else None,
            "extracted_data": self.extracted_data or {},
            "order_reference": self.order_reference,
            "needs_review": self.needs_review,
            "review_reasons": self.review_reasons or [],
            "duplicate_of_id": self.duplicate_of_id,
            "historical_order_id": self.historical_order_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
