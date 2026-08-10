"""import staging layer - phase 3.1

Adds import_sessions and import_rows: a staging area for uploaded price
lists. Purely additive — no existing table or column changes. Nothing here
writes to products/suppliers/supplier_product_offers; those are only ever
touched by a later phase's explicit approve/commit step.

Revision ID: 20260719_import_staging
Revises: 20260719_supplier_offers
Create Date: 2026-07-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260719_import_staging'
down_revision = '20260719_supplier_offers'


def upgrade():
    op.create_table(
        'import_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=True),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('column_headers', sa.JSON(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_sessions_tenant_id'), 'import_sessions', ['tenant_id'], unique=False)

    op.create_table(
        'import_rows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_session_id', sa.Integer(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_session_id'], ['import_sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_rows_tenant_id'), 'import_rows', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_rows_import_session_id'), 'import_rows', ['import_session_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_import_rows_import_session_id'), table_name='import_rows')
    op.drop_index(op.f('ix_import_rows_tenant_id'), table_name='import_rows')
    op.drop_table('import_rows')

    op.drop_index(op.f('ix_import_sessions_tenant_id'), table_name='import_sessions')
    op.drop_table('import_sessions')
