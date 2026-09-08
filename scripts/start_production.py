"""Production entrypoint for Render.

Database migrations are owned by Render's preDeployCommand in render.yaml.
Keeping schema changes out of the web process prevents every Gunicorn worker
from attempting migration work during application startup.
"""
from __future__ import annotations

import os


def main() -> None:
    port = os.environ.get("PORT", "10000")
    workers = os.environ.get("WEB_CONCURRENCY", "4")
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
            "120",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
        ],
    )


if __name__ == "__main__":
    main()
