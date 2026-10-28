"""Stop storing original supplier invoice file binaries.

Revision ID: 20261028_invoice_metadata_only
Revises: 20261026_user_perms
"""
from alembic import op
import sqlalchemy as sa

revision = "20261028_invoice_metadata_only"
down_revision = "20261026_user_perms"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "supplier_invoices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("supplier_invoices")}
    if "attachment_data" in columns:
        # Original file bytes are intentionally discarded. Descriptive metadata
        # columns remain available for historical traceability.
        op.drop_column("supplier_invoices", "attachment_data")


def downgrade():
    # Reintroducing the binary column does not restore deleted original files.
    op.add_column("supplier_invoices", sa.Column("attachment_data", sa.LargeBinary(), nullable=True))
