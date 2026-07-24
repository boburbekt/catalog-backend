"""Admin statistikasi: total_products, new_orders, by_day."""
from datetime import UTC, datetime

ALFA = {"X-Admin-Token": "alfa-token"}


async def _alfa_product_id(client):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    return catalog["products"][0]["id"]


async def test_stats_yangi_maydonlar(client, shops):
    product_id = await _alfa_product_id(client)

    # 3 ta tashrif (2 katalog + 1 product) va 1 ta buyurtma.
    await client.post("/api/public/shops/alfa-mebel/visits", json={"source": "qr"})
    await client.post("/api/public/shops/alfa-mebel/visits", json={"source": "link"})
    await client.post(
        "/api/public/shops/alfa-mebel/visits", json={"product_id": product_id, "source": "qr"}
    )
    order = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        json={
            "product_id": product_id,
            "customer_name": "Jasurbek",
            "customer_phone": "+998901234567",
            "consent": True,
        },
    )
    assert order.status_code == 201

    stats = (await client.get("/api/admin/stats", params={"days": 7}, headers=ALFA)).json()

    assert stats["total_products"] == 2  # alfa: ko‘rinadigan + yashirin
    assert stats["total_orders"] == 1
    assert stats["new_orders"] == 1
    assert stats["total_visits"] == 3

    # by_day: aynan `days` ta kun, oxirgisi bugun.
    by_day = stats["by_day"]
    assert len(by_day) == 7
    today = datetime.now(UTC).date().isoformat()
    assert by_day[-1]["date"] == today
    assert by_day[-1]["visits"] == 3
    assert by_day[-1]["orders"] == 1

    # Bo‘sh kunlar 0 bilan qaytadi.
    assert all(day["visits"] == 0 and day["orders"] == 0 for day in by_day[:-1])
    # by_day tashriflari yig‘indisi umumiy tashrifga teng.
    assert sum(day["visits"] for day in by_day) == stats["total_visits"]


async def test_stats_tenant_izolyatsiya(client, shops):
    """Alfa statistikasi beta tashriflarini ko‘rmaydi."""
    await client.post("/api/public/shops/beta-mebel/visits", json={"source": "qr"})

    stats = (await client.get("/api/admin/stats", params={"days": 7}, headers=ALFA)).json()
    assert stats["total_visits"] == 0
    assert stats["total_products"] == 2


async def test_stats_bosh_kunlar_nol(client, shops):
    stats = (await client.get("/api/admin/stats", params={"days": 30}, headers=ALFA)).json()
    assert len(stats["by_day"]) == 30
    assert all(day["visits"] == 0 and day["orders"] == 0 for day in stats["by_day"])
    assert stats["total_visits"] == 0
    assert stats["new_orders"] == 0
