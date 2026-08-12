#!/usr/bin/env bash
set -euo pipefail

# Render does not expose Pre-Deploy Command on every service configuration.
# Run Alembic immediately before Gunicorn so the ORM schema is always brought
# to the application revision before workers begin accepting requests.
python -m flask --app wsgi:app db upgrade

exec gunicorn -w 4 -b 0.0.0.0:"${PORT}" wsgi:app --timeout 120
