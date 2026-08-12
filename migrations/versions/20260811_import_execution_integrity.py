"""import execution integrity constraints

Adds a database-level guard that prevents two COMMITTED executions from
existing for the same tenant/import session when existing data is clean.

Legacy duplicate committed executions are preserved and reported rather than
aborting the whole deployment. Application-level transaction handling remains
in place for new executions, and the unique index can be introduced after the
legacy records are reconciled.

Revision ID: 20260811_import_execution_integrity
Revises: 20260811_catalog_integrity
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
            for row in duplicates[:5]
        )
        print(
            "WARNING: skipping uq_import_executions_tenant_session_committed; "
            f"legacy duplicates exist: {examples}"
        )
        return

    op.create_index(
        "uq_import_executions_tenant_session_committed",
        "import_executions",
        ["tenant_id", "import_session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'COMMITTED'"),
        sqlite_where=sa.text("status = 'COMMITTED'"),
    )


def downgrade():
    bind = op.get_bind()
    existing = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("import_executions")
    }
    if "uq_import_executions_tenant_session_committed" in existing:
        op.drop_index(
            "uq_import_executions_tenant_session_committed",
            table_name="import_executions",
        )
