from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import Availability, OrderStatus


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    position: int
    is_active: bool


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
    position: int
    is_visible: bool
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


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_name: str
    quantity: int
    unit_price: Decimal

    @computed_field  # type: ignore[prop-decorator]
    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    customer_phone: str
    comment: str | None
    status: OrderStatus
    source: str
    created_at: datetime
    notified_at: datetime | None
    items: list[OrderItemOut]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0"))


class OrderListOut(BaseModel):
    orders: list[OrderOut]
    total: int
    limit: int
    offset: int


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class AdminProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class AdminProductUpdate(BaseModel):
    """Mahsulotni qisman yangilash.

    Handler `payload.model_dump(exclude_unset=True)` bilan ishlaydi: yuborilmagan maydon
    tegilmaydi. Nullable maydonlar (`category_id`, `description`, `old_price`, `material`,
    `dimensions`, `color`, `sku`, `image_url`) explicit `null` bilan tozalanadi.
    `name`, `slug`, `price`, `availability`, `position`, `is_visible` turida `None` yo‘q —
    ularning standart `None` qiymati faqat "yuborilmagan"ni bildiradi, `null` yuborilsa 422 bo‘ladi.
    """

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = None
    name: str = Field(default=None, min_length=2, max_length=180)
    slug: str = Field(
        default=None, min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = None
    price: Decimal = Field(default=None, gt=0)
    old_price: Decimal | None = Field(default=None, gt=0)
    material: str | None = None
    dimensions: str | None = None
    color: str | None = Field(default=None, max_length=60)
    sku: str | None = Field(default=None, max_length=60)
    image_url: str | None = None
    availability: Availability = Field(default=None)
    position: int = Field(default=None, ge=0)
    is_visible: bool = Field(default=None)


_CATEGORY_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120, pattern=_CATEGORY_SLUG)
    position: int = Field(default=0, ge=0)
    is_active: bool = True


class CategoryUpdate(BaseModel):
    """Qisman yangilash. Yuborilgan maydonlar `null` bo‘la olmaydi (standart `None` = "yuborilmagan")."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default=None, min_length=1, max_length=120)
    slug: str = Field(default=None, min_length=1, max_length=120, pattern=_CATEGORY_SLUG)
    position: int = Field(default=None, ge=0)
    is_active: bool = Field(default=None)


class CategoryDeleteResult(BaseModel):
    id: int
    detached_products: int


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
