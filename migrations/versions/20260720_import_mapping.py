"""mapping engine - phase 3.2b

Adds import_mappings, import_mapping_columns, import_mapping_templates, and
one nullable column on import_sessions (staged_sheet_name — tracks which
sheet was actually staged into ImportRow, needed to link a Mapping
workspace to the matching ImportAnalysis row for that same sheet).

Purely additive. Still writes nothing to products/suppliers/
supplier_product_offers — approving a mapping only records a person's
reviewed decision about how columns should be interpreted; creating
catalog rows from it is Phase 3.2D (Import Execution Engine).

Revision ID: 20260720_import_mapping
Revises: 20260719_import_analysis
Create Date: 2026-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260720_import_mapping'
down_revision = '20260719_import_analysis'


def upgrade():
    with op.batch_alter_table('import_sessions') as batch_op:
        batch_op.add_column(sa.Column('staged_sheet_name', sa.String(length=255), nullable=True))

    op.create_table(
        'import_mappings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_session_id', sa.Integer(), nullable=False),
        sa.Column('import_analysis_id', sa.Integer(), nullable=True),
        sa.Column('sheet_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_session_id'], ['import_sessions.id'], ),
        sa.ForeignKeyConstraint(['import_analysis_id'], ['import_analyses.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_mappings_tenant_id'), 'import_mappings', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_mappings_import_session_id'), 'import_mappings', ['import_session_id'], unique=False)

    op.create_table(
        'import_mapping_columns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_mapping_id', sa.Integer(), nullable=False),
        sa.Column('column_index', sa.Integer(), nullable=False),
        sa.Column('column_header', sa.String(length=255), nullable=False),
        sa.Column('suggested_target', sa.String(length=30), nullable=False),
        sa.Column('suggested_confidence', sa.String(length=10), nullable=False),
        sa.Column('suggested_supplier_id', sa.Integer(), nullable=True),
        sa.Column('suggested_supplier_name', sa.String(length=255), nullable=True),
        sa.Column('suggested_price_type', sa.String(length=20), nullable=True),
        sa.Column('final_target', sa.String(length=30), nullable=False),
        sa.Column('final_supplier_id', sa.Integer(), nullable=True),
        sa.Column('final_supplier_name', sa.String(length=255), nullable=True),
        sa.Column('final_price_type', sa.String(length=20), nullable=True),
        sa.Column('user_reviewed', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_mapping_id'], ['import_mappings.id'], ),
        sa.ForeignKeyConstraint(['suggested_supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['final_supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('import_mapping_id', 'column_index', name='uq_mapping_column_index'),
    )
    op.create_index(op.f('ix_import_mapping_columns_tenant_id'), 'import_mapping_columns', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_mapping_columns_import_mapping_id'), 'import_mapping_columns', ['import_mapping_id'], unique=False)

    op.create_table(
        'import_mapping_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('column_mapping', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_mapping_templates_tenant_id'), 'import_mapping_templates', ['tenant_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_import_mapping_templates_tenant_id'), table_name='import_mapping_templates')
    op.drop_table('import_mapping_templates')

    op.drop_index(op.f('ix_import_mapping_columns_import_mapping_id'), table_name='import_mapping_columns')
    op.drop_index(op.f('ix_import_mapping_columns_tenant_id'), table_name='import_mapping_columns')
    op.drop_table('import_mapping_columns')

    op.drop_index(op.f('ix_import_mappings_import_session_id'), table_name='import_mappings')
    op.drop_index(op.f('ix_import_mappings_tenant_id'), table_name='import_mappings')
    op.drop_table('import_mappings')

    with op.batch_alter_table('import_sessions') as batch_op:
        batch_op.drop_column('staged_sheet_name')
