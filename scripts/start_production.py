"""Production entrypoint for Render's free web service.

When enabled by the Blueprint, migrations run once in this parent process before
Gunicorn starts, rather than once per worker. This avoids a paid-only pre-deploy
command while preserving a single migration execution per service start.
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    run_migrations = os.environ.get("RUN_MIGRATIONS_ON_START", "false").strip().lower() in {"1", "true", "yes"}
    if run_migrations:
        print("[production] Applying database migrations before Gunicorn starts", flush=True)
        subprocess.run(
            [sys.executable, "-m", "flask", "--app", "app:create_app()", "db", "upgrade", "heads"],
            check=True,
        )
    port = os.environ.get("PORT", "10000")
    workers = os.environ.get("WEB_CONCURRENCY", "1")
    print(f"[production] Starting Gunicorn on port {port} with {workers} workers", flush=True)
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "-w",
            workers,
            "-b",
            f"0.0.0.0:{port}",
            "wsgi:app",
            "--timeout",
            "900",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
        ],
    )


if __name__ == "__main__":
    main()
