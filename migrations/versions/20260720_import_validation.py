"""validation and preview engine - phase 3.2c

Adds import_validations, import_previews, import_issues. Also adds
import_rows.raw_values (a positional JSON array, alongside the existing
raw_data dict) — a prerequisite fix: dict key order isn't reliably
preserved through JSON storage, and Analysis's own header detection can
label the same columns differently than Phase 3.1's simple first-row rule
does (confirmed empirically against a real multi-tier-header file).
Validation aligns to ImportMappingColumn.column_index via raw_values,
never by matching header text between the two systems.

Purely additive. Still writes nothing to products/suppliers/
supplier_product_offers — this phase computes and stores what WOULD
happen, nothing more. Creating catalog rows from an approved preview is
Phase 3.2D (Import Execution Engine).

Revision ID: 20260720_import_validation
Revises: 20260720_import_mapping
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260720_import_validation'
down_revision = '20260720_import_mapping'


def upgrade():
    with op.batch_alter_table('import_rows') as batch_op:
        batch_op.add_column(sa.Column('raw_values', sa.JSON(), nullable=True))

    op.create_table(
        'import_validations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_session_id', sa.Integer(), nullable=False),
        sa.Column('import_mapping_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('products_to_create', sa.Integer(), nullable=False),
        sa.Column('products_to_update', sa.Integer(), nullable=False),
        sa.Column('products_to_skip', sa.Integer(), nullable=False),
        sa.Column('suppliers_to_create', sa.Integer(), nullable=False),
        sa.Column('offers_to_create', sa.Integer(), nullable=False),
        sa.Column('offers_to_update', sa.Integer(), nullable=False),
        sa.Column('warning_count', sa.Integer(), nullable=False),
        sa.Column('error_count', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_session_id'], ['import_sessions.id'], ),
        sa.ForeignKeyConstraint(['import_mapping_id'], ['import_mappings.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_validations_tenant_id'), 'import_validations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_validations_import_session_id'), 'import_validations', ['import_session_id'], unique=False)

    op.create_table(
        'import_previews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_validation_id', sa.Integer(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('product_action', sa.String(length=10), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=True),
        sa.Column('matched_product_id', sa.Integer(), nullable=True),
        sa.Column('supplier_action', sa.String(length=10), nullable=True),
        sa.Column('supplier_name', sa.String(length=255), nullable=True),
        sa.Column('matched_supplier_id', sa.Integer(), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('old_price', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('offers', sa.JSON(), nullable=True),
        sa.Column('has_errors', sa.Boolean(), nullable=False),
        sa.Column('has_warnings', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_validation_id'], ['import_validations.id'], ),
        sa.ForeignKeyConstraint(['matched_product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['matched_supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_previews_tenant_id'), 'import_previews', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_previews_import_validation_id'), 'import_previews', ['import_validation_id'], unique=False)

    op.create_table(
        'import_issues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_validation_id', sa.Integer(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=True),
        sa.Column('field', sa.String(length=100), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_validation_id'], ['import_validations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_issues_tenant_id'), 'import_issues', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_issues_import_validation_id'), 'import_issues', ['import_validation_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_import_issues_import_validation_id'), table_name='import_issues')
    op.drop_index(op.f('ix_import_issues_tenant_id'), table_name='import_issues')
    op.drop_table('import_issues')

    op.drop_index(op.f('ix_import_previews_import_validation_id'), table_name='import_previews')
    op.drop_index(op.f('ix_import_previews_tenant_id'), table_name='import_previews')
    op.drop_table('import_previews')

    op.drop_index(op.f('ix_import_validations_import_session_id'), table_name='import_validations')
    op.drop_index(op.f('ix_import_validations_tenant_id'), table_name='import_validations')
    op.drop_table('import_validations')

    with op.batch_alter_table('import_rows') as batch_op:
        batch_op.drop_column('raw_values')
