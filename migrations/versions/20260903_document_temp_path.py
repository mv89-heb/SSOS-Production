"""allow document analysis temp paths to be cleared

Revision ID: 20260903_document_temp_path
Revises: 20260903_document_intelligence
"""
from alembic import op
import sqlalchemy as sa

revision = "20260903_document_temp_path"
down_revision = "20260903_document_intelligence"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("document_analyses")}
    if "storage_path" in columns and columns["storage_path"].get("nullable") is False:
        op.alter_column(
            "document_analyses",
            "storage_path",
            existing_type=sa.String(length=500),
            nullable=True,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("document_analyses")}
    if "storage_path" in columns:
        op.execute(
            sa.text(
                "UPDATE document_analyses SET storage_path = '' "
                "WHERE storage_path IS NULL"
            )
        )
        op.alter_column(
            "document_analyses",
            "storage_path",
            existing_type=sa.String(length=500),
            nullable=False,
        )
