"""Explicit tashrif tracking + view_count."""
from sqlalchemy import func, select

from app.models import CatalogVisit, Product


async def _alfa_product_id(client):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    return catalog["products"][0]["id"]


async def test_get_katalog_tashrif_yaratmaydi(client, shops, db):
    """GET katalog endi tashrif YOZMAYDI — statistika faqat explicit endpoint orqali."""
    await client.get("/api/public/shops/alfa-mebel")
    count = await db.scalar(select(func.count()).select_from(CatalogVisit))
    assert count == 0


async def test_get_product_tashrif_yaratmaydi(client, shops, db):
    await client.get("/api/public/shops/alfa-mebel/products/alfa-divan")
    count = await db.scalar(select(func.count()).select_from(CatalogVisit))
    assert count == 0


async def test_explicit_katalog_tashrifi_yoziladi(client, shops, db):
    response = await client.post(
        "/api/public/shops/alfa-mebel/visits",
        json={"source": "qr", "path": "/alfa-mebel"},
    )
    assert response.status_code == 201

    visit = await db.scalar(select(CatalogVisit))
    assert visit is not None
    assert visit.business_id == shops["alfa"].id
    assert visit.product_id is None
    assert visit.source == "qr"
    assert visit.path == "/alfa-mebel"


async def test_explicit_product_tashrifi_view_countni_oshiradi(client, shops, db):
    product_id = await _alfa_product_id(client)
    before = await db.scalar(select(Product.view_count).where(Product.id == product_id))

    response = await client.post(
        "/api/public/shops/alfa-mebel/visits",
        json={"product_id": product_id, "source": "link"},
    )
    assert response.status_code == 201

    after = await db.scalar(select(Product.view_count).where(Product.id == product_id))
    assert after == before + 1

    visit = await db.scalar(select(CatalogVisit).where(CatalogVisit.product_id == product_id))
    assert visit.source == "link"


async def test_view_count_har_tashrifda_oshadi(client, shops, db):
    product_id = await _alfa_product_id(client)
    for _ in range(3):
        await client.post(
            "/api/public/shops/alfa-mebel/visits", json={"product_id": product_id}
        )
    count = await db.scalar(select(Product.view_count).where(Product.id == product_id))
    assert count == 3


async def test_boshqa_tenant_product_tashrifi_404(client, shops, db):
    """Beta mahsulotiga alfa do‘koni orqali tashrif → 404, hech narsa yozilmaydi."""
    beta_catalog = (await client.get("/api/public/shops/beta-mebel")).json()
    beta_product_id = beta_catalog["products"][0]["id"]

    response = await client.post(
        "/api/public/shops/alfa-mebel/visits",
        json={"product_id": beta_product_id},
    )
    assert response.status_code == 404

    count = await db.scalar(select(func.count()).select_from(CatalogVisit))
    assert count == 0


async def test_yashirin_product_tashrifi_404(client, shops, db):
    hidden = await db.scalar(select(Product).where(Product.slug == "yashirin-divan"))
    response = await client.post(
        "/api/public/shops/alfa-mebel/visits",
        json={"product_id": hidden.id},
    )
    assert response.status_code == 404


async def test_notogri_source_direct_ga_tushadi(client, shops, db):
    await client.post("/api/public/shops/alfa-mebel/visits", json={"source": "yolgon"})
    visit = await db.scalar(select(CatalogVisit))
    assert visit.source == "direct"


async def test_nofaol_dokon_tashrifi_404(client, shops, db):
    from app.models import Business

    beta = await db.get(Business, shops["beta"].id)
    beta.is_active = False
    await db.commit()

    response = await client.post("/api/public/shops/beta-mebel/visits", json={})
    assert response.status_code == 404
