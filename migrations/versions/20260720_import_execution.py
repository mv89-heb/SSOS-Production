"""import execution engine mvp - phase 3.2d-mvp

Adds import_executions: the record of what a single commit did (created/
updated IDs, price history for rollback, skipped-row report). This is the
first phase in the whole import pipeline that writes to products/
suppliers/supplier_product_offers — and it only ever does so via
CatalogService's existing validated, audited write methods.

Purely additive — no existing table or column changes.

Revision ID: 20260720_import_execution
Revises: 20260720_import_validation
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260720_import_execution'
down_revision = '20260720_import_validation'


def upgrade():
    op.create_table(
        'import_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_session_id', sa.Integer(), nullable=False),
        sa.Column('import_validation_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('snapshot_suppliers_before', sa.Integer(), nullable=False),
        sa.Column('snapshot_products_before', sa.Integer(), nullable=False),
        sa.Column('snapshot_offers_before', sa.Integer(), nullable=False),
        sa.Column('suppliers_created', sa.Integer(), nullable=False),
        sa.Column('products_created', sa.Integer(), nullable=False),
        sa.Column('products_updated', sa.Integer(), nullable=False),
        sa.Column('offers_created', sa.Integer(), nullable=False),
        sa.Column('created_supplier_ids', sa.JSON(), nullable=False),
        sa.Column('created_product_ids', sa.JSON(), nullable=False),
        sa.Column('created_offer_ids', sa.JSON(), nullable=False),
        sa.Column('price_history', sa.JSON(), nullable=False),
        sa.Column('skipped_rows', sa.JSON(), nullable=False),
        sa.Column('executed_by', sa.Integer(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.Column('rolled_back_by', sa.Integer(), nullable=True),
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_session_id'], ['import_sessions.id'], ),
        sa.ForeignKeyConstraint(['import_validation_id'], ['import_validations.id'], ),
        sa.ForeignKeyConstraint(['executed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['rolled_back_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_executions_tenant_id'), 'import_executions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_executions_import_session_id'), 'import_executions', ['import_session_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_import_executions_import_session_id'), table_name='import_executions')
    op.drop_index(op.f('ix_import_executions_tenant_id'), table_name='import_executions')
    op.drop_table('import_executions')
