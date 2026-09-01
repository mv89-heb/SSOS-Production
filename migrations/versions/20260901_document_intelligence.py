"""add document intelligence staging

Revision ID: 20260901_document_intelligence
Revises: 20260901_price_observations
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_document_intelligence"
down_revision = "20260901_price_observations"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_analyses" in inspector.get_table_names():
        return
    op.create_table(
        "document_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="UPLOADED"),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_document_analysis_tenant_id", "document_analyses", ["tenant_id"])
    op.create_index("ix_document_analysis_tenant_status", "document_analyses", ["tenant_id", "status"])
    op.create_index("ix_document_analysis_tenant_created", "document_analyses", ["tenant_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_analyses" not in inspector.get_table_names():
        return
    for name in ("ix_document_analysis_tenant_created", "ix_document_analysis_tenant_status", "ix_document_analysis_tenant_id"):
        op.drop_index(name, table_name="document_analyses")
    op.drop_table("document_analyses")
