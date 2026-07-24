"""Admin self-service: GET/PATCH /api/admin/me."""


async def test_me_returns_own_business_without_token(client, shops):
    response = await client.get("/api/admin/me", headers={"X-Admin-Token": "alfa-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "alfa-mebel"
    # Token/hash hech qachon chiqmaydi.
    assert "admin_token" not in body
    assert "admin_token_hash" not in body


async def test_me_tenant_isolation(client, shops):
    """Har token faqat o‘z biznesini ko‘radi."""
    alfa = (await client.get("/api/admin/me", headers={"X-Admin-Token": "alfa-token"})).json()
    beta = (await client.get("/api/admin/me", headers={"X-Admin-Token": "beta-token"})).json()
    assert alfa["slug"] == "alfa-mebel"
    assert beta["slug"] == "beta-mebel"
    assert alfa["id"] != beta["id"]


async def test_me_updates_allowed_fields(client, shops):
    response = await client.patch(
        "/api/admin/me",
        headers={"X-Admin-Token": "alfa-token"},
        json={
            "name": "Alfa Mebel Pro",
            "phone": "+998 91 111 22 33",
            "instagram": "alfa_mebel",
            "notify_telegram_chat_id": 123456,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alfa Mebel Pro"
    assert body["phone"] == "+998 91 111 22 33"
    assert body["instagram"] == "alfa_mebel"
    assert body["notify_telegram_chat_id"] == 123456
    # slug o‘zgarmagan.
    assert body["slug"] == "alfa-mebel"


async def test_me_cannot_change_slug(client, shops, db):
    from sqlalchemy import select

    from app.models import Business

    response = await client.patch(
        "/api/admin/me",
        headers={"X-Admin-Token": "alfa-token"},
        json={"slug": "boshqa-slug"},
    )
    # `extra="forbid"` — ruxsatsiz maydon 422.
    assert response.status_code == 422

    business = await db.scalar(select(Business).where(Business.id == shops["alfa"].id))
    assert business.slug == "alfa-mebel"


async def test_me_cannot_change_is_active(client, shops, db):
    from sqlalchemy import select

    from app.models import Business

    response = await client.patch(
        "/api/admin/me",
        headers={"X-Admin-Token": "alfa-token"},
        json={"is_active": False},
    )
    assert response.status_code == 422

    business = await db.scalar(select(Business).where(Business.id == shops["alfa"].id))
    assert business.is_active is True


async def test_me_cannot_change_token(client, shops):
    response = await client.patch(
        "/api/admin/me",
        headers={"X-Admin-Token": "alfa-token"},
        json={"admin_token_hash": "zararli"},
    )
    assert response.status_code == 422


async def test_me_requires_token(client, shops):
    assert (await client.get("/api/admin/me")).status_code == 401
    assert (
        await client.patch("/api/admin/me", json={"name": "X"})
    ).status_code == 401
