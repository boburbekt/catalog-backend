"""4-bosqich: kategoriya CRUD — tenant izolyatsiya, unique slug, public filtr, delete detach."""

import pytest
from sqlalchemy import func, select

from app.models import Category, Product

ALFA = {"X-Admin-Token": "alfa-token"}
BETA = {"X-Admin-Token": "beta-token"}


async def test_tenant_isolation_list(client, shops):
    await client.post("/api/admin/categories", headers=ALFA, json={"name": "Yangi", "slug": "yangi"})

    alfa = await client.get("/api/admin/categories", headers=ALFA)
    alfa_slugs = {c["slug"] for c in alfa.json()}
    assert {"divanlar", "yangi"} <= alfa_slugs

    beta = await client.get("/api/admin/categories", headers=BETA)
    beta_slugs = {c["slug"] for c in beta.json()}
    assert "divanlar" not in beta_slugs and "yangi" not in beta_slugs
    assert "stollar" in beta_slugs


async def test_duplicate_slug_409(client, shops):
    response = await client.post(
        "/api/admin/categories", headers=ALFA, json={"name": "Boshqa", "slug": "divanlar"}
    )
    assert response.status_code == 409


async def test_bir_xil_slug_boshqa_tenantda_ruxsat(client, shops):
    response = await client.post(
        "/api/admin/categories", headers=BETA, json={"name": "Divanlar", "slug": "divanlar"}
    )
    assert response.status_code == 201


async def test_admin_active_va_inactive_position_boyicha(client, shops):
    await client.post(
        "/api/admin/categories",
        headers=ALFA,
        json={"name": "C", "slug": "c", "position": 5, "is_active": False},
    )
    await client.post(
        "/api/admin/categories", headers=ALFA, json={"name": "A", "slug": "a", "position": 1}
    )
    response = await client.get("/api/admin/categories", headers=ALFA)
    cats = response.json()

    positions = [c["position"] for c in cats]
    assert positions == sorted(positions)  # position bo‘yicha tartiblangan
    assert any(c["is_active"] is False for c in cats)  # inactive ham ko‘rinadi


async def test_inactive_kategoriya_public_filtrda_chiqmaydi(client, shops):
    await client.post(
        "/api/admin/categories",
        headers=ALFA,
        json={"name": "Yashirin", "slug": "yashirin-kat", "is_active": False},
    )
    public = await client.get("/api/public/shops/alfa-mebel")
    slugs = {c["slug"] for c in public.json()["business"]["categories"]}
    assert "yashirin-kat" not in slugs
    assert "divanlar" in slugs  # active kategoriya ko‘rinadi


async def test_delete_category_mahsulotlarni_null_qiladi(client, shops, db):
    cat = await db.scalar(
        select(Category).where(Category.business_id == shops["alfa"].id, Category.slug == "divanlar")
    )
    response = await client.delete(f"/api/admin/categories/{cat.id}", headers=ALFA)
    assert response.status_code == 200
    # Fixture'da alfa'ning 2 mahsuloti shu kategoriyada edi.
    assert response.json() == {"id": cat.id, "detached_products": 2}

    still_attached = await db.scalar(
        select(func.count()).select_from(Product).where(Product.category_id == cat.id)
    )
    assert still_attached == 0
    assert await db.scalar(select(Category).where(Category.id == cat.id)) is None


async def test_boshqa_tenant_patch_404(client, shops, db):
    beta_cat = await db.scalar(select(Category).where(Category.business_id == shops["beta"].id))
    response = await client.patch(
        f"/api/admin/categories/{beta_cat.id}", headers=ALFA, json={"name": "O‘g‘irlangan"}
    )
    assert response.status_code == 404


async def test_boshqa_tenant_delete_404(client, shops, db):
    beta_cat = await db.scalar(select(Category).where(Category.business_id == shops["beta"].id))
    response = await client.delete(f"/api/admin/categories/{beta_cat.id}", headers=ALFA)
    assert response.status_code == 404


async def test_patch_active_toggle(client, shops, db):
    cat = await db.scalar(select(Category).where(Category.business_id == shops["alfa"].id))
    response = await client.patch(
        f"/api/admin/categories/{cat.id}", headers=ALFA, json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["name"] == "Divanlar"  # tegilmagan maydon o‘zgarmaydi


async def test_notanish_maydon_422(client, shops, db):
    cat = await db.scalar(select(Category).where(Category.business_id == shops["alfa"].id))
    response = await client.patch(
        f"/api/admin/categories/{cat.id}", headers=ALFA, json={"foo": "bar"}
    )
    assert response.status_code == 422
