from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Business, Category, Product

# Testlar xotiradagi SQLite'da ishlaydi: tashqi bog‘liqlik yo‘q, har bir test toza sxemadan boshlanadi.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest.fixture
async def shops(db):
    """Ikkita mustaqil do‘kon: ko‘p ijarachilik testlarining asosi.

    `alfa` da bitta ko‘rinadigan va bitta yashirin mahsulot, `beta` da bitta mahsulot bor.
    """
    # Bazada faqat hash saqlanadi; testlar xom "alfa-token"/"beta-token" ni header sifatida yuboradi.
    alfa = Business(name="Alfa Mebel", slug="alfa-mebel", admin_token_hash=hash_token("alfa-token"))
    beta = Business(name="Beta Mebel", slug="beta-mebel", admin_token_hash=hash_token("beta-token"))
    db.add_all([alfa, beta])
    await db.flush()

    alfa_category = Category(business_id=alfa.id, name="Divanlar", slug="divanlar")
    beta_category = Category(business_id=beta.id, name="Stollar", slug="stollar")
    db.add_all([alfa_category, beta_category])
    await db.flush()

    db.add_all(
        [
            Product(
                business_id=alfa.id,
                category_id=alfa_category.id,
                name="Alfa divan",
                slug="alfa-divan",
                price=Decimal("1000000"),
            ),
            Product(
                business_id=alfa.id,
                category_id=alfa_category.id,
                name="Yashirin divan",
                slug="yashirin-divan",
                price=Decimal("2000000"),
                is_visible=False,
            ),
            Product(
                business_id=beta.id,
                category_id=beta_category.id,
                name="Beta stol",
                slug="beta-stol",
                price=Decimal("3000000"),
            ),
        ]
    )
    await db.commit()
    return {"alfa": alfa, "beta": beta}
