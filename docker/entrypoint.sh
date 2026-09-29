#!/bin/sh
set -e
# Migrations run before the API accepts traffic, so no request ever meets an older schema.
uv run --no-sync alembic upgrade head
exec uv run --no-sync uvicorn kms.main:app --host 0.0.0.0 --port "${PORT:-8000}"
