"""Add isolated historical document import records.

Revision ID: 20261028_hist_doc_import
Revises: 20261028_invoice_metadata_only
"""
from alembic import op
import sqlalchemy as sa


revision = "20261028_hist_doc_import"
down_revision = "20261028_invoice_metadata_only"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="review"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finalized_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_historical_import_batches_tenant_id", "historical_import_batches", ["tenant_id"])
    op.create_index("ix_historical_import_batches_status", "historical_import_batches", ["status"])
    op.create_index("ix_historical_import_batches_tenant_created", "historical_import_batches", ["tenant_id", "created_at"])
    op.create_index("ix_historical_import_batches_tenant_status", "historical_import_batches", ["tenant_id", "status"])

    op.create_table(
        "historical_purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("historical_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("order_reference", sa.String(length=160), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("source_document_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_historical_purchase_orders_tenant_id", "historical_purchase_orders", ["tenant_id"])
    op.create_index("ix_historical_purchase_orders_supplier_id", "historical_purchase_orders", ["supplier_id"])
    op.create_index("ix_historical_purchase_orders_tenant_date", "historical_purchase_orders", ["tenant_id", "order_date"])
    op.create_index("ix_historical_purchase_orders_tenant_supplier", "historical_purchase_orders", ["tenant_id", "supplier_id"])
    op.create_index("ix_historical_purchase_orders_batch", "historical_purchase_orders", ["batch_id"])

    op.create_table(
        "historical_document_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("historical_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("document_analyses.id"), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("document_number", sa.String(length=160), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ILS"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("order_reference", sa.String(length=160), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("duplicate_of_id", sa.Integer(), sa.ForeignKey("historical_document_records.id"), nullable=True),
        sa.Column("historical_order_id", sa.Integer(), sa.ForeignKey("historical_purchase_orders.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "batch_id", "analysis_id", name="uq_historical_document_analysis"),
    )
    op.create_index("ix_historical_document_records_tenant_id", "historical_document_records", ["tenant_id"])
    op.create_index("ix_historical_document_records_supplier_id", "historical_document_records", ["supplier_id"])
    op.create_index("ix_historical_document_records_batch_id", "historical_document_records", ["batch_id"])
    op.create_index("ix_historical_document_tenant_type_number", "historical_document_records", ["tenant_id", "document_type", "document_number"])
    op.create_index("ix_historical_document_tenant_supplier_date", "historical_document_records", ["tenant_id", "supplier_id", "document_date"])
    op.create_index("ix_historical_document_batch", "historical_document_records", ["batch_id"])


def downgrade():
    op.drop_index("ix_historical_document_batch", table_name="historical_document_records")
    op.drop_index("ix_historical_document_tenant_supplier_date", table_name="historical_document_records")
    op.drop_index("ix_historical_document_tenant_type_number", table_name="historical_document_records")
    op.drop_index("ix_historical_document_records_batch_id", table_name="historical_document_records")
    op.drop_index("ix_historical_document_records_supplier_id", table_name="historical_document_records")
    op.drop_index("ix_historical_document_records_tenant_id", table_name="historical_document_records")
    op.drop_table("historical_document_records")
    op.drop_index("ix_historical_purchase_orders_batch", table_name="historical_purchase_orders")
    op.drop_index("ix_historical_purchase_orders_tenant_supplier", table_name="historical_purchase_orders")
    op.drop_index("ix_historical_purchase_orders_tenant_date", table_name="historical_purchase_orders")
    op.drop_index("ix_historical_purchase_orders_supplier_id", table_name="historical_purchase_orders")
    op.drop_index("ix_historical_purchase_orders_tenant_id", table_name="historical_purchase_orders")
    op.drop_table("historical_purchase_orders")
    op.drop_index("ix_historical_import_batches_tenant_status", table_name="historical_import_batches")
    op.drop_index("ix_historical_import_batches_tenant_created", table_name="historical_import_batches")
    op.drop_index("ix_historical_import_batches_status", table_name="historical_import_batches")
    op.drop_index("ix_historical_import_batches_tenant_id", table_name="historical_import_batches")
    op.drop_table("historical_import_batches")
