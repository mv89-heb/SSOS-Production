from datetime import datetime, timezone
from app.extensions import db

# --- Validation run status --------------------------------------------------
VALIDATION_STATUS_COMPLETED = "COMPLETED"
VALIDATION_STATUS_FAILED = "FAILED"
VALID_VALIDATION_STATUSES = (VALIDATION_STATUS_COMPLETED, VALIDATION_STATUS_FAILED)

# --- Per-row product/supplier actions --------------------------------------
ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_SKIP = "SKIP"
ACTION_EXISTING = "EXISTING"  # supplier already exists, nothing to change
ACTION_ERROR = "ERROR"  # row couldn't be interpreted at all (e.g. no product name)
VALID_ACTIONS = (ACTION_CREATE, ACTION_UPDATE, ACTION_SKIP, ACTION_EXISTING, ACTION_ERROR)

# --- Issue severity ----------------------------------------------------------
SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
VALID_SEVERITIES = (SEVERITY_ERROR, SEVERITY_WARNING)


class ImportValidation(db.Model):
    """
    Phase 3.2C — Validation & Import Preview Engine. One run per (session,
    mapping): interprets every raw ImportRow through the APPROVED mapping,
    checks it against the real catalog for duplicates, and computes what
    WOULD happen — without creating/updating a single Product, Supplier,
    or SupplierProductOffer. That commit step is Phase 3.2D (Import
    Execution Engine), deliberately not this one.

    Re-running validation on the same session replaces its previous
    ImportPreview/ImportIssue rows — this always reflects the latest run,
    not a history (mirrors ImportAnalysis's re-run behavior).
    """
    __tablename__ = "import_validations"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False, index=True)
    import_mapping_id = db.Column(db.Integer, db.ForeignKey("import_mappings.id"), nullable=False)

    status = db.Column(db.String(20), default=VALIDATION_STATUS_COMPLETED, nullable=False)
    error_message = db.Column(db.Text, nullable=True)  # set only if status == FAILED

    # Summary counts — computed once at validation time and stored, so
    # GET /validation doesn't need to re-aggregate ImportPreview every call.
    products_to_create = db.Column(db.Integer, default=0, nullable=False)
    products_to_update = db.Column(db.Integer, default=0, nullable=False)
    products_to_skip = db.Column(db.Integer, default=0, nullable=False)
    suppliers_to_create = db.Column(db.Integer, default=0, nullable=False)
    offers_to_create = db.Column(db.Integer, default=0, nullable=False)
    offers_to_update = db.Column(db.Integer, default=0, nullable=False)
    warning_count = db.Column(db.Integer, default=0, nullable=False)
    error_count = db.Column(db.Integer, default=0, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = db.relationship("ImportSession")
    mapping = db.relationship("ImportMapping")
    preview_rows = db.relationship(
        "ImportPreview", back_populates="validation",
        cascade="all, delete-orphan", order_by="ImportPreview.row_number",
    )
    issues = db.relationship(
        "ImportIssue", back_populates="validation",
        cascade="all, delete-orphan", order_by="ImportIssue.row_number",
    )

    def to_dict(self, include_rows=False):
        data = {
            "id": self.id,
            "import_session_id": self.import_session_id,
            "import_mapping_id": self.import_mapping_id,
            "status": self.status,
            "error_message": self.error_message,
            "summary": {
                "products": {
                    "created": self.products_to_create,
                    "updated": self.products_to_update,
                    "skipped": self.products_to_skip,
                },
                "suppliers": {"created": self.suppliers_to_create},
                "offers": {"created": self.offers_to_create, "updated": self.offers_to_update},
                "warnings": self.warning_count,
                "errors": self.error_count,
            },
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }
        if include_rows:
            data["preview_rows"] = [r.to_dict() for r in self.preview_rows]
            data["issues"] = [i.to_dict() for i in self.issues]
        return data


class ImportPreview(db.Model):
    """
    One interpreted row: what this ImportRow WOULD become if committed.
    product_action/supplier_action describe the single "primary" listing
    (TALL format: the row's own product+supplier+price; WIDE format: the
    cheapest of the row's SUPPLIER_OFFER columns — see
    ImportValidationService for why). `offers` carries every
    SUPPLIER_OFFER column's interpretation, including the one chosen as
    primary, so the preview UI can show the full picture per row.
    """
    __tablename__ = "import_previews"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_validation_id = db.Column(db.Integer, db.ForeignKey("import_validations.id"), nullable=False, index=True)

    row_number = db.Column(db.Integer, nullable=False)  # matches ImportRow.row_number

    product_action = db.Column(db.String(10), nullable=False)
    product_name = db.Column(db.String(255), nullable=True)
    matched_product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(100), nullable=True)

    supplier_action = db.Column(db.String(10), nullable=True)
    supplier_name = db.Column(db.String(255), nullable=True)
    matched_supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    price = db.Column(db.Numeric(12, 2), nullable=True)
    old_price = db.Column(db.Numeric(12, 2), nullable=True)  # only set when product_action == UPDATE

    # [{supplier_name, matched_supplier_id, price, price_type, action}, ...]
    offers = db.Column(db.JSON, nullable=True)

    has_errors = db.Column(db.Boolean, default=False, nullable=False)
    has_warnings = db.Column(db.Boolean, default=False, nullable=False)

    validation = db.relationship("ImportValidation", back_populates="preview_rows")
    matched_product = db.relationship("Product")
    matched_supplier = db.relationship("Supplier")

    def to_dict(self):
        return {
            "id": self.id,
            "row_number": self.row_number,
            "product_action": self.product_action,
            "product_name": self.product_name,
            "matched_product_id": self.matched_product_id,
            "unit": self.unit,
            "category": self.category,
            "supplier_action": self.supplier_action,
            "supplier_name": self.supplier_name,
            "matched_supplier_id": self.matched_supplier_id,
            "price": float(self.price) if self.price is not None else None,
            "old_price": float(self.old_price) if self.old_price is not None else None,
            "offers": self.offers,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
        }


class ImportIssue(db.Model):
    """One validation finding — an error blocks that row's action from
    being anything but SKIP/ERROR; a warning is informational and doesn't
    change what would happen, but flags something a person should look at
    (e.g. an unusual price jump, a non-standard unit spelling)."""
    __tablename__ = "import_issues"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_validation_id = db.Column(db.Integer, db.ForeignKey("import_validations.id"), nullable=False, index=True)

    row_number = db.Column(db.Integer, nullable=True)  # null for a workbook/mapping-level issue, not tied to one row
    field = db.Column(db.String(100), nullable=True)
    severity = db.Column(db.String(10), nullable=False)
    code = db.Column(db.String(50), nullable=False)  # e.g. "missing_product_name", "duplicate_barcode"
    message = db.Column(db.Text, nullable=False)

    validation = db.relationship("ImportValidation", back_populates="issues")

    def to_dict(self):
        return {
            "id": self.id,
            "row_number": self.row_number,
            "field": self.field,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
