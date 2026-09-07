"""add supplier extra fields phone2 customer_number delivery_days order_days

Revision ID: 95371bcfb9b2
Revises: 20260720_preview_unit_cat
Create Date: 2026-07-30 15:54:35.342818

"""
from alembic import op
import sqlalchemy as sa


revision = '95371bcfb9b2'
down_revision = '20260720_preview_unit_cat'
branch_labels = None
depends_on = None


def _create_index_if_missing(table_name, index_name, columns, unique=False):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    indexes = [
        ("audit_logs", "ix_audit_logs_hash_chain", ["hash_chain"], True),
        ("audit_logs", "ix_audit_logs_tenant_id", ["tenant_id"], False),
        ("audit_logs", "ix_audit_logs_user_id", ["user_id"], False),
        ("notifications", "ix_notifications_tenant_id", ["tenant_id"], False),
        ("notifications", "ix_notifications_user_id", ["user_id"], False),
        ("orders", "ix_orders_order_number", ["order_number"], False),
        ("orders", "ix_orders_status", ["status"], False),
        ("orders", "ix_orders_tenant_id", ["tenant_id"], False),
        ("orders", "ix_orders_user_id", ["user_id"], False),
        ("products", "ix_products_supplier_id", ["supplier_id"], False),
        ("users", "ix_users_tenant_id", ["tenant_id"], False),
    ]
    for table_name, index_name, columns, unique in indexes:
        _create_index_if_missing(table_name, index_name, columns, unique)


def downgrade():
    bind = op.get_bind()
    for table_name, index_name in [
        ("users", "ix_users_tenant_id"),
        ("products", "ix_products_supplier_id"),
        ("orders", "ix_orders_user_id"),
        ("orders", "ix_orders_tenant_id"),
        ("orders", "ix_orders_status"),
        ("orders", "ix_orders_order_number"),
        ("notifications", "ix_notifications_user_id"),
        ("notifications", "ix_notifications_tenant_id"),
        ("audit_logs", "ix_audit_logs_user_id"),
        ("audit_logs", "ix_audit_logs_tenant_id"),
        ("audit_logs", "ix_audit_logs_hash_chain"),
    ]:
        inspector = sa.inspect(bind)
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name in existing:
            op.drop_index(index_name, table_name=table_name)
