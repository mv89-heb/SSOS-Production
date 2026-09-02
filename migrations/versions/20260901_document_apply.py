"""add document apply metadata
Revision ID: 20260901_document_apply
Revises: 20260901_document_intelligence
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_document_apply"
down_revision = "20260901_document_intelligence"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("document_analyses")}
    if "applied_at" not in columns:
        op.add_column("document_analyses", sa.Column("applied_at", sa.DateTime(), nullable=True))
    if "applied_by" not in columns:
        op.add_column("document_analyses", sa.Column("applied_by", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_document_analyses_applied_by", "document_analyses", "users", ["applied_by"], ["id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("document_analyses")}
    if "applied_by" in columns:
        try:
            op.drop_constraint("fk_document_analyses_applied_by", "document_analyses", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("document_analyses", "applied_by")
    if "applied_at" in columns:
        op.drop_column("document_analyses", "applied_at")
