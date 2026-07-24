from sqlalchemy import select

from app.models import Order, OrderItem


async def test_boshqa_dokon_mahsuloti_korinmaydi(client, shops):
    """Ko‘p ijarachilikning asosiy invarianti: katalog faqat o‘z do‘koni mahsulotlarini qaytaradi."""
    response = await client.get("/api/public/shops/alfa-mebel")
    assert response.status_code == 200

    names = [product["name"] for product in response.json()["products"]]
    assert names == ["Alfa divan"]
    assert "Beta stol" not in names


async def test_boshqa_dokon_mahsulotini_slug_boyicha_ochib_bolmaydi(client, shops):
    response = await client.get("/api/public/shops/alfa-mebel/products/beta-stol")
    assert response.status_code == 404


async def test_yashirin_mahsulot_katalogda_chiqmaydi(client, shops):
    response = await client.get("/api/public/shops/alfa-mebel")
    slugs = [product["slug"] for product in response.json()["products"]]
    assert "yashirin-divan" not in slugs

    detail = await client.get("/api/public/shops/alfa-mebel/products/yashirin-divan")
    assert detail.status_code == 404


async def test_notogri_slug_404(client, shops):
    assert (await client.get("/api/public/shops/yoq-bunday-dokon")).status_code == 404
    assert (await client.get("/api/public/shops/alfa-mebel/products/yoq-bunday")).status_code == 404


async def test_pagination_total_qaytaradi(client, shops):
    response = await client.get("/api/public/shops/alfa-mebel", params={"limit": 1, "offset": 0})
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 1
    assert len(body["products"]) == 1


async def test_buyurtma_togri_business_id_ga_yoziladi(client, shops, db):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    product_id = catalog["products"][0]["id"]

    response = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        params={"source": "qr"},
        json={
            "product_id": product_id,
            "customer_name": "Jasurbek",
            "customer_phone": "+998901234567",
            "quantity": 2,
        },
    )
    assert response.status_code == 201

    order = await db.scalar(select(Order))
    assert order.business_id == shops["alfa"].id
    assert order.source == "qr"

    item = await db.scalar(select(OrderItem))
    assert item.product_name == "Alfa divan"
    assert item.quantity == 2


async def test_boshqa_dokon_mahsulotiga_buyurtma_bermaydi(client, shops):
    beta_catalog = (await client.get("/api/public/shops/beta-mebel")).json()
    beta_product_id = beta_catalog["products"][0]["id"]

    response = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        json={
            "product_id": beta_product_id,
            "customer_name": "Jasurbek",
            "customer_phone": "+998901234567",
        },
    )
    assert response.status_code == 404


async def test_telegram_ochirilganda_ham_buyurtma_201(client, shops, db):
    """TELEGRAM_BOT_TOKEN bo‘sh (test sozlamalarida standart) — buyurtma baribir saqlanishi kerak."""
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()

    response = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        json={
            "product_id": catalog["products"][0]["id"],
            "customer_name": "Dilnoza",
            "customer_phone": "+998901112233",
        },
    )
    assert response.status_code == 201

    order = await db.scalar(select(Order))
    assert order is not None
    assert order.notified_at is None


async def test_notanish_source_direct_ga_tushadi(client, shops, db):
    await client.get("/api/public/shops/alfa-mebel", params={"source": "yolgon-manba"})

    from app.models import CatalogVisit

    visit = await db.scalar(select(CatalogVisit))
    assert visit.source == "direct"
