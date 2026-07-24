"""Mahsulot rasmlarini tekshirish, WebP'ga o‘tkazish va xavfsiz saqlash."""

import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Faqat quyidagi haqiqiy formatlar qabul qilinadi (content-type'ga emas, Pillow aniqlagan formatga tayanamiz).
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Maksimal tomon ~2000px; aspect ratio saqlanadi (faqat kichraytiradi).
MAX_DIMENSION = 2000
# Decompression bomb himoyasi: bu chegaradan katta piksel soni rad etiladi.
Image.MAX_IMAGE_PIXELS = 40_000_000


class InvalidImageError(Exception):
    """Yuborilgan fayl haqiqiy/qo‘llab-quvvatlanadigan rasm emas."""


def build_webp(data: bytes) -> bytes:
    """Baytlarni tekshiradi va WebP baytlarini qaytaradi. Yaroqsiz bo‘lsa `InvalidImageError`."""
    # 1-bosqich: format va butunlikni tekshirish. `verify()` fayl buzuq emasligini tasdiqlaydi.
    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = probe.format
            probe.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        raise InvalidImageError("Rasmni o‘qib bo‘lmadi") from exc

    if image_format not in ALLOWED_FORMATS:
        raise InvalidImageError("Qo‘llab-quvvatlanmaydigan format")

    # 2-bosqich: `verify()` dan keyin obyekt yaroqsiz — qayta ochib, kichraytirib WebP'ga yozamiz.
    try:
        with Image.open(io.BytesIO(data)) as img:
            has_alpha = img.mode in ("RGBA", "LA", "P")
            img = img.convert("RGBA") if has_alpha else img.convert("RGB")
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))  # aspect ratio saqlanadi
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=82, method=4)
    except (OSError, Image.DecompressionBombError, ValueError) as exc:
        raise InvalidImageError("Rasmni qayta ishlab bo‘lmadi") from exc

    return buffer.getvalue()


def save_webp(webp_bytes: bytes, upload_dir: str, business_id: int) -> tuple[Path, str]:
    """`uploads/{business_id}/{uuid}.webp` ko‘rinishida saqlaydi. Foydalanuvchi filename'i ishlatilmaydi.

    `(fayl yo‘li, public URL)` qaytaradi.
    """
    business_dir = Path(upload_dir) / str(business_id)
    business_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.webp"
    path = business_dir / filename
    path.write_bytes(webp_bytes)
    return path, f"/uploads/{business_id}/{filename}"


def remove_local_image(url: str | None, upload_dir: str) -> None:
    """Eski lokal rasmni xavfsiz o‘chiradi.

    Faqat `/uploads/...` bilan boshlanadigan va `upload_dir` ichidagi fayllar o‘chiriladi —
    tashqi URL'lar va papkadan tashqaridagi yo‘llar (path traversal) e'tiborsiz qoldiriladi.
    """
    if not url or not url.startswith("/uploads/"):
        return
    base = Path(upload_dir).resolve()
    target = (base / url[len("/uploads/"):]).resolve()
    if target.is_relative_to(base) and target.is_file():
        target.unlink(missing_ok=True)
