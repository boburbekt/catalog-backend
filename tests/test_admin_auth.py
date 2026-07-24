import pytest
from sqlalchemy import select

from app.models import Product

ADMIN_PATHS = ["/api/admin/products", "/api/admin/stats", "/api/admin/qr", "/api/admin/qr.svg"]


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_tokensiz_401(client, shops, path):
    assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("path", ADMIN_PATHS)
async def test_notogri_token_401(client, shops, path):
    assert (await client.get(path, headers={"X-Admin-Token": "yolgon"})).status_code == 401


async def test_admin_faqat_oz_mahsulotlarini_koradi(client, shops):
    response = await client.get("/api/admin/products", headers={"X-Admin-Token": "alfa-token"})
    assert response.status_code == 200

    slugs = {product["slug"] for product in response.json()}
    # Yashirin mahsulot admin ro‘yxatida ko‘rinadi, boshqa do‘konniki esa yo‘q.
    assert slugs == {"alfa-divan", "yashirin-divan"}


async def test_mahsulot_token_egasining_dokoniga_yoziladi(client, shops, db):
    """Tenant token orqali aniqlanadi — so‘rov tanasida do‘konni tanlash imkoniyati yo‘q."""
    response = await client.post(
        "/api/admin/products",
        headers={"X-Admin-Token": "beta-token"},
        json={"name": "Yangi stol", "slug": "yangi-stol", "price": "500000"},
    )
    assert response.status_code == 201

    product = await db.scalar(select(Product).where(Product.slug == "yangi-stol"))
    assert product.business_id == shops["beta"].id


async def test_body_dagi_business_slug_etiborga_olinmaydi(client, shops, db):
    """`extra="forbid"` bilan noma'lum `business_slug` maydoni rad etiladi (422).

    Tenant faqat token orqali aniqlanadi — so‘rov tanasidan do‘kon tanlab bo‘lmaydi va
    bunday urinish jimgina e'tiborsiz qolmasdan, aniq xato bilan qaytariladi.
    """
    response = await client.post(
        "/api/admin/products",
        headers={"X-Admin-Token": "beta-token"},
        json={
            "business_slug": "alfa-mebel",
            "name": "O‘g‘irlangan divan",
            "slug": "ogirlangan-divan",
            "price": "700000",
        },
    )
    assert response.status_code == 422

    product = await db.scalar(select(Product).where(Product.slug == "ogirlangan-divan"))
    assert product is None


async def test_boshqa_dokon_kategoriyasini_biriktirib_bolmaydi(client, shops, db):
    from app.models import Category

    alfa_category = await db.scalar(select(Category).where(Category.business_id == shops["alfa"].id))
    response = await client.post(
        "/api/admin/products",
        headers={"X-Admin-Token": "beta-token"},
        json={
            "name": "Chalkash mahsulot",
            "slug": "chalkash-mahsulot",
            "price": "100000",
            "category_id": alfa_category.id,
        },
    )
    assert response.status_code == 404


async def test_bir_dokon_ichida_slug_takrorlanmaydi(client, shops):
    response = await client.post(
        "/api/admin/products",
        headers={"X-Admin-Token": "alfa-token"},
        json={"name": "Yana divan", "slug": "alfa-divan", "price": "100000"},
    )
    assert response.status_code == 409


async def test_bir_xil_slug_boshqa_dokonda_ruxsat(client, shops):
    """`(business_id, slug)` juftligi unique — slug faqat do‘kon ichida takrorlanmaydi."""
    response = await client.post(
        "/api/admin/products",
        headers={"X-Admin-Token": "beta-token"},
        json={"name": "Beta divan", "slug": "alfa-divan", "price": "100000"},
    )
    assert response.status_code == 201


async def test_super_token_talab_qilinadi(client):
    response = await client.post(
        "/api/super/businesses",
        json={"name": "Yangi Mebel", "slug": "yangi-mebel"},
    )
    assert response.status_code == 403


async def test_super_token_sozlanmagan_bolsa_hech_kim_kira_olmaydi(client):
    """Standart sozlamada `super_admin_token` bo‘sh — bo‘sh header bilan ham 403 bo‘lishi kerak."""
    response = await client.post(
        "/api/super/businesses",
        headers={"X-Super-Token": ""},
        json={"name": "Yangi Mebel", "slug": "yangi-mebel"},
    )
    assert response.status_code == 403


async def test_super_admin_token_bilan_dokon_yaratadi(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "super_admin_token", "test-super-token")

    response = await client.post(
        "/api/super/businesses",
        headers={"X-Super-Token": "test-super-token"},
        json={"name": "Yangi Mebel", "slug": "yangi-mebel"},
    )
    assert response.status_code == 201

    body = response.json()
    assert body["slug"] == "yangi-mebel"
    assert len(body["admin_token"]) >= 32

    # Qaytgan token darhol ishlashi kerak.
    products = await client.get("/api/admin/products", headers={"X-Admin-Token": body["admin_token"]})
    assert products.status_code == 200
    assert products.json() == []
