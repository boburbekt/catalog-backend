"""SEO sitemap endpointi."""
from app.models import Business


async def test_sitemap_faol_dokon_va_korinadigan_mahsulot(client, shops):
    response = await client.get("/api/public/sitemap")
    assert response.status_code == 200
    body = response.json()

    shop_slugs = {s["slug"] for s in body["shops"]}
    assert shop_slugs == {"alfa-mebel", "beta-mebel"}
    assert all("updated_at" in s for s in body["shops"])

    # Yashirin mahsulot sitemap'da chiqmaydi; ko‘rinadiganlar chiqadi.
    product_slugs = {(p["shop_slug"], p["slug"]) for p in body["products"]}
    assert ("alfa-mebel", "alfa-divan") in product_slugs
    assert ("beta-mebel", "beta-stol") in product_slugs
    assert ("alfa-mebel", "yashirin-divan") not in product_slugs
    assert all("updated_at" in p for p in body["products"])


async def test_sitemap_nofaol_dokon_chiqmaydi(client, shops, db):
    beta = await db.get(Business, shops["beta"].id)
    beta.is_active = False
    await db.commit()

    body = (await client.get("/api/public/sitemap")).json()
    shop_slugs = {s["slug"] for s in body["shops"]}
    assert shop_slugs == {"alfa-mebel"}
    # Nofaol do‘kon mahsulotlari ham sitemap'dan tushib qoladi.
    assert all(p["shop_slug"] != "beta-mebel" for p in body["products"])
