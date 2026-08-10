from datetime import datetime, timezone
from app.extensions import db

# Pipeline: UPLOADED -> MAPPING -> VALIDATING -> READY_FOR_APPROVAL -> IMPORTED
#           (any state) -> FAILED
# Phase 3.1 only ever produces UPLOADED or FAILED — later phases add the
# MAPPING/VALIDATING/READY_FOR_APPROVAL/IMPORTED transitions.
STATUS_UPLOADED = "UPLOADED"
STATUS_MAPPING = "MAPPING"
STATUS_VALIDATING = "VALIDATING"
STATUS_READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
STATUS_IMPORTED = "IMPORTED"
STATUS_FAILED = "FAILED"

VALID_STATUSES = (
    STATUS_UPLOADED, STATUS_MAPPING, STATUS_VALIDATING,
    STATUS_READY_FOR_APPROVAL, STATUS_IMPORTED, STATUS_FAILED,
)


class ImportSession(db.Model):
    """
    One uploaded price-list file, staged for review before anything is
    ever written to products/suppliers/offers. This table (plus ImportRow)
    IS the staging layer — Production tables are only touched by a later
    phase's explicit "Approve" step, never by upload or parsing alone.
    """
    __tablename__ = "import_sessions"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=False)  # original filename, as uploaded
    storage_path = db.Column(db.String(500), nullable=True)  # where the raw file was saved on disk
    # Optional: set when the whole file is known up front to be a single
    # supplier's price list (e.g. "אנג'ל", tall format). Wide-format files
    # comparing several suppliers per row (e.g. "גידרון") leave this null —
    # there's no single "the" supplier for those; each column maps to its
    # own supplier in the (future) Mapping Engine step.
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    status = db.Column(db.String(30), default=STATUS_UPLOADED, nullable=False)
    error_message = db.Column(db.Text, nullable=True)

    # Phase 3.1: which sheet was actually resolved/staged into ImportRow
    # (may differ from the requested sheet_name if that name didn't exist
    # in the file — see ImportService._parse_xlsx/_parse_xls fallback to
    # the first sheet). Needed by Phase 3.2B to link the Mapping workspace
    # to the matching ImportAnalysis row for this same sheet.
    staged_sheet_name = db.Column(db.String(255), nullable=True)

    # Populated once the file has been parsed into ImportRow — convenience
    # fields so the (future) mapping UI doesn't need to load every row just
    # to know the shape of the file.
    column_headers = db.Column(db.JSON, nullable=True)
    row_count = db.Column(db.Integer, nullable=True)

    # Phase 3.2A: populated by ImportAnalysisService.analyze() — workbook-
    # level facts that don't belong to any single sheet. Null until
    # analysis has been run at least once.
    workbook_sheet_names = db.Column(db.JSON, nullable=True)
    workbook_sheet_count = db.Column(db.Integer, nullable=True)
    # Which sheet was selected/focused when the file was last saved in
    # Excel. Only reliably available for .xlsx (openpyxl exposes
    # wb.active) — stays null for .xls/.csv, where this isn't tracked.
    workbook_active_sheet = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    supplier = db.relationship("Supplier")
    uploader = db.relationship("User")
    rows = db.relationship("ImportRow", back_populates="session", cascade="all, delete-orphan")
    analyses = db.relationship("ImportAnalysis", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self, include_headers=True):
        data = {
            "id": self.id,
            "filename": self.filename,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "uploaded_by": self.uploaded_by,
            "uploaded_by_name": self.uploader.full_name if self.uploader else None,
            "status": self.status,
            "error_message": self.error_message,
            "row_count": self.row_count,
            "workbook_sheet_names": self.workbook_sheet_names,
            "workbook_sheet_count": self.workbook_sheet_count,
            "workbook_active_sheet": self.workbook_active_sheet,
            "staged_sheet_name": self.staged_sheet_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_headers:
            data["column_headers"] = self.column_headers
        return data
