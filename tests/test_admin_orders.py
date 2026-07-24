"""2-bosqich: buyurtmalar API — multi-tenant izolyatsiya, filtrlar, hisob-kitob."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Order, OrderItem, OrderStatus, Product

ALFA = {"X-Admin-Token": "alfa-token"}
BETA = {"X-Admin-Token": "beta-token"}


@pytest.fixture
async def orders(db, shops):
    """Alfa'da 3 ta buyurtma (biri eski, biri `confirmed`), Beta'da 1 ta."""
    alfa_divan = await db.scalar(select(Product).where(Product.slug == "alfa-divan"))
    beta_stol = await db.scalar(select(Product).where(Product.slug == "beta-stol"))

    now = datetime.now(UTC)
    o1 = Order(business_id=shops["alfa"].id, customer_name="Ali", customer_phone="+998901112233")
    o2 = Order(
        business_id=shops["alfa"].id,
        customer_name="Vali",
        customer_phone="+998901112244",
        status=OrderStatus.CONFIRMED,
    )
    # 40 kun oldingi buyurtma — 30 kunlik oynadan tashqarida.
    o3 = Order(
        business_id=shops["alfa"].id,
        customer_name="Eski",
        customer_phone="+998901112255",
        created_at=now - timedelta(days=40),
    )
    o_beta = Order(business_id=shops["beta"].id, customer_name="Beta", customer_phone="+998900000000")
    db.add_all([o1, o2, o3, o_beta])
    await db.flush()

    db.add_all(
        [
            # o1: 2 x 1_000_000 + 1 x 500_000 = 2_500_000
            OrderItem(order_id=o1.id, product_id=alfa_divan.id, product_name=alfa_divan.name, quantity=2, unit_price=Decimal("1000000")),
            OrderItem(order_id=o1.id, product_id=alfa_divan.id, product_name="Yostiq", quantity=1, unit_price=Decimal("500000")),
            OrderItem(order_id=o2.id, product_id=alfa_divan.id, product_name=alfa_divan.name, quantity=1, unit_price=Decimal("1000000")),
            OrderItem(order_id=o_beta.id, product_id=beta_stol.id, product_name=beta_stol.name, quantity=1, unit_price=Decimal("3000000")),
        ]
    )
    await db.commit()
    return {"o1": o1.id, "o2": o2.id, "o3": o3.id, "beta": o_beta.id}


async def test_admin_faqat_oz_buyurtmalarini_koradi(client, orders):
    response = await client.get("/api/admin/orders", headers=ALFA, params={"days": 365})
    assert response.status_code == 200
    body = response.json()
    # Alfa'da 3 ta buyurtma bor; Beta'niki ko‘rinmaydi.
    assert body["total"] == 3
    names = {o["customer_name"] for o in body["orders"]}
    assert names == {"Ali", "Vali", "Eski"}
    assert "Beta" not in names


async def test_boshqa_tenant_detail_404(client, orders):
    response = await client.get(f"/api/admin/orders/{orders['beta']}", headers=ALFA)
    assert response.status_code == 404


async def test_boshqa_tenant_status_update_404(client, orders, db):
    response = await client.patch(
        f"/api/admin/orders/{orders['beta']}", headers=ALFA, json={"status": "confirmed"}
    )
    assert response.status_code == 404
    beta = await db.scalar(select(Order).where(Order.id == orders["beta"]))
    assert beta.status == "new"  # o‘zgarmagan


async def test_items_togri_yuklanadi(client, orders):
    response = await client.get(f"/api/admin/orders/{orders['o1']}", headers=ALFA)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    names = {i["product_name"] for i in body["items"]}
    assert names == {"Alfa divan", "Yostiq"}


async def test_line_total_va_total(client, orders):
    response = await client.get(f"/api/admin/orders/{orders['o1']}", headers=ALFA)
    body = response.json()
    by_name = {i["product_name"]: i for i in body["items"]}
    assert Decimal(by_name["Alfa divan"]["line_total"]) == Decimal("2000000")  # 2 x 1_000_000
    assert Decimal(by_name["Yostiq"]["line_total"]) == Decimal("500000")  # 1 x 500_000
    assert Decimal(body["total"]) == Decimal("2500000")


async def test_status_filtri(client, orders):
    response = await client.get(
        "/api/admin/orders", headers=ALFA, params={"status": "confirmed", "days": 365}
    )
    body = response.json()
    assert body["total"] == 1
    assert body["orders"][0]["customer_name"] == "Vali"
    assert body["orders"][0]["status"] == "confirmed"


async def test_days_filtri(client, orders):
    # 30 kunlik oyna: 40 kun oldingi "Eski" buyurtma tushmaydi.
    response = await client.get("/api/admin/orders", headers=ALFA, params={"days": 30})
    body = response.json()
    assert body["total"] == 2
    assert "Eski" not in {o["customer_name"] for o in body["orders"]}


async def test_pagination_total(client, orders):
    response = await client.get(
        "/api/admin/orders", headers=ALFA, params={"days": 365, "limit": 1, "offset": 0}
    )
    body = response.json()
    # `total` filterlangan umumiy son (3), sahifadagilar esa limit bo‘yicha (1).
    assert body["total"] == 3
    assert len(body["orders"]) == 1
    assert body["limit"] == 1
    assert body["offset"] == 0


async def test_notogri_status_422(client, orders):
    response = await client.patch(
        f"/api/admin/orders/{orders['o1']}", headers=ALFA, json={"status": "yolgon"}
    )
    assert response.status_code == 422


async def test_status_yangilanadi(client, orders, db):
    response = await client.patch(
        f"/api/admin/orders/{orders['o1']}", headers=ALFA, json={"status": "contacted"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "contacted"
    # Javob itemlar bilan qaytadi.
    assert len(response.json()["items"]) == 2


async def test_notanish_maydon_status_update_422(client, orders):
    response = await client.patch(
        f"/api/admin/orders/{orders['o1']}",
        headers=ALFA,
        json={"status": "new", "notified_at": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 422
