"""import preview unit/category fields - phase 3.2d-mvp fix

Adds unit/category to import_previews. Real bug found doing an actual end-
to-end import: Validation correctly extracted a row's unit/category (per
the user's own explicit "ייבא מוצרים: שם מוצר, יחידה, קטגוריה" requirement)
but never persisted them onto ImportPreview, so Execution had nothing to
pass to CatalogService.create_product — every imported product silently
got unit=None regardless of what the source file said.

Purely additive — no existing column changed or removed.

Revision ID: 20260720_preview_unit_cat
Revises: 20260720_import_execution
Create Date: 2026-07-20 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260720_preview_unit_cat'
down_revision = '20260720_import_execution'


def upgrade():
    with op.batch_alter_table('import_previews') as batch_op:
        batch_op.add_column(sa.Column('unit', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('import_previews') as batch_op:
        batch_op.drop_column('category')
        batch_op.drop_column('unit')
