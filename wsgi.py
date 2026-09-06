import os

from app import create_app
from flask_migrate import upgrade as migrate_upgrade


def _run_startup_migrations(app):
    """Bring the target database to the application revision before serving.

    This runs from WSGI because the existing Render service still uses a
    dashboard-configured Gunicorn command and may not consume the Blueprint
    pre-deploy setting from render.yaml.
    """
    with app.app_context():
        print("[production] Running database migrations before serving", flush=True)
        migrate_upgrade()
        print("[production] Database migrations completed", flush=True)


app = create_app()
_run_startup_migrations(app)

from app.services.import_runtime_fixes import install_import_supplier_detection_fix

install_import_supplier_detection_fix()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
