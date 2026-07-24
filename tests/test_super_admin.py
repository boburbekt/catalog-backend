"""Super admin biznes boshqaruvi + token xavfsizligi (hash, rotatsiya)."""
import pytest
from sqlalchemy import select

from app.core.security import hash_token
from app.models import Business

SUPER_TOKEN = "test-super-token"


@pytest.fixture
def super_headers(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "super_admin_token", SUPER_TOKEN)
    return {"X-Super-Token": SUPER_TOKEN}


async def _create_business(client, super_headers, slug="yangi-mebel", name="Yangi Mebel"):
    response = await client.post(
        "/api/super/businesses",
        headers=super_headers,
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201
    return response.json()


async def test_create_returns_raw_token_and_db_stores_only_hash(client, super_headers, db):
    body = await _create_business(client, super_headers)
    raw = body["admin_token"]
    assert len(raw) >= 32

    business = await db.scalar(select(Business).where(Business.slug == "yangi-mebel"))
    # Bazada xom token yo‘q — faqat hash, va u xom tokenning hashiga teng.
    assert business.admin_token_hash == hash_token(raw)
    assert business.admin_token_hash != raw


async def test_no_raw_token_anywhere_in_db(client, super_headers, db):
    body = await _create_business(client, super_headers)
    raw = body["admin_token"]

    # Hech bir ustunda xom token saqlanmaganini tekshiramiz.
    hashes = (await db.scalars(select(Business.admin_token_hash))).all()
    assert raw not in hashes
    assert all(len(h) == 64 for h in hashes)


async def test_returned_token_works_immediately(client, super_headers):
    body = await _create_business(client, super_headers)
    resp = await client.get(
        "/api/admin/products", headers={"X-Admin-Token": body["admin_token"]}
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_rotate_old_token_401_new_token_works(client, super_headers):
    body = await _create_business(client, super_headers)
    old_token = body["admin_token"]
    business_id = body["id"]

    # Rotatsiyadan oldin eski token ishlaydi.
    assert (
        await client.get("/api/admin/me", headers={"X-Admin-Token": old_token})
    ).status_code == 200

    rotate = await client.post(
        f"/api/super/businesses/{business_id}/rotate-token", headers=super_headers
    )
    assert rotate.status_code == 200
    new_token = rotate.json()["admin_token"]
    assert new_token != old_token

    # Eski token darhol ishlamay qoladi.
    assert (
        await client.get("/api/admin/me", headers={"X-Admin-Token": old_token})
    ).status_code == 401
    # Yangi token ishlaydi.
    assert (
        await client.get("/api/admin/me", headers={"X-Admin-Token": new_token})
    ).status_code == 200


async def test_super_list_hides_token_and_hash(client, super_headers, shops):
    response = await client.get("/api/super/businesses", headers=super_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    for item in items:
        assert "admin_token" not in item
        assert "admin_token_hash" not in item
        # Kutilgan maydonlar bor.
        assert {"id", "name", "slug", "is_active", "notify_telegram_chat_id"} <= item.keys()


async def test_super_list_requires_super_token(client, shops):
    assert (await client.get("/api/super/businesses")).status_code == 403


async def test_super_patch_updates_fields(client, super_headers, shops):
    alfa_id = shops["alfa"].id
    response = await client.patch(
        f"/api/super/businesses/{alfa_id}",
        headers=super_headers,
        json={"name": "Alfa Yangi", "is_active": False, "phone": "+998 90 000 00 00"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alfa Yangi"
    assert body["is_active"] is False
    assert body["phone"] == "+998 90 000 00 00"
    assert "admin_token" not in body


async def test_super_patch_duplicate_slug_409(client, super_headers, shops):
    alfa_id = shops["alfa"].id
    response = await client.patch(
        f"/api/super/businesses/{alfa_id}",
        headers=super_headers,
        json={"slug": "beta-mebel"},
    )
    assert response.status_code == 409


async def test_super_create_duplicate_slug_409(client, super_headers, shops):
    response = await client.post(
        "/api/super/businesses",
        headers=super_headers,
        json={"name": "Takror", "slug": "alfa-mebel"},
    )
    assert response.status_code == 409


async def test_rotate_requires_super_token(client, shops):
    business_id = shops["alfa"].id
    assert (
        await client.post(f"/api/super/businesses/{business_id}/rotate-token")
    ).status_code == 403
