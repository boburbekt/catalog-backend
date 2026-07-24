from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.rate_limit import order_rate_limiter
from app.db.session import AsyncSessionLocal, get_db
from app.models import Business, Category, Order, OrderItem, Product, normalize_source
from app.schemas.catalog import (
    CatalogOut,
    OrderCreate,
    OrderCreated,
    ProductOut,
    SitemapOut,
    SitemapProduct,
    SitemapShop,
    VisitCreate,
)
from app.services.analytics import record_visit
from app.services.telegram import build_order_message, send_order_notification

router = APIRouter(prefix="/public", tags=["public catalog"])


@router.get("/sitemap", response_model=SitemapOut)
async def get_sitemap(db: AsyncSession = Depends(get_db)) -> SitemapOut:
    """SEO uchun: faol do‘kon slug'lari va ko‘rinadigan mahsulot slug'lari + `updated_at`.

    Absolute URL va XML Nuxt tomonida quriladi — bu endpoint faqat xom ma'lumot beradi.
    """
    shop_rows = (
        await db.execute(
            select(Business.slug, Business.updated_at)
            .where(Business.is_active.is_(True))
            .order_by(Business.slug)
        )
    ).all()

    # Faqat faol do‘konlarning ko‘rinadigan mahsulotlari (inactive do‘kon mahsulotlari chiqmaydi).
    product_rows = (
        await db.execute(
            select(Business.slug, Product.slug, Product.updated_at)
            .join(Business, Product.business_id == Business.id)
            .where(Business.is_active.is_(True), Product.is_visible.is_(True))
            .order_by(Business.slug, Product.slug)
        )
    ).all()

    return SitemapOut(
        shops=[SitemapShop(slug=slug, updated_at=updated_at) for slug, updated_at in shop_rows],
        products=[
            SitemapProduct(shop_slug=shop_slug, slug=slug, updated_at=updated_at)
            for shop_slug, slug, updated_at in product_rows
        ],
    )


@router.get("/shops/{shop_slug}", response_model=CatalogOut)
async def get_catalog(
    shop_slug: str,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CatalogOut:
    business_query = (
        select(Business)
        # Public katalogda faqat active kategoriyalar ko‘rsatiladi.
        .options(selectinload(Business.categories.and_(Category.is_active.is_(True))))
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
        # Inactive kategoriya slug'i bilan ham public mahsulotlar chiqmasligi kerak.
        filters.append(Category.slug == category)
        filters.append(Category.is_active.is_(True))
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

    # Tashrif bu yerda YOZILMAYDI — statistika endi faqat explicit `POST .../visits` orqali.
    return CatalogOut(business=business, products=products, total=total, limit=limit, offset=offset)


@router.get("/shops/{shop_slug}/products/{product_slug}", response_model=ProductOut)
async def get_product(
    shop_slug: str,
    product_slug: str,
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

    # Tashrif bu yerda YOZILMAYDI — `view_count` va tashrif explicit `POST .../visits` orqali.
    return product


@router.post(
    "/shops/{shop_slug}/visits",
    status_code=status.HTTP_201_CREATED,
)
async def track_visit(
    shop_slug: str,
    payload: VisitCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Frontend explicit chaqiradigan tashrif eventi (katalog yoki mahsulot ochilganda bir marta)."""
    business = await db.scalar(
        select(Business).where(Business.slug == shop_slug, Business.is_active.is_(True))
    )
    if not business:
        raise HTTPException(status_code=404, detail="Do‘kon topilmadi")

    if payload.product_id is not None:
        # Mahsulot shu tenantga tegishli va ko‘rinadigan bo‘lishi shart; aks holda 404 (cross-tenant leak yo‘q).
        product = await db.scalar(
            select(Product.id).where(
                Product.id == payload.product_id,
                Product.business_id == business.id,
                Product.is_visible.is_(True),
            )
        )
        if not product:
            raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    await record_visit(
        db,
        business_id=business.id,
        product_id=payload.product_id,
        source=payload.source,
        path=payload.path,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "recorded"}


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
    # Honeypot: haqiqiy foydalanuvchi bu yashirin maydonni bo‘sh qoldiradi; to‘lgan bo‘lsa — bot.
    if payload.honeypot:
        raise HTTPException(status_code=400, detail="Buyurtma rad etildi")

    # Anti-spam: bitta IP uchun jarayon ichidagi tezlik cheklovi (limit config orqali).
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not order_rate_limiter.allow(client_ip, settings.order_rate_limit_per_minute, 60.0):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Juda ko‘p buyurtma yuborildi. Bir oz kuting.",
        )

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
