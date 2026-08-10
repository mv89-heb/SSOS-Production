from datetime import datetime, timezone
from app.extensions import db


class ImportRow(db.Model):
    """
    One raw row exactly as read from the uploaded file — column header ->
    cell value, as strings, completely unprocessed. Phase 3.1 never
    interprets these (no product matching, no price parsing, no
    validation) — that's the Mapping Engine and Validation Engine, both
    later sub-phases. This table exists purely so the source data survives
    intact for the user to review before any decision is made about it.
    """
    __tablename__ = "import_rows"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    import_session_id = db.Column(db.Integer, db.ForeignKey("import_sessions.id"), nullable=False, index=True)

    row_number = db.Column(db.Integer, nullable=False)  # 1-based position in the source file
    raw_data = db.Column(db.JSON, nullable=False)  # {"מוצר": "בורקס גבינה", "גידרון": "20.85", ...}
    # Phase 3.2C: the SAME row's cell values, but as a plain ordered list
    # by column position, not a dict. Needed because dict key order isn't
    # reliably preserved through JSON storage/serialization (confirmed:
    # keys can come back re-sorted), and because Analysis's own header
    # detection can label the same columns differently than this table's
    # header-text keys do (e.g. multi-tier headers). Validation aligns to
    # ImportMappingColumn.column_index against THIS list, never raw_data's
    # keys, to avoid silently misaligned data.
    raw_values = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = db.relationship("ImportSession", back_populates="rows")

    def to_dict(self):
        return {
            "id": self.id,
            "import_session_id": self.import_session_id,
            "row_number": self.row_number,
            "raw_data": self.raw_data,
            "raw_values": self.raw_values,
            "created_at": self.created_at.isoformat(),
        }
