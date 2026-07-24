from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal, get_db
from app.models import Business, Category, Order, OrderItem, Product, normalize_source
from app.schemas.catalog import CatalogOut, OrderCreate, OrderCreated, ProductOut
from app.services.analytics import track_visit
from app.services.telegram import build_order_message, send_order_notification

router = APIRouter(prefix="/public", tags=["public catalog"])


@router.get("/shops/{shop_slug}", response_model=CatalogOut)
async def get_catalog(
    shop_slug: str,
    request: Request,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CatalogOut:
    business_query = (
        select(Business)
        .options(selectinload(Business.categories))
        .where(Business.slug == shop_slug, Business.is_active.is_(True))
    )
    business = await db.scalar(business_query)
    if not business:
        raise HTTPException(status_code=404, detail="Do‘kon topilmadi")

    filters = [Product.business_id == business.id, Product.is_visible.is_(True)]
    product_query = select(Product).options(selectinload(Product.category))
    count_query = select(func.count()).select_from(Product)
    if category:
        product_query = product_query.join(Category)
        count_query = count_query.join(Category, Product.category_id == Category.id)
        filters.append(Category.slug == category)
    if search:
        filters.append(Product.name.ilike(f"%{search}%"))

    total = await db.scalar(count_query.where(*filters)) or 0
    products = list(
        (
            await db.scalars(
                product_query.where(*filters)
                .order_by(Product.position, Product.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )

    await track_visit(request, db, business_id=business.id)
    return CatalogOut(business=business, products=products, total=total, limit=limit, offset=offset)


@router.get("/shops/{shop_slug}/products/{product_slug}", response_model=ProductOut)
async def get_product(
    shop_slug: str,
    product_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Product:
    query = (
        select(Product)
        .join(Business)
        .options(selectinload(Product.category))
        .where(
            Business.slug == shop_slug,
            Business.is_active.is_(True),
            Product.slug == product_slug,
            Product.is_visible.is_(True),
        )
    )
    product = await db.scalar(query)
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    await track_visit(request, db, business_id=product.business_id, product_id=product.id)
    return product


async def _notify_order(order_id: int, chat_id: int | None, text: str, phone: str) -> None:
    """Buyurtma saqlangandan keyin fon rejimida ishlaydi; xatolar mijozga qaytmaydi."""
    if not chat_id:
        return
    if not await send_order_notification(chat_id, text, phone):
        return
    async with AsyncSessionLocal() as session:
        await session.execute(
            Order.__table__.update().where(Order.id == order_id).values(notified_at=datetime.now(UTC))
        )
        await session.commit()


@router.post(
    "/shops/{shop_slug}/orders",
    response_model=OrderCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    shop_slug: str,
    payload: OrderCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> OrderCreated:
    business = await db.scalar(select(Business).where(Business.slug == shop_slug, Business.is_active.is_(True)))
    if not business:
        raise HTTPException(status_code=404, detail="Do‘kon topilmadi")

    product = await db.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.business_id == business.id,
            Product.is_visible.is_(True),
        )
    )
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    order = Order(
        business_id=business.id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        comment=payload.comment,
        source=normalize_source(request.query_params.get("source")),
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=payload.quantity,
            unit_price=product.price,
        )
    )
    await db.commit()

    message = build_order_message(
        order_id=order.id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        items=[(product.name, payload.quantity, product.price)],
        comment=order.comment,
        source=order.source,
    )
    background_tasks.add_task(
        _notify_order, order.id, business.notify_telegram_chat_id, message, order.customer_phone
    )

    return OrderCreated(id=order.id, status=order.status, message="Buyurtmangiz qabul qilindi")
