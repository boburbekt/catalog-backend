# Database schema — MVP

```mermaid
erDiagram
    BUSINESS ||--o{ CATEGORY : has
    BUSINESS ||--o{ PRODUCT : owns
    BUSINESS ||--o{ ORDER : receives
    CATEGORY ||--o{ PRODUCT : groups
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : selected

    BUSINESS {
      int id PK
      string name
      string slug UK
      string logo_url
      string phone
      string telegram_username
      string address
      bool is_active
    }

    CATEGORY {
      int id PK
      int business_id FK
      string name
      string slug
      int position
      bool is_active
    }

    PRODUCT {
      int id PK
      int business_id FK
      int category_id FK
      string name
      string slug
      decimal price
      decimal old_price
      string material
      string dimensions
      string image_url
      string availability
      bool is_visible
    }

    ORDER {
      int id PK
      int business_id FK
      string customer_name
      string customer_phone
      string comment
      string status
    }

    ORDER_ITEM {
      int id PK
      int order_id FK
      int product_id FK
      int quantity
      decimal unit_price
    }
```

## Multi-tenant cheklovlar

- `businesses.slug` global unique.
- `categories`: `UNIQUE(business_id, slug)`.
- `products`: `UNIQUE(business_id, slug)`.
- Public va admin so‘rovlari doimo `business_id` yoki biznes `slug` orqali cheklanadi.
- Keyingi bosqichda admin foydalanuvchi tokenidagi `business_id` bilan barcha CRUD so‘rovlari tekshiriladi.
