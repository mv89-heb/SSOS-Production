"""initial schema

Revision ID: 2e087983a70a
Revises: None
Create Date: 2024-05-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2e087983a70a'
down_revision = None

def upgrade():
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)

    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('previous_hash', sa.String(length=64), nullable=False),
        sa.Column('hash_chain', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('timestamp_iso', sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('order_number', sa.String(length=40), nullable=False),
        sa.Column('supplier_name', sa.String(length=200), nullable=False),
        sa.Column('supplier_contact', sa.String(length=200), nullable=True),
        sa.Column('supplier_email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('discount_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('final_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('snapshot', sa.JSON(), nullable=True),
        sa.Column('snapshot_taken_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('orders')
    op.drop_table('notifications')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('tenants')
