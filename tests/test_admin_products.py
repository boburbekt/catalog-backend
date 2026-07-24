"""1-bosqich: mahsulot CRUD (PATCH / DELETE) va multi-tenant izolyatsiyasi."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Category, Order, OrderItem, Product

ALFA = {"X-Admin-Token": "alfa-token"}
BETA = {"X-Admin-Token": "beta-token"}


async def _product(db, slug: str) -> Product:
    return await db.scalar(select(Product).where(Product.slug == slug))


# --- PATCH: multi-tenant izolyatsiya ---------------------------------------


async def test_boshqa_tenant_mahsuloti_patch_404(client, shops, db):
    beta_stol = await _product(db, "beta-stol")
    response = await client.patch(
        f"/api/admin/products/{beta_stol.id}", headers=ALFA, json={"price": "111"}
    )
    assert response.status_code == 404
    # Boshqa do‘kon mahsuloti o‘zgarmagan bo‘lishi kerak.
    await db.refresh(beta_stol)
    assert beta_stol.price == Decimal("3000000")


async def test_faqat_price_yangilanadi_name_ozgarmaydi(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"price": "1500000"}
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["price"]) == Decimal("1500000")
    assert body["name"] == "Alfa divan"  # tegilmagan maydon o‘zgarmaydi


async def test_name_null_422(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"name": None}
    )
    assert response.status_code == 422


async def test_notanish_maydon_422(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"foo": "bar"}
    )
    assert response.status_code == 422


async def test_category_id_null_bilan_tozalanadi(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    assert alfa_divan.category_id is not None
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"category_id": None}
    )
    assert response.status_code == 200
    assert response.json()["category"] is None
    await db.refresh(alfa_divan)
    assert alfa_divan.category_id is None


async def test_boshqa_tenant_kategoriyasi_404(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    beta_category = await db.scalar(
        select(Category).where(Category.business_id == shops["beta"].id)
    )
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}",
        headers=ALFA,
        json={"category_id": beta_category.id},
    )
    assert response.status_code == 404


async def test_duplicate_slug_409(client, shops, db):
    # `yashirin-divan` allaqachon mavjud; `alfa-divan`ni o‘shanga o‘tkazib bo‘lmaydi.
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"slug": "yashirin-divan"}
    )
    assert response.status_code == 409


async def test_visible_false_public_katalogda_chiqmaydi(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.patch(
        f"/api/admin/products/{alfa_divan.id}", headers=ALFA, json={"is_visible": False}
    )
    assert response.status_code == 200
    assert response.json()["is_visible"] is False

    catalog = await client.get("/api/public/shops/alfa-mebel")
    slugs = {product["slug"] for product in catalog.json()["products"]}
    assert "alfa-divan" not in slugs


# --- DELETE ----------------------------------------------------------------


async def test_boshqa_tenant_mahsuloti_delete_404(client, shops, db):
    beta_stol = await _product(db, "beta-stol")
    response = await client.delete(f"/api/admin/products/{beta_stol.id}", headers=ALFA)
    assert response.status_code == 404
    assert await _product(db, "beta-stol") is not None  # o‘chib ketmagan


async def test_buyurtmasi_yoq_mahsulot_delete_204(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    response = await client.delete(f"/api/admin/products/{alfa_divan.id}", headers=ALFA)
    assert response.status_code == 204
    assert await _product(db, "alfa-divan") is None


async def test_buyurtmasi_bor_mahsulot_delete_409(client, shops, db):
    alfa_divan = await _product(db, "alfa-divan")
    order = Order(
        business_id=shops["alfa"].id, customer_name="Ali", customer_phone="+998901112233"
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=alfa_divan.id,
            product_name=alfa_divan.name,
            quantity=1,
            unit_price=alfa_divan.price,
        )
    )
    await db.commit()

    response = await client.delete(f"/api/admin/products/{alfa_divan.id}", headers=ALFA)
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Bu mahsulotda buyurtma tarixi mavjud. Uni o‘chirish o‘rniga yashiring."
    )
    assert await _product(db, "alfa-divan") is not None  # o‘chirilmagan
