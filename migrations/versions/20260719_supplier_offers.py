"""supplier catalog engine - phase 2

Adds supplier_product_offers: alternate suppliers' prices for products that
already exist in the catalog under their own primary supplier. Purely
additive — no existing table or column changes, and OrderService never
reads this table (order creation still snapshots Product.current_price/
supplier_id exactly as before).

Revision ID: 20260719_supplier_offers
Revises: 20260719_product_upgrade
Create Date: 2026-07-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260719_supplier_offers'
down_revision = '20260719_product_upgrade'


def upgrade():
    op.create_table(
        'supplier_product_offers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('supplier_sku', sa.String(length=100), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('units_per_carton', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'supplier_id', name='uq_offer_product_supplier'),
    )
    op.create_index(op.f('ix_supplier_product_offers_tenant_id'), 'supplier_product_offers', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_supplier_product_offers_product_id'), 'supplier_product_offers', ['product_id'], unique=False)
    op.create_index(op.f('ix_supplier_product_offers_supplier_id'), 'supplier_product_offers', ['supplier_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_supplier_product_offers_supplier_id'), table_name='supplier_product_offers')
    op.drop_index(op.f('ix_supplier_product_offers_product_id'), table_name='supplier_product_offers')
    op.drop_index(op.f('ix_supplier_product_offers_tenant_id'), table_name='supplier_product_offers')
    op.drop_table('supplier_product_offers')
