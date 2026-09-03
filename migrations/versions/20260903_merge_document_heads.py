"""merge document intelligence migration heads

Revision ID: 20260903_merge_document_heads
Revises: 20260901_document_apply, 20260903_document_intelligence
"""

revision = "20260903_merge_document_heads"
down_revision = ("20260901_document_apply", "20260903_document_intelligence")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
