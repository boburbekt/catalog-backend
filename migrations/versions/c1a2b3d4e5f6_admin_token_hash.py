"""admin_token -> admin_token_hash (SHA-256)

Revision ID: c1a2b3d4e5f6
Revises: 963426a4bda0
Create Date: 2026-07-24 09:00:00.000000

Xom `admin_token` ustuni `admin_token_hash` ga aylantiriladi va mavjud plaintext
tokenlar joyida SHA-256 hex hashiga o‘tkaziladi. Login kelgan xom tokenni hash qilib
solishtirgani uchun foydalanuvchidagi eski xom token migratsiyadan keyin ham ishlaydi.
"""
import hashlib
from string import hexdigits
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "963426a4bda0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HEX = set(hexdigits)


def _looks_hashed(value: str) -> bool:
    """SHA-256 hex hashi — aynan 64 ta hex belgi. Idempotentlik uchun ikki marta hashlamaymiz."""
    return len(value) == 64 and all(ch in _HEX for ch in value)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.drop_index(op.f("ix_businesses_admin_token"), table_name="businesses")
    op.alter_column(
        "businesses",
        "admin_token",
        new_column_name="admin_token_hash",
        existing_type=sa.String(length=64),
        existing_nullable=True,
    )

    # Data migration: joyida turgan plaintext tokenlarni hashga o‘tkazamiz.
    businesses = sa.table(
        "businesses",
        sa.column("id", sa.Integer),
        sa.column("admin_token_hash", sa.String),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(businesses.c.id, businesses.c.admin_token_hash)
    ).fetchall()
    for row_id, value in rows:
        if value and not _looks_hashed(value):
            conn.execute(
                businesses.update()
                .where(businesses.c.id == row_id)
                .values(admin_token_hash=_sha256(value))
            )

    op.create_index(
        op.f("ix_businesses_admin_token_hash"),
        "businesses",
        ["admin_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    # Hash bir tomonlama — downgrade faqat ustun/indeks strukturasini tiklaydi,
    # plaintext tokenlarni qaytarib bo‘lmaydi (saqlangan qiymat hash bo‘lib qoladi).
    op.drop_index(op.f("ix_businesses_admin_token_hash"), table_name="businesses")
    op.alter_column(
        "businesses",
        "admin_token_hash",
        new_column_name="admin_token",
        existing_type=sa.String(length=64),
        existing_nullable=True,
    )
    op.create_index(
        op.f("ix_businesses_admin_token"),
        "businesses",
        ["admin_token"],
        unique=True,
    )
