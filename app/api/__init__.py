from app.api.admin import router as admin_router
from app.api.catalog import router as catalog_router
from app.api.qr import router as qr_router
from app.api.super_admin import router as super_router

__all__ = ["admin_router", "catalog_router", "qr_router", "super_router"]
