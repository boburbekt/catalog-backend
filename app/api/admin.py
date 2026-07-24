from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_business
from app.db.session import get_db
from app.models import Business, CatalogVisit, Category, Order, Product
from app.schemas.catalog import AdminProductCreate, ProductOut, SourceCount, StatsOut, TopProduct

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> list[Product]:
    query = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.business_id == business.id)
        .order_by(Product.position, Product.id.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: AdminProductCreate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Product:
    duplicate = await db.scalar(
        select(Product).where(Product.business_id == business.id, Product.slug == payload.slug)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Bu slug allaqachon mavjud")

    if payload.category_id is not None:
        owned = await db.scalar(
            select(Category.id).where(
                Category.id == payload.category_id,
                Category.business_id == business.id,
            )
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    product = Product(
        business_id=business.id,
        category_id=payload.category_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price=payload.price,
        old_price=payload.old_price,
        material=payload.material,
        dimensions=payload.dimensions,
        color=payload.color,
        sku=payload.sku,
        image_url=payload.image_url,
        availability=payload.availability,
        position=payload.position,
    )
    db.add(product)
    await db.commit()
    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    since = datetime.now(UTC) - timedelta(days=days)

    source_rows = (
        await db.execute(
            select(CatalogVisit.source, func.count())
            .where(CatalogVisit.business_id == business.id, CatalogVisit.created_at >= since)
            .group_by(CatalogVisit.source)
            .order_by(func.count().desc())
        )
    ).all()

    total_orders = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.business_id == business.id, Order.created_at >= since)
    )

    top_rows = (
        await db.execute(
            select(Product.id, Product.name, Product.slug, func.count(CatalogVisit.id).label("visits"))
            .join(CatalogVisit, CatalogVisit.product_id == Product.id)
            .where(CatalogVisit.business_id == business.id, CatalogVisit.created_at >= since)
            .group_by(Product.id, Product.name, Product.slug)
            .order_by(func.count(CatalogVisit.id).desc())
            .limit(10)
        )
    ).all()

    by_source = [SourceCount(source=source, visits=count) for source, count in source_rows]
    return StatsOut(
        days=days,
        total_visits=sum(item.visits for item in by_source),
        total_orders=total_orders or 0,
        by_source=by_source,
        top_products=[
            TopProduct(id=row.id, name=row.name, slug=row.slug, visits=row.visits) for row in top_rows
        ],
    )
