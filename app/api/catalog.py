from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import Business, Category, Order, OrderItem, Product
from app.schemas.catalog import CatalogOut, OrderCreate, OrderCreated, ProductOut

router = APIRouter(prefix="/public", tags=["public catalog"])


@router.get("/shops/{shop_slug}", response_model=CatalogOut)
async def get_catalog(
    shop_slug: str,
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=80),
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

    product_query = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.business_id == business.id, Product.is_visible.is_(True))
        .order_by(Product.id.desc())
    )
    if category:
        product_query = product_query.join(Category).where(Category.slug == category)
    if search:
        product_query = product_query.where(Product.name.ilike(f"%{search}%"))

    products = list((await db.scalars(product_query)).all())
    return CatalogOut(business=business, products=products)


@router.get("/shops/{shop_slug}/products/{product_slug}", response_model=ProductOut)
async def get_product(shop_slug: str, product_slug: str, db: AsyncSession = Depends(get_db)) -> Product:
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
    return product


@router.post(
    "/shops/{shop_slug}/orders",
    response_model=OrderCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(shop_slug: str, payload: OrderCreate, db: AsyncSession = Depends(get_db)) -> OrderCreated:
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
    )
    db.add(order)
    await db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=payload.quantity,
            unit_price=product.price,
        )
    )
    await db.commit()
    return OrderCreated(id=order.id, status=order.status, message="Buyurtmangiz qabul qilindi")
