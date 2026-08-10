"""import analysis engine - phase 3.2a

Adds import_analyses (one row per analyzed sheet — header shape,
orientation, column-type guesses, detected suppliers/units, data-quality
findings) plus 2 nullable workbook-summary columns on import_sessions.
Purely additive — no existing column changed or removed. Nothing here
writes to products/suppliers/supplier_product_offers/import_rows; this
phase is read-only analysis of the originally uploaded file.

Revision ID: 20260719_import_analysis
Revises: 20260719_import_staging
Create Date: 2026-07-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260719_import_analysis'
down_revision = '20260719_import_staging'


def upgrade():
    with op.batch_alter_table('import_sessions') as batch_op:
        batch_op.add_column(sa.Column('workbook_sheet_names', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('workbook_sheet_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('workbook_active_sheet', sa.String(length=255), nullable=True))

    op.create_table(
        'import_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('import_session_id', sa.Integer(), nullable=False),
        sa.Column('sheet_name', sa.String(length=255), nullable=False),
        sa.Column('sheet_index', sa.Integer(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('header_row_index', sa.Integer(), nullable=True),
        sa.Column('header_tier_count', sa.Integer(), nullable=True),
        sa.Column('has_merged_header_cells', sa.Boolean(), nullable=False),
        sa.Column('detected_format', sa.String(length=20), nullable=False),
        sa.Column('format_reason', sa.Text(), nullable=True),
        sa.Column('columns', sa.JSON(), nullable=True),
        sa.Column('detected_suppliers', sa.JSON(), nullable=True),
        sa.Column('detected_units', sa.JSON(), nullable=True),
        sa.Column('data_quality', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['import_session_id'], ['import_sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_analyses_tenant_id'), 'import_analyses', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_import_analyses_import_session_id'), 'import_analyses', ['import_session_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_import_analyses_import_session_id'), table_name='import_analyses')
    op.drop_index(op.f('ix_import_analyses_tenant_id'), table_name='import_analyses')
    op.drop_table('import_analyses')

    with op.batch_alter_table('import_sessions') as batch_op:
        batch_op.drop_column('workbook_active_sheet')
        batch_op.drop_column('workbook_sheet_count')
        batch_op.drop_column('workbook_sheet_names')
