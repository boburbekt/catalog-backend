from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Category, Product


async def seed_demo(session: AsyncSession) -> None:
    existing = await session.scalar(select(Business).where(Business.slug == "demo-mebel"))
    if existing:
        return

    business = Business(
        name="Demo Mebel",
        slug="demo-mebel",
        phone="+998 90 123 45 67",
        telegram_username="demo_mebel",
        address="Farg‘ona shahri",
        description="Zamonaviy mebel katalogi: divanlar, stollar va shkaflar.",
        logo_url="https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=240&q=80",
    )
    session.add(business)
    await session.flush()

    categories = [
        Category(business_id=business.id, name="Divanlar", slug="divanlar", position=1),
        Category(business_id=business.id, name="Stollar", slug="stollar", position=2),
        Category(business_id=business.id, name="Shkaflar", slug="shkaflar", position=3),
    ]
    session.add_all(categories)
    await session.flush()

    products = [
        Product(
            business_id=business.id,
            category_id=categories[0].id,
            name="Milan divan",
            slug="milan-divan",
            description="Yumshoq matoli, zamonaviy uch kishilik divan.",
            price=Decimal("4850000"),
            old_price=Decimal("5200000"),
            material="Velur mato",
            dimensions="230 × 95 × 85 sm",
            image_url="https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=1200&q=85",
        ),
        Product(
            business_id=business.id,
            category_id=categories[0].id,
            name="Oslo burchak divan",
            slug="oslo-burchak-divan",
            description="Keng mehmonxona uchun burchakli divan.",
            price=Decimal("7250000"),
            material="Mikrovelur",
            dimensions="285 × 185 × 90 sm",
            image_url="https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=85",
        ),
        Product(
            business_id=business.id,
            category_id=categories[1].id,
            name="Nordik stol",
            slug="nordik-stol",
            description="6 kishilik yog‘och ovqatlanish stoli.",
            price=Decimal("2100000"),
            material="Massiv yog‘och",
            dimensions="180 × 90 × 76 sm",
            image_url="https://images.unsplash.com/photo-1530018607912-eff2daa1bac4?auto=format&fit=crop&w=1200&q=85",
        ),
        Product(
            business_id=business.id,
            category_id=categories[2].id,
            name="Linea shkaf",
            slug="linea-shkaf",
            description="Surilma eshikli, katta sig‘imli shkaf.",
            price=Decimal("5900000"),
            material="Laminat MDF",
            dimensions="240 × 65 × 220 sm",
            image_url="https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=85",
        ),
    ]
    session.add_all(products)
    await session.commit()
