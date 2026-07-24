import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Business


def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)


async def get_current_business(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Admin tokenidan tenantni aniqlaydi. Tenant hech qachon so‘rov tanasidan olinmaydi."""
    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Admin-Token headeri talab qilinadi",
        )

    business = await db.scalar(
        select(Business).where(
            Business.admin_token == x_admin_token,
            Business.is_active.is_(True),
        )
    )
    if not business:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token yaroqsiz")
    return business


async def require_superadmin(
    x_super_token: str | None = Header(default=None, alias="X-Super-Token"),
) -> None:
    expected = get_settings().super_admin_token
    # Sozlanmagan bo‘lsa hech kimni kiritmaymiz — bo‘sh token hamma uchun ochiq qoldirmasin.
    if not expected or not x_super_token or not secrets.compare_digest(x_super_token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ruxsat yo‘q")
