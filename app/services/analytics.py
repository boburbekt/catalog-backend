import logging

from fastapi import Request
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogVisit, Product, normalize_source

logger = logging.getLogger(__name__)


async def track_visit(
    request: Request,
    db: AsyncSession,
    business_id: int,
    product_id: int | None = None,
) -> None:
    """Ko‘rishni yozadi. Statistika hech qachon sahifani yiqitmasligi kerak, shuning uchun xatolar yutiladi."""
    try:
        user_agent = request.headers.get("user-agent")
        db.add(
            CatalogVisit(
                business_id=business_id,
                product_id=product_id,
                source=normalize_source(request.query_params.get("source")),
                path=str(request.url.path)[:300],
                user_agent=user_agent[:400] if user_agent else None,
            )
        )
        if product_id is not None:
            await db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(view_count=Product.view_count + 1)
            )
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Tashrifni yozib bo‘lmadi")
        await db.rollback()
