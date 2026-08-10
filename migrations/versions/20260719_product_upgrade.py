"""product model upgrade - phase 1 core data foundation

Adds image/barcode/category/unit/stock fields to products. All columns are
nullable, so this is purely additive: existing rows get NULL, no existing
API contract changes, and OrderService never reads these (Snapshot
Architecture only copies sku/name/price at order-creation time) so no
existing order is affected either.

Revision ID: 20260719_product_upgrade
Revises: 20240520_catalog
Create Date: 2026-07-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260719_product_upgrade'
down_revision = '20240520_catalog'


def upgrade():
    with op.batch_alter_table('products') as batch_op:
        batch_op.add_column(sa.Column('image_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('barcode', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('unit', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('units_per_carton', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('supplier_sku', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('current_stock', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('min_stock', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('recommended_stock', sa.Integer(), nullable=True))

    op.create_index(op.f('ix_products_barcode'), 'products', ['barcode'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_products_category'), table_name='products')
    op.drop_index(op.f('ix_products_barcode'), table_name='products')

    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('recommended_stock')
        batch_op.drop_column('min_stock')
        batch_op.drop_column('current_stock')
        batch_op.drop_column('supplier_sku')
        batch_op.drop_column('units_per_carton')
        batch_op.drop_column('unit')
        batch_op.drop_column('category')
        batch_op.drop_column('barcode')
        batch_op.drop_column('image_url')
