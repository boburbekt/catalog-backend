from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import Business, Product
from app.schemas.catalog import AdminProductCreate, ProductOut

router = APIRouter(prefix="/admin", tags=["admin demo"])


@router.get("/products", response_model=list[ProductOut])
async def list_products(business_slug: str = "demo-mebel", db: AsyncSession = Depends(get_db)) -> list[Product]:
    query = (
        select(Product)
        .join(Business)
        .options(selectinload(Product.category))
        .where(Business.slug == business_slug)
        .order_by(Product.id.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(payload: AdminProductCreate, db: AsyncSession = Depends(get_db)) -> Product:
    business = await db.scalar(select(Business).where(Business.slug == payload.business_slug))
    if not business:
        raise HTTPException(status_code=404, detail="Do‘kon topilmadi")

    duplicate = await db.scalar(
        select(Product).where(Product.business_id == business.id, Product.slug == payload.slug)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Bu slug allaqachon mavjud")

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
        image_url=payload.image_url,
        availability=payload.availability,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]
