import os

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import create_app
from app.extensions import db
from flask_migrate import upgrade as migrate_upgrade
from sqlalchemy import text


def _run_startup_migrations(app):
    """Bring the production database to current Alembic heads only when needed.

    The dashboard-configured Gunicorn command imports this module in each
    worker. A PostgreSQL advisory lock serializes startup checks; workers that
    start after the first migration see the current heads and skip Alembic.
    This keeps the existing deployment safe without requiring Blueprint sync.
    """
    with app.app_context():
        migrate_extension = app.extensions.get("migrate")
        if migrate_extension is None:
            raise RuntimeError("Flask-Migrate is not initialized")

        config = migrate_extension.get_config()
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        with db.engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(73184219)"))
            current_heads = set(MigrationContext.configure(conn).get_current_heads())
            if current_heads == expected_heads:
                print("[production] Database migrations already current; skipping", flush=True)
                return

            print(
                f"[production] Applying database migrations "
                f"(current={sorted(current_heads)}, expected={sorted(expected_heads)})",
                flush=True,
            )
            migrate_upgrade(revision="heads")
            print("[production] Database migrations completed", flush=True)


app = create_app()
_run_startup_migrations(app)

from app.services.import_runtime_fixes import install_import_supplier_detection_fix

install_import_supplier_detection_fix()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
