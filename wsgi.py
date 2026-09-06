import os

from app import create_app
from app.extensions import db
from flask_migrate import upgrade as migrate_upgrade
from sqlalchemy import text


def _run_startup_migrations(app):
    """Bring the production database to the application revision before serving.

    The existing Render service uses a dashboard-configured Gunicorn command.
    Running Alembic from WSGI makes the protection independent of Render
    Blueprint synchronization. A PostgreSQL advisory lock serializes multiple
    Gunicorn workers so only one process performs a migration at a time.
    """
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(73184219)"))
            print("[production] Running database migrations before serving", flush=True)
            migrate_upgrade()
            print("[production] Database migrations completed", flush=True)


app = create_app()
_run_startup_migrations(app)

from app.services.import_runtime_fixes import install_import_supplier_detection_fix

install_import_supplier_detection_fix()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
