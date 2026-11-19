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
- **Multi-tenant isolation** — tenant-scoped repositories and explicit
  tenant constraints in domain queries keep records isolated by
  `current_user.tenant_id`.
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

Patterns used: App Factory (`app/__init__.py`), tenant-scoped repositories and
domain services, and Flask Blueprints separated by domain. Repository reads
apply the tenant filter centrally; domain queries implemented directly in a
route must also include an explicit tenant constraint. Business workflows are
implemented in services, while a small number of legacy endpoints still keep
simple, tenant-scoped queries in their route handlers.

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

## Inventory counting and planning

Physical counts are the source of truth for current stock. To keep weekly work
manageable, the active catalog is divided into a four-week rotating count
cycle; products at or below zero stock or their configured minimum are added
to the current week's assigned group. Employees must complete that assigned
group, not recount the entire catalog every week. Consumption estimates use
count history and recorded receipts; routine warehouse withdrawals are not
required.

## Canonical supplier product matching

The canonical master catalog, supplier-specific listings, matching review queue, and normalized price comparison are documented in [Master Product Matching](docs/MASTER_PRODUCT_MATCHING.md). The new tables are added through Alembic; legacy products are preserved without fuzzy merging.

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
4. Render applies all migration heads at service startup when
   `RUN_MIGRATIONS_ON_START=true` is configured in the Blueprint. For local
   development, run `flask db upgrade heads` manually.

## Render Deployment

`render.yaml` defines the backend, frontend, and shared rate-limit storage:

**Backend** (`ssos-backend`, Python):
- **Build:** `pip install -r requirements.txt`
- **Start:** `python scripts/start_production.py`
- When `RUN_MIGRATIONS_ON_START=true`, the entrypoint applies all Alembic
  migration heads once before starting Gunicorn.
- The current Blueprint defaults to one Gunicorn worker with four threads to
  stay within the free instance's memory budget.

**Rate-limit storage** (`ssos-ratelimit-redis`, Render Key Value):
- Shared Redis-compatible storage is required by the production web service
  so login and registration rate limits are consistent across processes.

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
  cookies in production, HttpOnly, and SameSite=None for the credentialed
  cross-origin frontend/backend deployment.
- **CSRF:** Flask-WTF `CSRFProtect` enabled by default.
- **Rate limiting:** login endpoint is rate-limited (Flask-Limiter) to slow
  down credential-stuffing attempts.
- **Tenant isolation / IDOR prevention:** tenant-scoped repositories apply
  `tenant_id` to repository reads; services and any direct route-level queries
  must scope resources to the authenticated tenant. Cross-tenant access is
  covered by automated tests in key procurement workflows.
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

The pytest suite covers authentication, tenant isolation, RBAC, order lifecycle
transitions, audit hash-chain integrity (including simulated tampering),
upload validation, OCR/document processing, inventory planning, procurement
analytics, exports, notifications, and health checks. Tests run against an
in-memory SQLite database; PostgreSQL migrations are validated separately in
CI against PostgreSQL 16. The test count is intentionally not hard-coded here.

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
