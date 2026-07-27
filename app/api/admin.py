from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import get_current_business
from app.core.slugify import slugify, unique_slug
from app.db.session import get_db
from app.models import Availability, Business, CatalogVisit, Category, Order, OrderItem, OrderStatus, Product
from app.services.images import (
    ALLOWED_CONTENT_TYPES,
    InvalidImageError,
    build_webp,
    remove_local_image,
    save_webp,
)
from app.services.product_import import (
    MAX_IMPORT_BYTES,
    MAX_IMPORT_ROWS,
    XLSX_MAGIC,
    RowError,
    build_template_workbook,
    cell_str,
    is_blank,
    load_rows,
    parse_amount,
    parse_availability,
)
from app.schemas.catalog import (
    AdminMeOut,
    AdminMeUpdate,
    AdminProductCreate,
    AdminProductUpdate,
    CategoryCreate,
    CategoryDeleteResult,
    CategoryOut,
    CategoryUpdate,
    DayStat,
    ImportResult,
    ImportRowError,
    OrderListOut,
    OrderOut,
    OrderStatusUpdate,
    ProductOut,
    SourceCount,
    StatsOut,
    TopProduct,
)

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_DUPLICATE_SLUG = "Bu slug allaqachon mavjud"
_ORDER_HISTORY = "Bu mahsulotda buyurtma tarixi mavjud. Uni o‘chirish o‘rniga yashiring."

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=AdminMeOut)
async def get_me(
    business: Business = Depends(get_current_business),
) -> Business:
    """Token egasining biznes ma'lumotlari. Token/hash javobda chiqmaydi."""
    return business


@router.patch("/me", response_model=AdminMeOut)
async def update_me(
    payload: AdminMeUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Admin o‘z biznesining tahrirlashga ruxsat etilgan maydonlarini yangilaydi.

    `slug`, `is_active`, token/hash `AdminMeUpdate` da yo‘q — ularni yuborishga urinish
    422 bilan rad etiladi. Tenant faqat token orqali aniqlanadi.
    """
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(business, field, value)
    await db.commit()
    await db.refresh(business)
    return business


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> list[Product]:
    query = (
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.business_id == business.id)
        .order_by(Product.position, Product.id.desc())
    )
    return list((await db.scalars(query)).all())


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: AdminProductCreate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Product:
    duplicate = await db.scalar(
        select(Product).where(Product.business_id == business.id, Product.slug == payload.slug)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    if payload.category_id is not None:
        owned = await db.scalar(
            select(Category.id).where(
                Category.id == payload.category_id,
                Category.business_id == business.id,
            )
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    product = Product(
        business_id=business.id,
        category_id=payload.category_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price=payload.price,
        old_price=payload.old_price,
        material=payload.material,
        dimensions=payload.dimensions,
        color=payload.color,
        sku=payload.sku,
        image_url=payload.image_url,
        availability=payload.availability,
        position=payload.position,
    )
    db.add(product)
    await db.commit()
    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: AdminProductUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Product:
    # Tenant-scoped: mahsulot faqat token egasining do‘konidan izlanadi.
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business.id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    data = payload.model_dump(exclude_unset=True)

    # Slug o‘zgarsa, shu do‘kon ichida (o‘zidan boshqa) mahsulotda takrorlanmasin.
    if "slug" in data and data["slug"] != product.slug:
        duplicate = await db.scalar(
            select(Product.id).where(
                Product.business_id == business.id,
                Product.slug == data["slug"],
                Product.id != product.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    # category_id: null → biriktirishni olib tashlash; boshqa tenant kategoriyasi → 404.
    if data.get("category_id") is not None:
        owned = await db.scalar(
            select(Category.id).where(
                Category.id == data["category_id"],
                Category.business_id == business.id,
            )
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    for field, value in data.items():
        setattr(product, field, value)

    try:
        await db.commit()
    except IntegrityError:
        # Ikki so‘rov bir vaqtda bir xil slugni band qilib qolsa — DB unique cheklovi ushlaydi.
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Response:
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business.id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # Buyurtma tarixi bo‘lsa o‘chirmaymiz — mijoz buyurtmalari yo‘qolmasligi kerak.
    has_orders = await db.scalar(
        select(OrderItem.id).where(OrderItem.product_id == product.id).limit(1)
    )
    if has_orders:
        raise HTTPException(status_code=409, detail=_ORDER_HISTORY)

    await db.delete(product)
    try:
        await db.commit()
    except IntegrityError:
        # Race condition: tekshiruvdan keyin buyurtma qo‘shilsa, FK RESTRICT ushlaydi.
        await db.rollback()
        raise HTTPException(status_code=409, detail=_ORDER_HISTORY)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/products/{product_id}/image", response_model=ProductOut)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Product:
    product = await db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business.id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # content-type — birlamchi filtr, lekin unga yolg‘iz ishonmaymiz (haqiqiy tekshiruv Pillow'da).
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Faqat JPEG, PNG yoki WebP qabul qilinadi")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    # Faqat `max_bytes + 1` o‘qiymiz: chegaradan oshsa xotirani to‘ldirmasdan darrov rad etamiz.
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"Rasm hajmi {settings.max_upload_mb} MB dan oshmasligi kerak"
        )

    try:
        webp_bytes = build_webp(data)  # haqiqiy rasm ekanini tekshiradi + WebP'ga o‘tkazadi
    except InvalidImageError:
        raise HTTPException(status_code=400, detail="Yaroqli rasm fayli emas")

    old_url = product.image_url
    path, new_url = save_webp(webp_bytes, settings.upload_dir, business.id)

    product.image_url = new_url
    try:
        await db.commit()
    except SQLAlchemyError:
        # DB xatosida yangi saqlangan fayl yetim qolmasligi uchun o‘chiriladi.
        await db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Rasmni saqlab bo‘lmadi")

    # Commit muvaffaqiyatli — eski lokal rasm endi almashtirildi, xavfsiz o‘chiramiz.
    remove_local_image(old_url, settings.upload_dir)

    query = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    return await db.scalar(query)  # type: ignore[return-value]


@router.get("/products/import/template")
async def download_import_template(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Import uchun tayyor .xlsx shablonni qaytaradi.

    Kategoriya ustuniga shu do‘konning faol kategoriyalaridan dropdown qo‘yiladi (bo‘lsa).
    """
    category_names = list(
        (
            await db.scalars(
                select(Category.name)
                .where(Category.business_id == business.id, Category.is_active.is_(True))
                .order_by(Category.position, Category.id)
            )
        ).all()
    )
    content = build_template_workbook(category_names)
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="mahsulotlar-shablon.xlsx"'},
    )


@router.post("/products/import", response_model=ImportResult)
async def import_products(
    file: UploadFile = File(...),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    """Excel (.xlsx) faylidan mahsulotlarni ommaviy import qiladi.

    Har bir qator alohida validatsiya qilinadi: bitta xato qator qolganini to‘xtatmaydi
    (partial success). Faqat valid qatorlar bitta tranzaksiyada saqlanadi; xato qatorlar
    hisobotga tushadi. Yozish faqat token orqali aniqlangan `business_id` ga — hech qachon
    fayldan olingan id'ga emas.
    """
    # Hajmni faqat `max + 1` gacha o‘qiymiz — chegaradan oshsa xotirani to‘ldirmasdan rad etamiz.
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413, detail="Fayl hajmi 5 MB dan oshmasligi kerak"
        )
    # Magic bytes: xlsx = ZIP (PK\x03\x04). content-type'ga yolg‘iz ishonmaymiz.
    if not data.startswith(XLSX_MAGIC):
        raise HTTPException(
            status_code=422, detail="Fayl .xlsx (Excel) formatida bo‘lishi kerak"
        )
    try:
        rows = load_rows(data)
    except Exception:
        raise HTTPException(status_code=422, detail="Excel faylni o‘qib bo‘lmadi")
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=422,
            detail=f"Faylda {MAX_IMPORT_ROWS} tadan ortiq mahsulot bo‘lmasligi kerak",
        )

    # Shu biznes ichidagi mavjud slug'lar va kategoriyalarni oldindan yuklaymiz (cross-tenant emas).
    product_slugs = set(
        (await db.scalars(select(Product.slug).where(Product.business_id == business.id))).all()
    )
    category_slugs = set(
        (await db.scalars(select(Category.slug).where(Category.business_id == business.id))).all()
    )
    categories = {
        category.name.strip().lower(): category
        for category in (
            await db.scalars(select(Category).where(Category.business_id == business.id))
        ).all()
    }
    max_position = await db.scalar(
        select(func.max(Product.position)).where(Product.business_id == business.id)
    )
    next_position = (max_position or 0) + 1

    created = 0
    errors: list[ImportRowError] = []

    for excel_row, cells in rows:
        try:
            name = cell_str(cells[0])
            if not name:
                raise RowError("Nomi majburiy")

            # Narx/eski narxni kategoriya yaratishdan OLDIN tekshiramiz — xato qatorda
            # yetim kategoriya paydo bo‘lmasligi uchun.
            if is_blank(cells[2]):
                raise RowError("Narx majburiy")
            try:
                price = parse_amount(cells[2])
            except ValueError:
                raise RowError("Narx noto‘g‘ri formatda")
            if price is None or price <= 0:
                raise RowError("Narx 0 dan katta bo‘lishi kerak")

            old_price = None
            if not is_blank(cells[3]):
                try:
                    old_price = parse_amount(cells[3])
                except ValueError:
                    raise RowError("Eski narx noto‘g‘ri formatda")
                if old_price is not None and old_price <= price:
                    raise RowError("Eski narx joriy narxdan katta bo‘lishi kerak")

            availability: Availability = parse_availability(cells[9])

            # Kategoriya: shu biznes ichida case-insensitive qidiriladi; topilmasa yaratiladi.
            category_id = None
            category_name = cell_str(cells[1])
            if category_name:
                key = category_name.lower()
                category = categories.get(key)
                if category is None:
                    category = Category(
                        business_id=business.id,
                        name=category_name,
                        slug=unique_slug(slugify(category_name), category_slugs),
                        is_active=True,
                    )
                    category_slugs.add(category.slug)
                    db.add(category)
                    await db.flush()  # id kerak — mahsulotga biriktirish uchun
                    categories[key] = category
                category_id = category.id

            slug = unique_slug(slugify(name), product_slugs)
            product_slugs.add(slug)

            db.add(
                Product(
                    business_id=business.id,
                    category_id=category_id,
                    name=name,
                    slug=slug,
                    description=cell_str(cells[4]) or None,
                    price=price,
                    old_price=old_price,
                    material=cell_str(cells[5]) or None,
                    dimensions=cell_str(cells[6]) or None,
                    color=cell_str(cells[7]) or None,
                    sku=cell_str(cells[8]) or None,
                    availability=availability,
                    position=next_position,
                )
            )
            next_position += 1
            created += 1
        except RowError as exc:
            errors.append(ImportRowError(row=excel_row, message=f"{excel_row}-qator: {exc}"))

    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Importni saqlab bo‘lmadi")

    return ImportResult(created=created, skipped=len(errors), errors=errors)


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> list[Category]:
    # Admin uchun active va inactive — hammasi position bo‘yicha.
    query = (
        select(Category)
        .where(Category.business_id == business.id)
        .order_by(Category.position, Category.id)
    )
    return list((await db.scalars(query)).all())


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Category:
    duplicate = await db.scalar(
        select(Category.id).where(
            Category.business_id == business.id, Category.slug == payload.slug
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    category = Category(
        business_id=business.id,
        name=payload.name,
        slug=payload.slug,
        position=payload.position,
        is_active=payload.is_active,
    )
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)
    await db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Category:
    category = await db.scalar(
        select(Category).where(
            Category.id == category_id, Category.business_id == business.id
        )
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != category.slug:
        duplicate = await db.scalar(
            select(Category.id).where(
                Category.business_id == business.id,
                Category.slug == data["slug"],
                Category.id != category.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)

    for field, value in data.items():
        setattr(category, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_DUPLICATE_SLUG)
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}", response_model=CategoryDeleteResult)
async def delete_category(
    category_id: int,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> CategoryDeleteResult:
    category = await db.scalar(
        select(Category).where(
            Category.id == category_id, Category.business_id == business.id
        )
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Kategoriya topilmadi")

    # Mahsulotlarni explicit ravishda kategoriyasiz qoldiramiz (FK SET NULL'ga tayanmasdan),
    # shu bilan nechta mahsulot ajratilganini ham sanaymiz.
    result = await db.execute(
        Product.__table__.update()
        .where(Product.category_id == category.id, Product.business_id == business.id)
        .values(category_id=None)
    )
    detached = result.rowcount or 0

    await db.delete(category)
    await db.commit()
    return CategoryDeleteResult(id=category_id, detached_products=detached)


@router.get("/orders", response_model=OrderListOut)
async def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> OrderListOut:
    since = datetime.now(UTC) - timedelta(days=days)
    filters = [Order.business_id == business.id, Order.created_at >= since]
    if status_filter is not None:
        filters.append(Order.status == status_filter)

    total = await db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    # selectinload — buyurtmalar itemlarini bitta qo‘shimcha so‘rovda oldindan yuklaydi (N+1 yo‘q).
    orders = list(
        (
            await db.scalars(
                select(Order)
                .options(selectinload(Order.items))
                .where(*filters)
                .order_by(Order.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return OrderListOut(orders=orders, total=total, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.business_id == business.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return order


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> Order:
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.business_id == business.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    order.status = payload.status
    await db.commit()
    # `expire_on_commit=False` — itemlar yuklangicha qoladi, qayta so‘rov shart emas.
    return order


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    # Kalendar kunlariga tayanamiz: oxirgi `days` kun (bugun ham kiradi) yarim tunidan boshlab.
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    since = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)

    source_rows = (
        await db.execute(
            select(CatalogVisit.source, func.count())
            .where(CatalogVisit.business_id == business.id, CatalogVisit.created_at >= since)
            .group_by(CatalogVisit.source)
            .order_by(func.count().desc())
        )
    ).all()

    total_orders = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.business_id == business.id, Order.created_at >= since)
    )

    new_orders = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.business_id == business.id,
            Order.created_at >= since,
            Order.status == OrderStatus.NEW,
        )
    )

    total_products = await db.scalar(
        select(func.count()).select_from(Product).where(Product.business_id == business.id)
    )

    top_rows = (
        await db.execute(
            select(Product.id, Product.name, Product.slug, func.count(CatalogVisit.id).label("visits"))
            .join(CatalogVisit, CatalogVisit.product_id == Product.id)
            .where(CatalogVisit.business_id == business.id, CatalogVisit.created_at >= since)
            .group_by(Product.id, Product.name, Product.slug)
            .order_by(func.count(CatalogVisit.id).desc())
            .limit(10)
        )
    ).all()

    # by_day: har bir kun uchun tashrif va buyurtma sonini Python'da guruhlaymiz (DB-agnostik).
    # Bo‘sh kunlar 0 bilan to‘ldiriladi.
    visit_dates = (
        await db.scalars(
            select(CatalogVisit.created_at).where(
                CatalogVisit.business_id == business.id, CatalogVisit.created_at >= since
            )
        )
    ).all()
    order_dates = (
        await db.scalars(
            select(Order.created_at).where(
                Order.business_id == business.id, Order.created_at >= since
            )
        )
    ).all()

    visits_by_date: dict = {}
    for created in visit_dates:
        key = created.date()
        visits_by_date[key] = visits_by_date.get(key, 0) + 1
    orders_by_date: dict = {}
    for created in order_dates:
        key = created.date()
        orders_by_date[key] = orders_by_date.get(key, 0) + 1

    by_day = [
        DayStat(
            date=(day := start_date + timedelta(days=offset)).isoformat(),
            visits=visits_by_date.get(day, 0),
            orders=orders_by_date.get(day, 0),
        )
        for offset in range(days)
    ]

    by_source = [SourceCount(source=source, visits=count) for source, count in source_rows]
    return StatsOut(
        days=days,
        total_visits=sum(item.visits for item in by_source),
        total_orders=total_orders or 0,
        total_products=total_products or 0,
        new_orders=new_orders or 0,
        by_source=by_source,
        by_day=by_day,
        top_products=[
            TopProduct(id=row.id, name=row.name, slug=row.slug, visits=row.visits) for row in top_rows
        ],
    )
