import logging
from decimal import Decimal
from html import escape

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
REQUEST_TIMEOUT = 10.0

SOURCE_LABELS = {
    "qr": "QR kod",
    "link": "Havola",
    "instagram": "Instagram",
    "telegram": "Telegram",
    "direct": "To‘g‘ridan-to‘g‘ri",
}


def _money(value: Decimal) -> str:
    return f"{value:,.0f}".replace(",", " ") + " so‘m"


def build_order_message(
    *,
    order_id: int,
    customer_name: str,
    customer_phone: str,
    items: list[tuple[str, int, Decimal]],
    comment: str | None = None,
    source: str = "direct",
) -> str:
    """Telegram uchun HTML matn. `items` — (nomi, miqdori, dona narxi)."""
    lines = [
        f"🛒 <b>Yangi buyurtma №{order_id}</b>",
        "",
        f"👤 {escape(customer_name)}",
        f"📞 {escape(customer_phone)}",
        "",
        "<b>Mahsulotlar:</b>",
    ]

    total = Decimal(0)
    for name, quantity, unit_price in items:
        line_total = unit_price * quantity
        total += line_total
        lines.append(f"• {escape(name)} × {quantity} — {_money(line_total)}")

    lines += ["", f"💰 <b>Jami: {_money(total)}</b>"]
    if comment:
        lines += ["", f"💬 <i>{escape(comment)}</i>"]
    lines += ["", f"📍 Manba: {SOURCE_LABELS.get(source, source)}"]
    return "\n".join(lines)


async def send_order_notification(chat_id: int, text: str, phone: str) -> bool:
    """Bildirishnoma yuboradi. Hech qachon exception ko‘tarmaydi — faqat log yozadi.

    Buyurtma allaqachon saqlangan bo‘ladi, shuning uchun Telegram xatosi mijozga qaytmasligi kerak.
    """
    token = get_settings().telegram_bot_token
    if not token or not chat_id:
        logger.info("Telegram o‘chirilgan (token yoki chat_id yo‘q), bildirishnoma yuborilmadi")
        return False

    # Telegram inline tugmalarida faqat http(s) va tg:// sxemalari ishlaydi — `tel:` 400 qaytaradi,
    # shuning uchun tugma wa.me ga ketadi, raqamning o‘zi esa matnda nusxalash uchun qoladi.
    digits = "".join(char for char in phone if char.isdigit())
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if digits:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": f"📞 {phone}", "url": f"https://wa.me/{digits}"}]]
        }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(f"{TELEGRAM_API}/bot{token}/sendMessage", json=payload)
            if response.status_code >= 400:
                logger.warning("Telegram %s qaytardi: %s", response.status_code, response.text[:300])
                return False
    except Exception:  # noqa: BLE001 — bildirishnoma hech qachon buyurtmani buzmasin
        logger.exception("Telegram bildirishnomasini yuborib bo‘lmadi")
        return False

    return True
