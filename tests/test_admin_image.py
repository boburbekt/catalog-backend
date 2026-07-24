"""3-bosqich: mahsulot rasmini yuklash — MIME, hajm, haqiqiylik va xavfsiz almashtirish."""

import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Product

ALFA = {"X-Admin-Token": "alfa-token"}


def make_image(fmt: str = "JPEG", size: tuple[int, int] = (120, 90)) -> bytes:
    img = Image.new("RGB", size, (200, 120, 60))
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Har bir test rasmni izolyatsiyalangan vaqtinchalik papkaga yozadi."""
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


async def _product_id(db, slug: str) -> int:
    return (await db.scalar(select(Product).where(Product.slug == slug))).id


async def test_boshqa_tenant_productiga_upload_404(client, shops, db):
    beta_id = await _product_id(db, "beta-stol")
    response = await client.post(
        f"/api/admin/products/{beta_id}/image",
        headers=ALFA,
        files={"file": ("x.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 404


async def test_notogri_mime_rad(client, shops, db):
    alfa_id = await _product_id(db, "alfa-divan")
    response = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": ("note.txt", b"salom", "text/plain")},
    )
    assert response.status_code == 400


async def test_fake_jpg_rad(client, shops, db):
    """content-type image/jpeg, lekin tarkibi rasm emas — Pillow rad etadi."""
    alfa_id = await _product_id(db, "alfa-divan")
    response = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": ("fake.jpg", b"bu haqiqiy rasm emas", "image/jpeg")},
    )
    assert response.status_code == 400


async def test_katta_fayl_413(client, shops, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 1)
    alfa_id = await _product_id(db, "alfa-divan")
    big = b"\xff" * (1 * 1024 * 1024 + 16)  # 1 MB dan biroz katta
    response = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": ("big.jpg", big, "image/jpeg")},
    )
    assert response.status_code == 413


@pytest.mark.parametrize("fmt,content_type", [("JPEG", "image/jpeg"), ("PNG", "image/png")])
async def test_haqiqiy_rasm_webpga(client, shops, db, upload_dir, fmt, content_type):
    alfa_id = await _product_id(db, "alfa-divan")
    response = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": (f"real.{fmt.lower()}", make_image(fmt), content_type)},
    )
    assert response.status_code == 200
    body = response.json()
    # image_url yangilandi va WebP'ga ishora qiladi.
    assert body["image_url"].startswith(f"/uploads/{shops['alfa'].id}/")
    assert body["image_url"].endswith(".webp")

    # Disk'dagi fayl haqiqatan WebP.
    saved = upload_dir / body["image_url"].split("/uploads/")[1]
    assert saved.is_file()
    with Image.open(saved) as img:
        assert img.format == "WEBP"


async def test_eski_fayl_xavfsiz_almashtiriladi(client, shops, db, upload_dir):
    alfa_id = await _product_id(db, "alfa-divan")

    # Birinchi yuklash — eski fayl.
    first = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": ("a.jpg", make_image(), "image/jpeg")},
    )
    old_url = first.json()["image_url"]
    old_path = upload_dir / old_url.split("/uploads/")[1]
    assert old_path.is_file()

    # Ikkinchi yuklash — yangi fayl, eskisi o‘chishi kerak.
    second = await client.post(
        f"/api/admin/products/{alfa_id}/image",
        headers=ALFA,
        files={"file": ("b.png", make_image("PNG"), "image/png")},
    )
    new_url = second.json()["image_url"]
    new_path = upload_dir / new_url.split("/uploads/")[1]

    assert new_url != old_url
    assert new_path.is_file()
    assert not old_path.exists()  # eski fayl xavfsiz o‘chirildi
