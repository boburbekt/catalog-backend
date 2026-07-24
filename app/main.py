from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_router, catalog_router, qr_router, super_router
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, engine
from app.services.seed import seed_demo

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Sxema faqat Alembic orqali o‘zgaradi (`alembic upgrade head`) — bu yerda create_all yo‘q.
    if settings.environment == "dev":
        async with AsyncSessionLocal() as session:
            await seed_demo(session)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(qr_router, prefix="/api")
app.include_router(super_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
