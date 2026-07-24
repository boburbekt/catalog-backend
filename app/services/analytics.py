import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogVisit, Product, normalize_source

logger = logging.getLogger(__name__)


async def record_visit(
    db: AsyncSession,
    *,
    business_id: int,
    product_id: int | None = None,
    source: str | None = None,
    path: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Tashrifni yozadi va mahsulot bo‘lsa `view_count`ni atomik oshiradi.

    Statistika hech qachon sahifani yiqitmasligi kerak — DB xatosi yutiladi, faqat log yoziladi.
    Tenantga tegishlilik va ko‘rinuvchanlik tekshiruvi chaqiruvchi (endpoint)da bajariladi.
    """
    try:
        db.add(
            CatalogVisit(
                business_id=business_id,
                product_id=product_id,
                source=normalize_source(source),
                path=path[:300] if path else None,
                user_agent=user_agent[:400] if user_agent else None,
            )
        )
        if product_id is not None:
            # Atomik: `view_count = view_count + 1` bevosita DB'da bajariladi (race'siz).
            await db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(view_count=Product.view_count + 1)
            )
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Tashrifni yozib bo‘lmadi")
        await db.rollback()
