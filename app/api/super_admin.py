from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_admin_token, require_superadmin
from app.db.session import get_db
from app.models import Business
from app.schemas.catalog import BusinessCreate, BusinessCreated

router = APIRouter(prefix="/super", tags=["super admin"], dependencies=[Depends(require_superadmin)])


@router.post("/businesses", response_model=BusinessCreated, status_code=status.HTTP_201_CREATED)
async def create_business(
    payload: BusinessCreate,
    db: AsyncSession = Depends(get_db),
) -> Business:
    existing = await db.scalar(select(Business).where(Business.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Bu slug allaqachon band")

    business = Business(**payload.model_dump(), admin_token=generate_admin_token())
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business
