# Mebel Catalog API

Ko‘p ijarali (multi-tenant) mebel katalogi uchun backend.

- FastAPI + SQLAlchemy 2 (async) + PostgreSQL
- Public katalog API va demo admin API
- Frontend alohida repoda: [catalog-frontend](https://github.com/boburbekt/catalog-frontend)

## 1. Ishga tushirish (Docker)

```bash
cp .env.example .env     # ixtiyoriy — barcha qiymatlarning defaulti bor
docker compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

Backend birinchi ishga tushganda jadvallarni yaratadi va `demo-mebel` do‘koni uchun demo ma’lumotlarni kiritadi.

## 2. Ishga tushirish (Docker'siz)

PostgreSQL alohida ishlab turgan bo‘lsa:

```bash
pip install -e .
export DATABASE_URL=postgresql+asyncpg://catalog:catalog_password@localhost:5432/mebel_catalog
uvicorn app.main:app --reload
```

## 3. Muhit o‘zgaruvchilari

| O‘zgaruvchi | Default | Izoh |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://catalog:catalog_password@db:5432/mebel_catalog` | asyncpg drayveri majburiy |
| `CORS_ORIGINS` | `http://localhost:3000` | vergul bilan ajratilgan ro‘yxat |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `mebel_catalog` / `catalog` / `catalog_password` | faqat compose'dagi `db` servisi uchun |
| `ORDER_RATE_LIMIT_PER_MINUTE` | `5` | bitta IP daqiqasiga nechta buyurtma bera oladi (anti-spam) |

## 4. API

Public (katalog):

- `GET /api/public/shops/{shop_slug}` — do‘kon + kategoriyalar + mahsulotlar (`?category=`, `?search=`)
- `GET /api/public/shops/{shop_slug}/products/{product_slug}` — mahsulot tafsiloti
- `POST /api/public/shops/{shop_slug}/visits` — tashrif eventi (statistika; GET so‘rovlari tashrif yozmaydi)
- `POST /api/public/shops/{shop_slug}/orders` — buyurtma yuborish (`consent` majburiy)

Admin (demo, **autentifikatsiyasiz**):

- `GET /api/admin/products?business_slug=demo-mebel`
- `POST /api/admin/products`

`GET /health` — healthcheck.

## 5. Ma’lumotlar bazasi

Sxema: [`docs/database-schema.md`](docs/database-schema.md).

Hozircha migratsiya yo‘q — jadvallar startupda `Base.metadata.create_all` orqali yaratiladi. **`create_all` mavjud jadvallarni o‘zgartirmaydi**, shuning uchun modelni o‘zgartirgandan keyin volume'ni o‘chirish kerak:

```bash
docker compose down -v && docker compose up --build
```

## 6. Muhim arxitektura qoidasi

Barcha biznesga tegishli obyektlarda `business_id` mavjud va do‘kon har doim URL'dagi `slug` orqali aniqlanadi. Shu sababli bitta backend va bitta database ichida ko‘p do‘kon xavfsiz ajratiladi. Yangi endpoint qo‘shganda so‘rovni albatta `business_id` bo‘yicha cheklang.

## 7. Anti-spam (buyurtma tezligi cheklovi)

Buyurtma endpointi oddiy **in-process** (jarayon ichidagi) rate limiter bilan himoyalangan: bitta IP
uchun `ORDER_RATE_LIMIT_PER_MINUTE` (default 5) dan ko‘p buyurtma bo‘lsa `429` qaytadi. Bundan tashqari
so‘rovda majburiy `consent: true` va yashirin **honeypot** maydoni tekshiriladi (bot to‘ldirsa `400`).

> ⚠️ **Bir jarayon cheklovi.** Limiter holati faqat shu Python jarayonining xotirasida saqlanadi.
> Bir nechta uvicorn worker yoki replika ishlatilsa, har biri o‘z hisobini yuritadi va cheklov global
> bo‘lmaydi. Ishonchli, taqsimlangan cheklov uchun Redis kabi umumiy do‘kon kerak (MVP doirasida
> ataylab qo‘shilmagan).

## 8. Keyingi ishlar

- Admin autentifikatsiyasi
- Alembic migratsiyalari
- Rasm yuklash va S3-compatible storage
- Excel import
- QR generator va QR scan analytics
- Mijoz kabineti
- Telegram Mini App `initData` validatsiyasi
- Obuna va tariflar
