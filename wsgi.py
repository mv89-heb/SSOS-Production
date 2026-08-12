import os

# Render services that were created without a Pre-Deploy Command can start
# Gunicorn directly. Run the small, additive production schema bootstrap
# before importing/creating the Flask app so SQLAlchemy never sees a partially
# upgraded Product schema. Alembic remains the canonical migration mechanism.
from scripts.ensure_production_schema import ensure_schema

ensure_schema()

from app import create_app
from app.services.import_runtime_fixes import install_import_supplier_detection_fix

app = create_app()
install_import_supplier_detection_fix()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
