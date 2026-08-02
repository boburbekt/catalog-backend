#!/bin/sh
set -e

# The schema changes only here — there is no create_all inside the app.
echo "Applying migrations…"
alembic upgrade head

exec "$@"
