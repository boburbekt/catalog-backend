from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    PREORDER = "preorder"
    OUT_OF_STOCK = "out_of_stock"


class OrderStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class VisitSource(StrEnum):
    QR = "qr"
    LINK = "link"
    INSTAGRAM = "instagram"
    TELEGRAM = "telegram"
    DIRECT = "direct"


def normalize_source(raw: str | None) -> str:
    """Ruxsat etilgan manbalar ro‘yxatiga tushirish; notanish qiymat → `direct`."""
    if raw and raw.lower() in _ALLOWED_SOURCES:
        return raw.lower()
    return VisitSource.DIRECT.value


_ALLOWED_SOURCES = {member.value for member in VisitSource}


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(40))
    telegram_username: Mapped[str | None] = mapped_column(String(80))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    instagram: Mapped[str | None] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    admin_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    notify_telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)

    categories: Mapped[list["Category"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    visits: Mapped[list["CatalogVisit"]] = relationship(back_populates="business", cascade="all, delete-orphan")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("business_id", "slug", name="uq_category_business_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship(back_populates="categories")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "slug", name="uq_product_business_slug"),
        Index("ix_product_business_visible", "business_id", "is_visible"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    material: Mapped[str | None] = mapped_column(String(160))
    dimensions: Mapped[str | None] = mapped_column(String(160))
    color: Mapped[str | None] = mapped_column(String(60))
    sku: Mapped[str | None] = mapped_column(String(60))
    image_url: Mapped[str | None] = mapped_column(String(500))
    availability: Mapped[Availability] = mapped_column(
        SAEnum(
            Availability,
            name="availability",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=Availability.IN_STOCK,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship(back_populates="products")
    category: Mapped[Category | None] = relationship(back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.NEW.value, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default=VisitSource.DIRECT.value, nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    business: Mapped[Business] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    product_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class CatalogVisit(Base):
    __tablename__ = "catalog_visits"
    __table_args__ = (
        Index("ix_visit_business_created", "business_id", "created_at"),
        Index("ix_visit_business_source", "business_id", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(30), default=VisitSource.DIRECT.value, nullable=False)
    path: Mapped[str | None] = mapped_column(String(300))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    business: Mapped[Business] = relationship(back_populates="visits")
