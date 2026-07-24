from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import Availability


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    price: Decimal
    old_price: Decimal | None
    material: str | None
    dimensions: str | None
    color: str | None = None
    sku: str | None = None
    image_url: str | None
    availability: Availability
    category: CategoryOut | None = None


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_url: str | None
    phone: str | None
    telegram_username: str | None
    whatsapp: str | None = None
    instagram: str | None = None
    address: str | None
    description: str | None
    categories: list[CategoryOut]


class CatalogOut(BaseModel):
    business: BusinessOut
    products: list[ProductOut]
    total: int
    limit: int
    offset: int


class OrderCreate(BaseModel):
    product_id: int
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=7, max_length=40)
    quantity: int = Field(default=1, ge=1, le=99)
    comment: str | None = Field(default=None, max_length=1000)


class OrderCreated(BaseModel):
    id: int
    status: str
    message: str


class AdminProductCreate(BaseModel):
    category_id: int | None = None
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=2, max_length=180)
    description: str | None = None
    price: Decimal = Field(gt=0)
    old_price: Decimal | None = Field(default=None, gt=0)
    material: str | None = None
    dimensions: str | None = None
    color: str | None = Field(default=None, max_length=60)
    sku: str | None = Field(default=None, max_length=60)
    image_url: str | None = None
    availability: Availability = Availability.IN_STOCK
    position: int = 0


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    phone: str | None = Field(default=None, max_length=40)
    telegram_username: str | None = Field(default=None, max_length=80)
    whatsapp: str | None = Field(default=None, max_length=40)
    instagram: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=300)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    notify_telegram_chat_id: int | None = None


class BusinessCreated(BaseModel):
    """`admin_token` faqat shu javobda bir marta ko‘rsatiladi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    admin_token: str


class SourceCount(BaseModel):
    source: str
    visits: int


class TopProduct(BaseModel):
    id: int
    name: str
    slug: str
    visits: int


class StatsOut(BaseModel):
    days: int
    total_visits: int
    total_orders: int
    by_source: list[SourceCount]
    top_products: list[TopProduct]
