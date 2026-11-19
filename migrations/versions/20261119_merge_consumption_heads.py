"""Merge existing delete-protection head with consumption-profile schema.

Revision ID: 20261119_merge_consumption_heads
Revises: 20261119_preserve_delete, 20261119_consumption_profiles
"""
revision = "20261119_merge_consumption_heads"
down_revision = ("20261119_preserve_delete", "20261119_consumption_profiles")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
