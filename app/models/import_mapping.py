from datetime import datetime, timezone
from app.extensions import db

# --- Mapping status -------------------------------------------------------
MAPPING_STATUS_DRAFT = "DRAFT"
MAPPING_STATUS_APPROVED = "APPROVED"
VALID_MAPPING_STATUSES = (MAPPING_STATUS_DRAFT, MAPPING_STATUS_APPROVED)

# --- Mapping targets --------------------------------------------------------
# Product fields
TARGET_PRODUCT_NAME = "PRODUCT_NAME"
TARGET_PRODUCT_CODE = "PRODUCT_CODE"
TARGET_BARCODE = "BARCODE"
TARGET_CATEGORY = "CATEGORY"
TARGET_UNIT = "UNIT"
# Supplier fields (TALL format: one column names the supplier itself)
TARGET_SUPPLIER_NAME = "SUPPLIER_NAME"
TARGET_SUPPLIER_CODE = "SUPPLIER_CODE"
# Pricing fields (TALL format: this sheet is already one supplier's price list)
TARGET_PRICE = "PRICE"
TARGET_PRICE_BEFORE_VAT = "PRICE_BEFORE_VAT"
TARGET_PRICE_AFTER_VAT = "PRICE_AFTER_VAT"
TARGET_DISCOUNT_PRICE = "DISCOUNT_PRICE"
# WIDE format: this column IS a specific supplier's price for the product
# named elsewhere in the row — carries its own supplier + price-type choice
# (see ImportMappingColumn.supplier_id/supplier_name/price_type).
TARGET_SUPPLIER_OFFER = "SUPPLIER_OFFER"
# Explicitly not part of the import
TARGET_IGNORE = "IGNORE"

VALID_TARGETS = (
    TARGET_PRODUCT_NAME, TARGET_PRODUCT_CODE, TARGET_BARCODE, TARGET_CATEGORY, TARGET_UNIT,
    TARGET_SUPPLIER_NAME, TARGET_SUPPLIER_CODE,
    TARGET_PRICE, TARGET_PRICE_BEFORE_VAT, TARGET_PRICE_AFTER_VAT, TARGET_DISCOUNT_PRICE,
    TARGET_SUPPLIER_OFFER, TARGET_IGNORE,
)

# Price "flavor" for a SUPPLIER_OFFER column specifically
PRICE_TYPE_REGULAR = "regular"
PRICE_TYPE_BEFORE_VAT = "before_vat"
PRICE_TYPE_AFTER_VAT = "after_vat"
PRICE_TYPE_DISCOUNT = "discount"
VALID_PRICE_TYPES = (PRICE_TYPE_REGULAR, PRICE_TYPE_BEFORE_VAT, PRICE_TYPE_AFTER_VAT, PRICE_TYPE_DISCOUNT)


class ImportMapping(db.Model):
    """
    Phase 3.2B — Mapping Engine. One mapping workspace for ONE sheet of ONE
    ImportSession (the sheet actually staged into ImportRow — see
    ImportSession.staged_sheet_name). Holds the overall review status;
    the actual per-column decisions live in ImportMappingColumn.

    Still write-nothing-to-production: approving a mapping only means "a
    person has confirmed how these columns should be interpreted" — it
    does not create a single Product, Supplier, or SupplierProductOffer.
    That's Phase 3.2D (Import Execution Engine), deliberately not this one.
    """
    __tablename__ = "import_mappings"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False, index=True)
    import_analysis_id = db.Column(db.Integer, db.ForeignKey("import_analyses.id"), nullable=True)

    sheet_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default=MAPPING_STATUS_DRAFT, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    session = db.relationship("ImportSession")
    columns = db.relationship(
        "ImportMappingColumn", back_populates="mapping",
        cascade="all, delete-orphan", order_by="ImportMappingColumn.column_index",
    )
    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])

    def to_dict(self):
        return {
            "id": self.id,
            "import_session_id": self.import_session_id,
            "import_analysis_id": self.import_analysis_id,
            "sheet_name": self.sheet_name,
            "status": self.status,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "approved_by": self.approved_by,
            "approved_by_name": self.approver.full_name if self.approver else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "columns": [c.to_dict() for c in self.columns],
        }


class ImportMappingColumn(db.Model):
    """
    One column's mapping decision within an ImportMapping. Starts out
    holding ONLY the engine's suggestion (from ImportAnalysis); a person
    reviews and may override any of it via the mapping API. `user_reviewed`
    tracks whether a person has actually looked at this column yet (per
    spec's "User Decision: Confirm/Change" — both count as reviewed).
    """
    __tablename__ = "import_mapping_columns"
    __table_args__ = (
        db.UniqueConstraint("import_mapping_id", "column_index", name="uq_mapping_column_index"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_mapping_id = db.Column(db.Integer, db.ForeignKey("import_mappings.id"), nullable=False, index=True)

    column_index = db.Column(db.Integer, nullable=False)
    column_header = db.Column(db.String(255), nullable=False)

    # The engine's suggestion — never mutated after creation, so a person
    # can always see "what the system originally thought" even after
    # overriding it.
    suggested_target = db.Column(db.String(30), nullable=False)
    suggested_confidence = db.Column(db.String(10), nullable=False)  # high/medium/low/none
    suggested_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    suggested_supplier_name = db.Column(db.String(255), nullable=True)
    suggested_price_type = db.Column(db.String(20), nullable=True)

    # The final decision — defaults to the suggestion at creation time;
    # overwritten when a person confirms or changes it via the API.
    final_target = db.Column(db.String(30), nullable=False)
    final_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    final_supplier_name = db.Column(db.String(255), nullable=True)
    final_price_type = db.Column(db.String(20), nullable=True)

    user_reviewed = db.Column(db.Boolean, default=False, nullable=False)

    mapping = db.relationship("ImportMapping", back_populates="columns")
    suggested_supplier = db.relationship("Supplier", foreign_keys=[suggested_supplier_id])
    final_supplier = db.relationship("Supplier", foreign_keys=[final_supplier_id])

    def to_dict(self):
        return {
            "id": self.id,
            "column_index": self.column_index,
            "column_header": self.column_header,
            "suggested_target": self.suggested_target,
            "suggested_confidence": self.suggested_confidence,
            "suggested_supplier_id": self.suggested_supplier_id,
            "suggested_supplier_name": self.suggested_supplier_name,
            "suggested_price_type": self.suggested_price_type,
            "final_target": self.final_target,
            "final_supplier_id": self.final_supplier_id,
            "final_supplier_name": self.final_supplier_name,
            "final_price_type": self.final_price_type,
            "user_reviewed": self.user_reviewed,
            "changed_from_suggestion": (
                self.final_target != self.suggested_target
                or self.final_supplier_id != self.suggested_supplier_id
                or self.final_supplier_name != self.suggested_supplier_name
                or self.final_price_type != self.suggested_price_type
            ),
        }


class ImportMappingTemplate(db.Model):
    """
    A saved, reusable column-mapping decision set, keyed by column HEADER
    TEXT (not index — a later file's columns may be reordered). Optionally
    tied to a specific supplier; a generic template has supplier_id=None.
    Applying a template never writes to production — it only pre-fills an
    ImportMappingColumn's final_* fields, still fully editable afterward.
    """
    __tablename__ = "import_mapping_templates"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    name = db.Column(db.String(255), nullable=False)
    source_filename = db.Column(db.String(255), nullable=True)  # original filename it was saved from, for match suggestions
    # {"<header text>": {"target": ..., "supplier_id": ..., "supplier_name": ..., "price_type": ...}, ...}
    column_mapping = db.Column(db.JSON, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    supplier = db.relationship("Supplier")
    creator = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "name": self.name,
            "source_filename": self.source_filename,
            "column_mapping": self.column_mapping,
            "created_by": self.created_by,
            "created_by_name": self.creator.full_name if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
