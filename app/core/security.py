import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Business


def generate_admin_token() -> str:
    """Foydalanuvchiga bir marta ko‘rsatiladigan xom token (URL-safe, ~43 belgi)."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """Xom tokenni SHA-256 hex hashiga aylantiradi (64 belgi). Bir tomonlama."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_current_business(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Admin tokenidan tenantni aniqlaydi. Tenant hech qachon so‘rov tanasidan olinmaydi.

    Kelgan xom token hash qilinib, DB dagi `admin_token_hash` bilan solishtiriladi —
    xom token bazada saqlanmaydi.
    """
    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Admin-Token headeri talab qilinadi",
        )

    business = await db.scalar(
        select(Business).where(
            Business.admin_token_hash == hash_token(x_admin_token),
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
