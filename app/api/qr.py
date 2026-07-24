import io
from urllib.parse import quote, urlencode

import segno
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_current_business
from app.db.session import get_db
from app.models import Business, Product, normalize_source

router = APIRouter(prefix="/admin", tags=["admin"])


async def _build_target(
    business: Business,
    product_slug: str | None,
    source: str,
    db: AsyncSession,
) -> tuple[str, str]:
    """Katalog/mahsulot havolasi va yuklab olinadigan fayl nomini qaytaradi."""
    if product_slug:
        owned = await db.scalar(
            select(Product.id).where(
                Product.business_id == business.id,
                Product.slug == product_slug,
            )
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    base = get_settings().public_site_url.rstrip("/")
    path = f"/{quote(business.slug)}"
    if product_slug:
        path += f"/product/{quote(product_slug)}"
    query = urlencode({"source": normalize_source(source)})

    filename = f"qr-{business.slug}" + (f"-{product_slug}" if product_slug else "")
    return f"{base}{path}?{query}", filename


@router.get("/qr", response_class=Response, responses={200: {"content": {"image/png": {}}}})
async def qr_png(
    product_slug: str | None = Query(default=None),
    source: str = Query(default="qr"),
    scale: int = Query(default=10, ge=1, le=40),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Response:
    target, filename = await _build_target(business, product_slug, source, db)
    buffer = io.BytesIO()
    segno.make(target, error="h").save(buffer, kind="png", scale=scale, border=2)
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}.png"'},
    )


@router.get("/qr.svg", response_class=Response, responses={200: {"content": {"image/svg+xml": {}}}})
async def qr_svg(
    product_slug: str | None = Query(default=None),
    source: str = Query(default="qr"),
    scale: int = Query(default=10, ge=1, le=40),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Bosmaxona uchun vektor variant."""
    target, filename = await _build_target(business, product_slug, source, db)
    buffer = io.BytesIO()
    segno.make(target, error="h").save(buffer, kind="svg", scale=scale, border=2)
    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}.svg"'},
    )
