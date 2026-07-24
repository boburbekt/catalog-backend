from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_business
from app.db.session import get_db
from app.models import Business, CatalogVisit, Category, Order, OrderItem, OrderStatus, Product
from app.schemas.catalog import (
    AdminProductCreate,
    AdminProductUpdate,
    OrderListOut,
    OrderOut,
    OrderStatusUpdate,
    ProductOut,
    SourceCount,
    StatsOut,
    TopProduct,
)

_DUPLICATE_SLUG = "Bu slug allaqachon mavjud"
_ORDER_HISTORY = "Bu mahsulotda buyurtma tarixi mavjud. Uni o‘chirish o‘rniga yashiring."

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
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

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


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: AdminProductUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Product:
    # Tenant-scoped: mahsulot faqat token egasining do‘konidan izlanadi.
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business.id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    data = payload.model_dump(exclude_unset=True)

    # Slug o‘zgarsa, shu do‘kon ichida (o‘zidan boshqa) mahsulotda takrorlanmasin.
    if "slug" in data and data["slug"] != product.slug:
        duplicate = await db.scalar(
            select(Product.id).where(
                Product.business_id == business.id,
                Product.slug == data["slug"],
                Product.id != product.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    # category_id: null → biriktirishni olib tashlash; boshqa tenant kategoriyasi → 404.
    if data.get("category_id") is not None:
        owned = await db.scalar(
            select(Category.id).where(
                Category.id == data["category_id"],
                Category.business_id == business.id,
            )
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    for field, value in data.items():
        setattr(product, field, value)

    try:
        await db.commit()
    except IntegrityError:
        # Ikki so‘rov bir vaqtda bir xil slugni band qilib qolsa — DB unique cheklovi ushlaydi.
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Response:
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business.id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # Buyurtma tarixi bo‘lsa o‘chirmaymiz — mijoz buyurtmalari yo‘qolmasligi kerak.
    has_orders = await db.scalar(
        select(OrderItem.id).where(OrderItem.product_id == product.id).limit(1)
    )
    if has_orders:
        raise HTTPException(status_code=409, detail=_ORDER_HISTORY)

    await db.delete(product)
    try:
        await db.commit()
    except IntegrityError:
        # Race condition: tekshiruvdan keyin buyurtma qo‘shilsa, FK RESTRICT ushlaydi.
        await db.rollback()
        raise HTTPException(status_code=409, detail=_ORDER_HISTORY)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/orders", response_model=OrderListOut)
async def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> OrderListOut:
    since = datetime.now(UTC) - timedelta(days=days)
    filters = [Order.business_id == business.id, Order.created_at >= since]
    if status_filter is not None:
        filters.append(Order.status == status_filter)

    total = await db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    # selectinload — buyurtmalar itemlarini bitta qo‘shimcha so‘rovda oldindan yuklaydi (N+1 yo‘q).
    orders = list(
        (
            await db.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(*filters)
                .order_by(Order.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return OrderListOut(orders=orders, total=total, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.business_id == business.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return order


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.business_id == business.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    order.status = payload.status
    await db.commit()
    # `expire_on_commit=False` — itemlar yuklangicha qoladi, qayta so‘rov shart emas.
    return order


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
