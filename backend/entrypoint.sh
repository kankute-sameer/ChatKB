#!/bin/sh
set -eu

alembic upgrade head

# Keep exactly one process: resumable response streams are buffered in memory.
exec uvicorn app.main:create_app \
    --factory \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --root-path "${ROOT_PATH:-}" \
    --proxy-headers \
    --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
