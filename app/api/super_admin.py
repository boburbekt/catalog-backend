from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_admin_token, hash_token, require_superadmin
from app.db.session import get_db
from app.models import Business
from app.schemas.catalog import (
    BusinessAdminOut,
    BusinessCreate,
    BusinessCreated,
    SuperBusinessUpdate,
    TokenRotated,
)

router = APIRouter(prefix="/super", tags=["super admin"], dependencies=[Depends(require_superadmin)])

_DUPLICATE_SLUG = "Bu slug allaqachon band"


@router.post("/businesses", response_model=BusinessCreated, status_code=status.HTTP_201_CREATED)
async def create_business(
    payload: BusinessCreate,
    db: AsyncSession = Depends(get_db),
) -> BusinessCreated:
    existing = await db.scalar(select(Business).where(Business.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    # Xom token faqat shu yerda mavjud bo‘ladi; bazaga faqat uning hashi yoziladi.
    raw_token = generate_admin_token()
    business = Business(**payload.model_dump(), admin_token_hash=hash_token(raw_token))
    db.add(business)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)
    await db.refresh(business)
    return BusinessCreated(
        id=business.id, name=business.name, slug=business.slug, admin_token=raw_token
    )


@router.get("/businesses", response_model=list[BusinessAdminOut])
async def list_businesses(
    db: AsyncSession = Depends(get_db),
) -> list[Business]:
    # Token/hash `BusinessAdminOut` sxemasida yo‘q — javobda hech qachon ko‘rinmaydi.
    query = select(Business).order_by(Business.id)
    return list((await db.scalars(query)).all())


@router.patch("/businesses/{business_id}", response_model=BusinessAdminOut)
async def update_business(
    business_id: int,
    payload: SuperBusinessUpdate,
    db: AsyncSession = Depends(get_db),
) -> Business:
    business = await db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Biznes topilmadi")

    data = payload.model_dump(exclude_unset=True)

    # Slug o‘zgarsa, u boshqa biznesda band bo‘lmasligi kerak (slug global unikal).
    if "slug" in data and data["slug"] != business.slug:
        duplicate = await db.scalar(
            select(Business.id).where(
                Business.slug == data["slug"], Business.id != business.id
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    for field, value in data.items():
        setattr(business, field, value)

    try:
        await db.commit()
    except IntegrityError:
        # Ikki so‘rov bir vaqtda bir xil slugni band qilib qolsa — DB unique cheklovi ushlaydi.
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)
    await db.refresh(business)
    return business


@router.post("/businesses/{business_id}/rotate-token", response_model=TokenRotated)
async def rotate_token(
    business_id: int,
    db: AsyncSession = Depends(get_db),
) -> TokenRotated:
    business = await db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Biznes topilmadi")

    # Yangi hash yozilishi bilan eski token hashi yo‘qoladi — eski token darhol ishlamay qoladi.
    raw_token = generate_admin_token()
    business.admin_token_hash = hash_token(raw_token)
    await db.commit()
    return TokenRotated(id=business.id, slug=business.slug, admin_token=raw_token)
