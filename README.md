# Mebel Catalog API

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2-D71F00?style=flat-square) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![Tests](https://img.shields.io/badge/tests-16_suites-success?style=flat-square)

Multi-tenant backend for a furniture catalog platform. Each business gets its own storefront slug, admin token and QR code; customers browse and place orders without signing up, and shop owners get instant Telegram notifications.

**Highlights**
- 🏢 Multi-tenant isolation via per-business admin tokens
- 🛡️ Anti-spam: honeypot field + per-IP rate limiting on orders
- 📊 Visit analytics and per-day order stats
- 📥 Bulk product import + image upload pipeline
- 📱 QR code generation (PNG / SVG) for offline-to-online traffic
- ✅ 16 test suites running on in-memory SQLite — no external deps
- 🐳 One-command local setup with Docker Compose

**Frontend:** [catalog-frontend](https://github.com/boburbekt/catalog-frontend)

> 📸 Screenshots of the client that consumes this API are in the
> [catalog-frontend](https://github.com/boburbekt/catalog-frontend#screenshots) repo.

## 1. Running locally (Docker)

```bash
cp .env.example .env     # optional — every value has a default
docker compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

When started in the dev environment, the backend seeds demo data for the demo-mebel shop (admin token: demo-admin-token).

> These credentials are for local development only — never use them in production.

## 2. Running locally (without Docker)

If you already have PostgreSQL running:

```bash
pip install -e ".[dev]"     # dev = pytest, pytest-asyncio, aiosqlite
export DATABASE_URL=postgresql+asyncpg://catalog:catalog_password@localhost:5432/mebel_catalog
alembic upgrade head        # creates the schema through migrations
uvicorn app.main:app --reload
```

Tests (in-memory SQLite, no external dependencies):

```bash
python -m pytest -q
python -m compileall app
```

## 3. Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| ENVIRONMENT | dev | demo seed runs in dev |
| DATABASE_URL | postgresql+asyncpg://catalog:catalog_password@db:5432/mebel_catalog | the asyncpg driver is required |
| CORS_ORIGINS | http://localhost:3000 | comma-separated list |
| PUBLIC_SITE_URL | http://localhost:3000 | QR codes and links point here |
| TELEGRAM_BOT_TOKEN | (empty) | if empty, no notification is sent (the order is still stored) |
| SUPER_ADMIN_TOKEN | (empty) | for /api/super/*; if empty, the endpoints are closed to everyone |
| UPLOAD_DIR | uploads | directory for uploaded images |
| MAX_UPLOAD_MB | 8 | maximum size per image |
| ORDER_RATE_LIMIT_PER_MINUTE | 5 | how many orders a single IP may place per minute (anti-spam) |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | mebel_catalog / catalog / catalog_password | only for the db service in compose |

## 4. API

**Public (catalog):**

| Method | Path | Notes |
| --- | --- | --- |
| GET | /api/public/shops/{shop_slug} | shop + categories + products (?category=, ?search=, ?limit=, ?offset=) |
| GET | /api/public/shops/{shop_slug}/products/{product_slug} | product detail |
| POST | /api/public/shops/{shop_slug}/visits | visit event for analytics; GET requests do not record visits |
| POST | /api/public/shops/{shop_slug}/orders | place an order (consent: true required, honeypot + IP rate limit) |
| GET | /api/public/sitemap | SEO: slugs of active shops and visible products with updated_at |

**Admin (X-Admin-Token header — the tenant is resolved from the token):**

| Method | Path | Notes |
| --- | --- | --- |
| GET/PATCH | /api/admin/me | business self-service (slug / is_active / token cannot be changed) |
| GET/POST/PATCH/DELETE | /api/admin/products[...] | product CRUD + /{id}/image upload |
| GET/POST/PATCH/DELETE | /api/admin/categories[...] | category CRUD |
| GET/PATCH | /api/admin/orders[...] | order list + status updates |
| GET | /api/admin/stats | statistics (total_products, new_orders, by_day, ...) |
| GET | /api/admin/qr[.svg] | QR code |

**Super admin (X-Super-Token header):**

| Method | Path | Notes |
| --- | --- | --- |
| GET/POST | /api/super/businesses | list / create a business (the raw token is returned once on creation) |
| PATCH | /api/super/businesses/{id} | edit a business (duplicate slug → 409) |
| POST | /api/super/businesses/{id}/rotate-token | rotate the token (the old one stops working immediately) |

GET /health — healthcheck.

## 5. Database and migrations

Schema: [docs/database-schema.md](docs/database-schema.md).

The schema is managed with **Alembic** (create_all is not used at startup):

```bash
alembic upgrade head        # migrate to the latest revision
alembic downgrade -1        # roll back one migration
alembic revision --autogenerate -m "message"   # new migration after a model change
```

The Docker container runs alembic upgrade head on startup (docker-entrypoint.sh).

## 6. Image uploads

Images are uploaded through POST /api/admin/products/{id}/image: the file is converted to WebP and stored under UPLOAD_DIR as {business_id}/...webp, then served from /uploads/.... For now this uses the **local disk** (not S3); in Docker the directory is kept in a volume.

## 7. Admin token security and rotation

Admin tokens are **never stored in plaintext** — only a SHA-256 hash (admin_token_hash). The raw token is returned exactly once, in two places: when a business is created, and in the rotate-token response. Incoming tokens are hashed and compared against the stored hash.

```bash
# rotate the token (the old one returns 401 immediately)
curl -X POST -H "X-Super-Token: $SUPER_ADMIN_TOKEN" \
  http://localhost:8000/api/super/businesses/1/rotate-token
```

## 8. Key architectural rule

Every business-owned entity carries a business_id, and the shop is always resolved from the slug in the URL. When adding a new endpoint, always scope the query by business_id.

## 9. Anti-spam (order rate limiting)

The order endpoint is protected by a simple **in-process** rate limiter: if a single IP exceeds ORDER_RATE_LIMIT_PER_MINUTE (default 5), the request returns 429. Requests must also carry consent: true and pass a hidden **honeypot** field check (filled in by a bot → 400).

> ⚠️ **Single-process limitation.** The limiter state lives only in the memory of one Python
> process. With multiple uvicorn workers or replicas, each keeps its own counters and the limit
> is not global. A reliable distributed limit needs shared storage such as Redis — deliberately
> left out of the MVP scope.
