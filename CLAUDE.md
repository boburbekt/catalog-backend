# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Backend for a multi-tenant furniture catalog MVP ("Mebel Catalog"): FastAPI + SQLAlchemy 2 (async) + PostgreSQL. API error messages and seed data are in Uzbek. The Nuxt frontend lives in a separate repository (`catalog-frontend`) and talks to this API over HTTP; `CORS_ORIGINS` must list its origin.

## Commands

```bash
docker compose up --build        # db on 5432, backend on 8000
docker compose down -v           # also drops the postgres volume (see schema note below)
```

The backend container bind-mounts the repo and runs uvicorn with `--reload`, so code edits apply without rebuilding. Rebuild only when `pyproject.toml` changes.

Without Docker (needs a reachable PostgreSQL):

```bash
pip install -e . && uvicorn app.main:app --reload
```

There is no test suite, linter, or Alembic migrations directory yet — the pytest asyncio config and the `alembic` dependency in `pyproject.toml` are declared in anticipation. Schema changes take effect via `Base.metadata.create_all` on startup, and **`create_all` does not alter existing tables**, so after changing a model you must `docker compose down -v` or add migrations.

API docs: http://localhost:8000/docs.

## Architecture

**Multi-tenancy is the core invariant.** Every business-owned entity (`Category`, `Product`, `Order`) carries `business_id`, and tenants are resolved by URL slug, never by an ID from the client. Public routes are `/api/public/shops/{shop_slug}/...`: the handler loads the `Business` by slug (rejecting inactive ones), then scopes every subsequent query by `business_id`. When adding endpoints or models, preserve this — a query filtering by `product_id`/`category_id` without also filtering on the resolved `business_id` is a cross-tenant leak. `(business_id, slug)` is unique per tenant for categories and products; only `Business.slug` is globally unique.

**Layers** (`app/`): `models/entities.py` (all SQLAlchemy models in one file; `Base` + `TimestampMixin` in `db/base.py`) → `schemas/catalog.py` (all Pydantic I/O, `from_attributes=True`) → `api/` routers → `main.py` mounts them under `/api`. Sessions come from the `get_db` dependency (`db/session.py`); settings are a cached `pydantic-settings` object (`core/config.py`, env var per field name, e.g. `DATABASE_URL`, `CORS_ORIGINS` as a comma-separated string).

`main.py`'s lifespan runs `create_all` then `seed_demo` (`services/seed.py`), which is idempotent — it no-ops if the `demo-mebel` business already exists.

`api/admin.py` is explicitly a demo surface: **no authentication**, and the tenant is chosen by a `business_slug` query param / body field defaulting to `demo-mebel`. Do not model real admin features on it without adding auth.

Async SQLAlchemy means relationships must be eager-loaded (`selectinload`) in the query, not touched lazily afterwards — see the `selectinload(Product.category)` calls in both routers.

**Contract with the frontend:** the frontend declares its own hand-written TypeScript interfaces mirroring `schemas/catalog.py`. Changing a response schema is a breaking change across repos — update `catalog-frontend` in the same change. Decimals serialize as strings.

Schema diagram: `docs/database-schema.md`.
