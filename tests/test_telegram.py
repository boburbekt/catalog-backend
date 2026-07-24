from decimal import Decimal

from app.services.telegram import build_order_message, send_order_notification


def test_xabar_narx_va_manbani_korsatadi():
    text = build_order_message(
        order_id=7,
        customer_name="Jasurbek",
        customer_phone="+998901234567",
        items=[("Milan divan", 2, Decimal("4850000"))],
        comment="Kulrang bo‘lsin",
        source="qr",
    )

    assert "№7" in text
    assert "Milan divan × 2" in text
    assert "9 700 000 so‘m" in text  # 2 × 4 850 000
    assert "QR kod" in text
    assert "Kulrang bo‘lsin" in text


def test_xabar_html_ni_ekranlaydi():
    """Mijoz kiritgan matn parse_mode=HTML ni buzmasligi kerak."""
    text = build_order_message(
        order_id=1,
        customer_name="<b>hack</b>",
        customer_phone="+998901234567",
        items=[("Stol", 1, Decimal("100"))],
    )

    assert "&lt;b&gt;hack&lt;/b&gt;" in text
    assert "<b>hack</b>" not in text


async def test_token_yoq_bolsa_jimgina_false_qaytaradi():
    assert await send_order_notification(123456, "salom", "+998901234567") is False


async def test_tarmoq_xatosi_exception_kotarmaydi(monkeypatch):
    """Telegram tushib qolsa ham buyurtma oqimi buzilmasligi kerak."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "123:FAKE")

    async def boom(*args, **kwargs):
        raise RuntimeError("tarmoq yo‘q")

    monkeypatch.setattr("httpx.AsyncClient.post", boom)

    assert await send_order_notification(123456, "salom", "+998901234567") is False
