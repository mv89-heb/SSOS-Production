"""Production entrypoint for Render.

Render services created before the Blueprint pre-deploy setting existed may
continue using their dashboard-configured start command. This entrypoint makes
schema migration part of the executable that Render starts, so an old service
configuration cannot boot the application against an outdated database.
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    env = os.environ.copy()
    env.setdefault("FLASK_APP", "app:create_app()")

    print("[production] Running database migrations before Gunicorn", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "app:create_app()",
            "db",
            "upgrade",
            "heads",
        ],
        env=env,
        check=True,
    )

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
        ],
    )


if __name__ == "__main__":
    main()
