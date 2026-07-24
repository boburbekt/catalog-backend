#!/bin/sh
set -e

# Sxema faqat shu yerda o‘zgaradi — ilova ichida create_all yo‘q.
echo "Migratsiyalar qo‘llanmoqda…"
alembic upgrade head

exec "$@"
