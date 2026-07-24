# Mebel Catalog API

Ko‘p ijarali (multi-tenant) mebel katalogi uchun backend.

- FastAPI + SQLAlchemy 2 (async) + PostgreSQL
- Public katalog API + token bilan himoyalangan admin API + super admin API
- Frontend alohida repoda: [catalog-frontend](https://github.com/boburbekt/catalog-frontend)

## 1. Lokal ishga tushirish (Docker)

```bash
cp .env.example .env     # ixtiyoriy — barcha qiymatlarning defaulti bor
docker compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

Backend `dev` muhitida ishga tushganda `demo-mebel` do‘koni uchun demo ma’lumotlarni kiritadi
(admin token: `demo-admin-token`).

## 2. Lokal ishga tushirish (Docker'siz)

PostgreSQL alohida ishlab turgan bo‘lsa:

```bash
pip install -e ".[dev]"     # dev = pytest, pytest-asyncio, aiosqlite
export DATABASE_URL=postgresql+asyncpg://catalog:catalog_password@localhost:5432/mebel_catalog
alembic upgrade head        # sxemani migratsiyalar orqali yaratadi
uvicorn app.main:app --reload
```

Testlar (xotiradagi SQLite, tashqi bog‘liqliksiz):

```bash
python -m pytest -q
python -m compileall app
```

## 3. Muhit o‘zgaruvchilari

| O‘zgaruvchi | Default | Izoh |
| --- | --- | --- |
| `ENVIRONMENT` | `dev` | `dev` da demo seed ishlaydi |
| `DATABASE_URL` | `postgresql+asyncpg://catalog:catalog_password@db:5432/mebel_catalog` | asyncpg drayveri majburiy |
| `CORS_ORIGINS` | `http://localhost:3000` | vergul bilan ajratilgan ro‘yxat |
| `PUBLIC_SITE_URL` | `http://localhost:3000` | QR/havolalar shu manzilga ishora qiladi |
| `TELEGRAM_BOT_TOKEN` | (bo‘sh) | bo‘sh bo‘lsa bildirishnoma yuborilmaydi (buyurtma baribir saqlanadi) |
| `SUPER_ADMIN_TOKEN` | (bo‘sh) | `/api/super/*` uchun; bo‘sh bo‘lsa endpoint hamma uchun yopiq |
| `UPLOAD_DIR` | `uploads` | yuklangan rasmlar papkasi |
| `MAX_UPLOAD_MB` | `8` | bitta rasm uchun maksimal hajm |
| `ORDER_RATE_LIMIT_PER_MINUTE` | `5` | bitta IP daqiqasiga nechta buyurtma bera oladi (anti-spam) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `mebel_catalog` / `catalog` / `catalog_password` | faqat compose'dagi `db` servisi uchun |

## 4. API

**Public (katalog):**

| Metod | Yo‘l | Izoh |
| --- | --- | --- |
| `GET` | `/api/public/shops/{shop_slug}` | do‘kon + kategoriyalar + mahsulotlar (`?category=`, `?search=`, `?limit=`, `?offset=`) |
| `GET` | `/api/public/shops/{shop_slug}/products/{product_slug}` | mahsulot tafsiloti |
| `POST` | `/api/public/shops/{shop_slug}/visits` | tashrif eventi (statistika); GET so‘rovlari tashrif yozmaydi |
| `POST` | `/api/public/shops/{shop_slug}/orders` | buyurtma (`consent: true` majburiy, honeypot + IP rate-limit) |
| `GET` | `/api/public/sitemap` | SEO: faol do‘kon va ko‘rinadigan mahsulot slug'lari + `updated_at` |

**Admin (X-Admin-Token header, tenant token orqali aniqlanadi):**

| Metod | Yo‘l | Izoh |
| --- | --- | --- |
| `GET/PATCH` | `/api/admin/me` | biznes self-service (slug/is_active/token o‘zgartirilmaydi) |
| `GET/POST/PATCH/DELETE` | `/api/admin/products[...]` | mahsulotlar CRUD + `/{id}/image` yuklash |
| `GET/POST/PATCH/DELETE` | `/api/admin/categories[...]` | kategoriyalar CRUD |
| `GET/PATCH` | `/api/admin/orders[...]` | buyurtmalar ro‘yxati + holat |
| `GET` | `/api/admin/stats` | statistika (`total_products`, `new_orders`, `by_day`, ...) |
| `GET` | `/api/admin/qr[.svg]` | QR kod |

**Super admin (X-Super-Token header):**

| Metod | Yo‘l | Izoh |
| --- | --- | --- |
| `GET/POST` | `/api/super/businesses` | ro‘yxat / yangi biznes (yaratishda xom token bir marta qaytadi) |
| `PATCH` | `/api/super/businesses/{id}` | biznesni tahrirlash (dublikat slug → 409) |
| `POST` | `/api/super/businesses/{id}/rotate-token` | tokenni yangilash (eski token darhol ishlamay qoladi) |

`GET /health` — healthcheck.

## 5. Ma’lumotlar bazasi va migratsiyalar

Sxema: [`docs/database-schema.md`](docs/database-schema.md).

Sxema **Alembic** orqali boshqariladi (startupda `create_all` ishlatilmaydi):

```bash
alembic upgrade head        # eng so‘nggi holatga
alembic downgrade -1        # bitta migratsiya orqaga
alembic revision --autogenerate -m "xabar"   # model o‘zgargach yangi migratsiya
```

Docker konteyneri startda `alembic upgrade head` ni ishga tushiradi (`docker-entrypoint.sh`).

## 6. Rasm yuklash (upload storage)

Rasmlar `POST /api/admin/products/{id}/image` orqali yuklanadi: fayl WebP ga o‘tkaziladi va
`UPLOAD_DIR` ostida `{business_id}/...webp` sifatida saqlanadi, `/uploads/...` orqali beriladi.
Hozircha **lokal disk** ishlatiladi (S3 emas); Docker'da papka volume bilan saqlanadi.

## 7. Admin token xavfsizligi va rotate

Admin token bazada **plaintext saqlanmaydi** — faqat SHA-256 hash (`admin_token_hash`). Xom token
faqat ikki joyda bir marta qaytadi: biznes yaratishda va `rotate-token` javobida. Kelgan token
hash qilinib solishtiriladi.

```bash
# tokenni yangilash (eski token darhol 401 bo‘ladi)
curl -X POST -H "X-Super-Token: $SUPER_ADMIN_TOKEN" \
  http://localhost:8000/api/super/businesses/1/rotate-token
```

## 8. Muhim arxitektura qoidasi

Barcha biznesga tegishli obyektlarda `business_id` mavjud va do‘kon har doim URL'dagi `slug`
orqali aniqlanadi. Yangi endpoint qo‘shganda so‘rovni albatta `business_id` bo‘yicha cheklang.

## 9. Anti-spam (buyurtma tezligi cheklovi)

Buyurtma endpointi oddiy **in-process** (jarayon ichidagi) rate limiter bilan himoyalangan: bitta IP
uchun `ORDER_RATE_LIMIT_PER_MINUTE` (default 5) dan ko‘p buyurtma bo‘lsa `429` qaytadi. Bundan tashqari
so‘rovda majburiy `consent: true` va yashirin **honeypot** maydoni tekshiriladi (bot to‘ldirsa `400`).

> ⚠️ **Bir jarayon cheklovi.** Limiter holati faqat shu Python jarayonining xotirasida saqlanadi.
> Bir nechta uvicorn worker yoki replika ishlatilsa, har biri o‘z hisobini yuritadi va cheklov global
> bo‘lmaydi. Ishonchli, taqsimlangan cheklov uchun Redis kabi umumiy do‘kon kerak (MVP doirasida
> ataylab qo‘shilmagan).
