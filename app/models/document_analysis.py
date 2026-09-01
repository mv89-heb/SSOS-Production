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
    storage_path = db.Column(db.String(500), nullable=False)
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

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "status": self.status,
            "extracted_data": self.extracted_data,
            "error_message": self.error_message,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "applied_by": self.applied_by,
        }
