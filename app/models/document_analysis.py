from datetime import datetime, timezone

from app.extensions import db


class DocumentAnalysis(db.Model):
    """Tenant-scoped staging record for AI document extraction."""

    __tablename__ = "document_analyses"
    __table_args__ = (
        db.Index("ix_document_analysis_tenant_status", "tenant_id", "status"),
        db.Index("ix_document_analysis_tenant_created", "tenant_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    # The path exists only while the uploaded document is being analyzed.
    # It is cleared immediately after analysis and is never returned by to_dict().
    storage_path = db.Column(db.String(500), nullable=True)
    mime_type = db.Column(db.String(100), nullable=False)
    document_type = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="UPLOADED")
    extracted_data = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    provider = db.Column(db.String(50), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    analyzed_at = db.Column(db.DateTime, nullable=True)
    applied_at = db.Column(db.DateTime, nullable=True)
    applied_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    uploader = db.relationship("User", foreign_keys=[uploaded_by])
    applier = db.relationship("User", foreign_keys=[applied_by])

    def is_stale_processing(self, stale_minutes: int = 20):
        """Whether a PROCESSING row is old enough to be offered for retry."""
        if self.status != "PROCESSING" or not self.created_at:
            return False
        created = self.created_at.replace(tzinfo=timezone.utc) if self.created_at.tzinfo is None else self.created_at
        age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        return age_seconds >= stale_minutes * 60

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "status": self.status,
            "processing_stale": self.is_stale_processing(),
            "extracted_data": self.extracted_data,
            "error_message": self.error_message,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "applied_by": self.applied_by,
        }
