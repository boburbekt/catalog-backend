"""Telefon normalizatsiyasi (E.164)."""
import pytest
from sqlalchemy import select

from app.core.phone import InvalidPhoneError, normalize_phone
from app.models import Order


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+998 90 123 45 67", "+998901234567"),
        ("998901234567", "+998901234567"),
        ("90 123 45 67", "+998901234567"),
        ("+998901234567", "+998901234567"),
        ("(90) 123-45-67", "+998901234567"),
        ("901234567", "+998901234567"),
        ("+1 415 555 0132", "+14155550132"),  # boshqa xalqaro raqam
    ],
)
def test_normalize_valid(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "abc", "12345", "1234567890123456"])
def test_normalize_invalid(raw):
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


async def test_order_phone_normalizatsiya(client, shops, db):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    response = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        json={
            "product_id": catalog["products"][0]["id"],
            "customer_name": "Jasurbek",
            "customer_phone": "90 123 45 67",  # lokal format
            "consent": True,
        },
    )
    assert response.status_code == 201

    order = await db.scalar(select(Order))
    assert order.customer_phone == "+998901234567"


async def test_order_notogri_telefon_422(client, shops):
    catalog = (await client.get("/api/public/shops/alfa-mebel")).json()
    response = await client.post(
        "/api/public/shops/alfa-mebel/orders",
        json={
            "product_id": catalog["products"][0]["id"],
            "customer_name": "Jasurbek",
            "customer_phone": "123",  # juda qisqa
            "consent": True,
        },
    )
    assert response.status_code == 422
