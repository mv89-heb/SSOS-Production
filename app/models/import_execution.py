from datetime import datetime, timezone
from app.extensions import db

EXECUTION_STATUS_COMMITTED = "COMMITTED"
EXECUTION_STATUS_ROLLED_BACK = "ROLLED_BACK"
VALID_EXECUTION_STATUSES = (EXECUTION_STATUS_COMMITTED, EXECUTION_STATUS_ROLLED_BACK)


class ImportExecution(db.Model):
    """
    Phase 3.2D-MVP — Import Execution Engine. Records exactly what a single
    commit did: which Suppliers/Products/SupplierProductOffers it created,
    which Products it updated (and their old prices, for rollback), and
    any rows it had to skip. This is the only phase in the whole import
    pipeline that writes to products/suppliers/supplier_product_offers —
    and it only ever does so via CatalogService's existing validated,
    audited write methods, never by touching those tables directly.
    """
    __tablename__ = "import_executions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False, index=True)
    import_validation_id = db.Column(db.Integer, db.ForeignKey("import_validations.id"), nullable=False)

    status = db.Column(db.String(20), default=EXECUTION_STATUS_COMMITTED, nullable=False)

    # Before-state, captured right before writing anything — lets the
    # summary show a clear delta (per spec's "Snapshot" requirement).
    snapshot_suppliers_before = db.Column(db.Integer, nullable=False)
    snapshot_products_before = db.Column(db.Integer, nullable=False)
    snapshot_offers_before = db.Column(db.Integer, nullable=False)

    suppliers_created = db.Column(db.Integer, default=0, nullable=False)
    products_created = db.Column(db.Integer, default=0, nullable=False)
    products_updated = db.Column(db.Integer, default=0, nullable=False)
    offers_created = db.Column(db.Integer, default=0, nullable=False)

    # IDs of everything this execution created — the basis for rollback.
    created_supplier_ids = db.Column(db.JSON, nullable=False, default=list)
    created_product_ids = db.Column(db.JSON, nullable=False, default=list)
    created_offer_ids = db.Column(db.JSON, nullable=False, default=list)
    # [{"product_id": int, "old_price": float, "new_price": float}, ...] —
    # updated (not created) products need their OLD price to roll back,
    # not just deletion.
    price_history = db.Column(db.JSON, nullable=False, default=list)
    # [{"row_number": int, "reason": str}, ...] — rows Validation approved
    # but that hit an unexpected error at actual write time.
    skipped_rows = db.Column(db.JSON, nullable=False, default=list)

    executed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    executed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    rolled_back_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rolled_back_at = db.Column(db.DateTime, nullable=True)

    session = db.relationship("ImportSession")
    validation = db.relationship("ImportValidation")

    def to_dict(self):
        return {
            "id": self.id,
            "import_session_id": self.import_session_id,
            "import_validation_id": self.import_validation_id,
            "status": self.status,
            "snapshot_before": {
                "suppliers": self.snapshot_suppliers_before,
                "products": self.snapshot_products_before,
                "offers": self.snapshot_offers_before,
            },
            "summary": {
                "suppliers_created": self.suppliers_created,
                "products_created": self.products_created,
                "products_updated": self.products_updated,
                "offers_created": self.offers_created,
            },
            "created_supplier_ids": self.created_supplier_ids,
            "created_product_ids": self.created_product_ids,
            "created_offer_ids": self.created_offer_ids,
            "price_history": self.price_history,
            "skipped_rows": self.skipped_rows,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at.isoformat(),
            "rolled_back_by": self.rolled_back_by,
            "rolled_back_at": self.rolled_back_at.isoformat() if self.rolled_back_at else None,
        }
