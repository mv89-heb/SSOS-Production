from datetime import datetime, timezone
from app.extensions import db

FORMAT_WIDE = "WIDE"
FORMAT_TALL = "TALL"
FORMAT_MIXED = "MIXED"
FORMAT_UNKNOWN = "UNKNOWN"

VALID_FORMATS = (FORMAT_WIDE, FORMAT_TALL, FORMAT_MIXED, FORMAT_UNKNOWN)


class ImportAnalysis(db.Model):
    """
    Phase 3.2A — Import Analysis Engine. Read-only structural findings for
    ONE sheet of an uploaded workbook: header shape, orientation, per-column
    type guesses, detected suppliers/units, and data-quality issues.

    This is deliberately NOT interpretation-with-consequences: nothing here
    creates/updates a Product, Supplier, or SupplierProductOffer, and
    nothing here is read by OrderService. It exists purely so a human (or
    the future Mapping Engine) has real signal instead of assumptions.
    Re-running analysis on the same session replaces its previous rows —
    this table always reflects the most recent analysis, not a history.
    """
    __tablename__ = "import_analyses"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False, index=True)

    sheet_name = db.Column(db.String(255), nullable=False)
    sheet_index = db.Column(db.Integer, nullable=False)  # 0-based position in the workbook
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)

    row_count = db.Column(db.Integer, nullable=False)
    column_count = db.Column(db.Integer, nullable=False)

    # 1-based row number the engine believes the (first) header row starts
    # at. Null when the sheet has no detectable header at all (e.g. empty).
    header_row_index = db.Column(db.Integer, nullable=True)
    header_tier_count = db.Column(db.Integer, nullable=True)  # 1, 2, 3...
    has_merged_header_cells = db.Column(db.Boolean, default=False, nullable=False)

    detected_format = db.Column(db.String(20), default=FORMAT_UNKNOWN, nullable=False)
    format_reason = db.Column(db.Text, nullable=True)

    # [{index, header, detected_type, confidence, reason}, ...]
    columns = db.Column(db.JSON, nullable=True)
    # [{column_index, header, matched_supplier_id, matched_supplier_name}, ...]
    detected_suppliers = db.Column(db.JSON, nullable=True)
    # ["קילו", "יחידה", ...]
    detected_units = db.Column(db.JSON, nullable=True)
    # structured findings — see ImportAnalysisService._detect_data_quality
    data_quality = db.Column(db.JSON, nullable=True)
    # plain-language warnings surfaced directly to the user
    warnings = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = db.relationship("ImportSession", back_populates="analyses")

    def to_dict(self):
        return {
            "id": self.id,
            "import_session_id": self.import_session_id,
            "sheet_name": self.sheet_name,
            "sheet_index": self.sheet_index,
            "is_hidden": self.is_hidden,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "header_row_index": self.header_row_index,
            "header_tier_count": self.header_tier_count,
            "has_merged_header_cells": self.has_merged_header_cells,
            "detected_format": self.detected_format,
            "format_reason": self.format_reason,
            "columns": self.columns,
            "detected_suppliers": self.detected_suppliers,
            "detected_units": self.detected_units,
            "data_quality": self.data_quality,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
        }
