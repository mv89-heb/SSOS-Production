"""import execution integrity constraints

Adds a database-level guard that prevents two COMMITTED executions from
existing for the same tenant/import session at the same time.

A rolled-back execution is intentionally excluded from the unique index so
the existing commit -> rollback -> recommit workflow remains valid.

Revision ID: 20260811_import_execution_integrity
Revises: 20260811_catalog_integrity
Create Date: 2026-08-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260811_import_execution_integrity"
down_revision = "20260811_catalog_integrity"


def upgrade():
    bind = op.get_bind()

    duplicates = bind.execute(
        sa.text(
            """
            SELECT tenant_id, import_session_id, COUNT(*) AS duplicate_count
            FROM import_executions
            WHERE status = 'COMMITTED'
            GROUP BY tenant_id, import_session_id
            HAVING COUNT(*) > 1
            ORDER BY tenant_id, import_session_id
            LIMIT 20
            """
        )
    ).fetchall()

    if duplicates:
        examples = ", ".join(
            f"tenant={row[0]} session={row[1]} count={row[2]}"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot apply committed-import uniqueness constraint: duplicate "
            f"COMMITTED executions already exist. Resolve them first. Examples: {examples}"
        )

    op.create_index(
        "uq_import_executions_tenant_session_committed",
        "import_executions",
        ["tenant_id", "import_session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'COMMITTED'"),
        sqlite_where=sa.text("status = 'COMMITTED'"),
    )


def downgrade():
    op.drop_index(
        "uq_import_executions_tenant_session_committed",
        table_name="import_executions",
    )
