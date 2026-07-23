from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    image_url: str | None
    availability: str
    category: CategoryOut | None = None


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    logo_url: str | None
    phone: str | None
    telegram_username: str | None
    address: str | None
    description: str | None
    categories: list[CategoryOut]


class CatalogOut(BaseModel):
    business: BusinessOut
    products: list[ProductOut]


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
    business_slug: str
    category_id: int | None = None
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=2, max_length=180)
    description: str | None = None
    price: Decimal = Field(gt=0)
    old_price: Decimal | None = Field(default=None, gt=0)
    material: str | None = None
    dimensions: str | None = None
    image_url: str | None = None
    availability: str = "in_stock"
