"""Consent, honeypot va IP bo‘yicha tezlik cheklovi."""
from sqlalchemy import func, select

from app.models import Order


async def _order_body(client, **overrides):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    body = {
        "product_id": catalog["products"][0]["id"],
        "customer_name": "Jasurbek",
        "customer_phone": "+998901234567",
        "consent": True,
    }
    body.update(overrides)
    return body


async def test_consent_false_422(client, shops, db):
    body = await _order_body(client, consent=False)
    response = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
    assert response.status_code == 422
    assert await db.scalar(select(func.count()).select_from(Order)) == 0


async def test_consent_yoq_422(client, shops):
    body = await _order_body(client)
    del body["consent"]
    response = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
    assert response.status_code == 422


async def test_honeypot_toldirilsa_rad(client, shops, db):
    body = await _order_body(client, honeypot="http://spam.example")
    response = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
    assert response.status_code == 400
    # Buyurtma saqlanmaydi.
    assert await db.scalar(select(func.count()).select_from(Order)) == 0


async def test_honeypot_bosh_bolsa_qabul(client, shops):
    body = await _order_body(client, honeypot="")
    response = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
    assert response.status_code == 201


async def test_rate_limit_429(client, shops, monkeypatch):
    """Config'dagi limit (bu yerda 2) oshsa — 429. Limiter jarayon ichida, IP bo‘yicha."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "order_rate_limit_per_minute", 2)

    body = await _order_body(client)
    # Ruxsat etilgan 2 ta.
    assert (await client.post("/api/public/shops/alfa-mebel/orders", json=body)).status_code == 201
    assert (await client.post("/api/public/shops/alfa-mebel/orders", json=body)).status_code == 201
    # 3-si limitdan oshadi.
    third = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
    assert third.status_code == 429


async def test_rate_limit_config_orqali_boshqariladi(client, shops, monkeypatch):
    """Limitni oshirsak — ko‘proq buyurtmaga ruxsat beriladi."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "order_rate_limit_per_minute", 10)

    body = await _order_body(client)
    for _ in range(6):
        resp = await client.post("/api/public/shops/alfa-mebel/orders", json=body)
        assert resp.status_code == 201
