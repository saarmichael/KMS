#!/bin/sh
set -e
# Migrations run before the API accepts traffic (design: "How schema changes are applied").
uv run --no-sync alembic upgrade head
exec uv run --no-sync uvicorn kms.main:app --host 0.0.0.0 --port "${PORT:-8000}"
