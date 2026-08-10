# SSOS — Smart Supplier Order System

A multi-tenant SaaS platform for supplier order management, with OCR document
intake, an immutable hash-chained audit trail, and role-based access control.

## System Overview

SSOS lets multiple organizations ("tenants") independently manage purchase
orders to their suppliers on a single shared deployment, with hard isolation
between tenants at the data-access layer. Every write that matters
(registrations, logins, order lifecycle changes) is recorded in an
append-only audit log whose entries are cryptographically chained, so
tampering with history is detectable.

Core capabilities:
- **Multi-tenant isolation** — every query is scoped to `current_user.tenant_id`
  at the repository layer, not left to individual routes to remember.
- **Order lifecycle** — draft → submitted → approved → sent → completed, with
  a frozen snapshot taken at submission time so later catalog/price changes
  never rewrite history.
- **OCR intake** — upload a supplier invoice (image or PDF) against an order
  and extract text via a swappable OCR provider.
- **Immutable audit trail** — SHA-256 hash-chained log entries; the ORM itself
  blocks UPDATE/DELETE on audit rows.
- **RBAC** — `employee` / `manager` / `admin`, enforced centrally by
  `PermissionService`.

## Architecture

```
Client (HTTP/JSON)
      |
   Blueprints (app/routes)      <- request parsing, RBAC checks, HTTP status
      |
   Services (app/services)      <- business logic, transactions, audit writes
      |
   Repositories (app/repositories) <- tenant-scoped SQLAlchemy 2.x `select()`
      |
   Models (app/models)          <- SQLAlchemy ORM, DB-level invariants
      |
   PostgreSQL (Neon) / SQLite (dev, test)
```

Patterns used: App Factory (`app/__init__.py`), Repository Pattern (every
repository extends `BaseRepository`, which injects the tenant filter),
Service Layer (routes never touch the DB directly), Blueprint separation per
domain (`auth`, `orders`, `audit`, `notifications`, `health`).

## Local Installation

```bash
git clone <your-repo-url> ssos
cd ssos
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — at minimum set SECRET_KEY; DATABASE_URL defaults to a local
# SQLite file under instance/ if left unset.
```

OCR requires the Tesseract system binary (optional — the app degrades
gracefully to a no-op OCR provider if it's missing):

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr poppler-utils
```

## Environment Configuration

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (Neon) or SQLite connection string. `postgres://` is auto-rewritten to `postgresql://`. |
| `SECRET_KEY` | Flask session/CSRF signing key — set a long random value in production. |
| `SESSION_COOKIE_SECURE` | `True` in production (HTTPS-only cookies). |
| `MAX_UPLOAD_SIZE` | Upload size cap in bytes for OCR document uploads. |
| `RATELIMIT_LOGIN` | Login attempt rate limit, e.g. `10 per minute`. |

## Database Migration

Migrations are managed with Flask-Migrate (Alembic) and live under
`migrations/`.

```bash
export FLASK_APP=wsgi.py
flask db upgrade          # apply migrations
flask db migrate -m "..."  # generate a new migration after model changes
```

## Neon Setup

1. Create a Neon project and database.
2. Copy the pooled connection string from the Neon dashboard (it includes
   `sslmode=require`).
3. Set it as `DATABASE_URL` in your environment or Render service.
4. Run `flask db upgrade` against it once (Render's release/pre-deploy step
   does this automatically — see `render.yaml`).

## Render Deployment

`render.yaml` defines two services:

**Backend** (`ssos-platform`, Python):
- **Build:** `pip install -r requirements.txt`
- **Pre-deploy:** `flask db upgrade`
- **Start:** `gunicorn -w 4 -b 0.0.0.0:$PORT wsgi:app`

**Frontend** (`ssos-frontend`, Node, `rootDir: frontend`):
- **Build:** `npm ci && npm run build`
- **Start:** `npm start -- -p $PORT`

The two services are cross-wired automatically: the backend's `CORS_ORIGINS`
is set to the frontend's live URL, and the frontend's `NEXT_PUBLIC_API_URL`
is set to the backend's live URL (both via `fromService` in `render.yaml`),
so credentialed cross-origin requests work without any manual URL copying.

Steps:
1. Push this repository to GitHub.
2. In Render, create a new **Blueprint** from the repo (it will read
   `render.yaml` and provision both services).
3. Set `DATABASE_URL` to your Neon connection string on the backend service
   in the Render dashboard (marked `sync: false` in `render.yaml`, so it
   isn't stored in git).
4. Deploy. Check `GET /health` and `GET /health/ready` on the backend, and
   `/login` on the frontend, once live.

## Security Model

- **Passwords:** hashed with Werkzeug's `generate_password_hash` (salted
  PBKDF2), never stored or logged in plaintext.
- **Sessions:** Flask-Login with `session_protection = "strong"`, secure
  cookies in production, HttpOnly + SameSite=Lax.
- **CSRF:** Flask-WTF `CSRFProtect` enabled by default.
- **Rate limiting:** login endpoint is rate-limited (Flask-Limiter) to slow
  down credential-stuffing attempts.
- **Tenant isolation / IDOR prevention:** `BaseRepository` injects
  `tenant_id` into every query; routes never query models directly.
- **RBAC:** `PermissionService.require_role_at_least()` centralizes role
  checks (`employee` < `manager` < `admin`).
- **Upload security:** `secure_filename`, extension allow-list, MIME-type
  allow-list, and `MAX_CONTENT_LENGTH` enforcement before any file touches
  disk.
- **Audit immutability:** SQLAlchemy `before_update` / `before_delete`
  listeners on `AuditLog` raise `RuntimeError`, so even a bug elsewhere in
  the codebase can't silently mutate history. `GET /api/audit/verify`
  recomputes the SHA-256 hash chain to detect tampering that bypasses the
  ORM entirely (e.g. a direct SQL `UPDATE`).

## Testing

```bash
FLASK_ENV=testing pytest -q
```

70 tests covering authentication, tenant isolation, RBAC, order lifecycle
transitions, audit hash-chain integrity (including a simulated tampering
scenario), upload validation, OCR service behavior, notifications, and health
checks. Tests run against an in-memory SQLite database — no external services
required.

## Project Layout

```
app/
  __init__.py          # application factory
  config.py             # environment-based configuration
  extensions.py         # Flask extension singletons
  models/                # SQLAlchemy models
  repositories/          # tenant-scoped data access (SQLAlchemy 2.x select())
  services/               # business logic / transactions
  routes/                  # Flask blueprints (HTTP layer only)
  utils/                    # decorators, validators
migrations/                  # Alembic migrations
tests/                         # pytest suite
wsgi.py                          # production entrypoint
render.yaml                       # Render deployment config
```
