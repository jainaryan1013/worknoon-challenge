#!/usr/bin/env sh
# Backend startup lifecycle — see docs/components/07-infra.md §3.
# 1) wait for db  2) alembic upgrade head  3) conditional idempotent seed  4) uvicorn
set -e
echo "[entrypoint] running migrations..."
alembic upgrade head
if [ "${SEED_ENABLED:-true}" = "true" ]; then
  echo "[entrypoint] seeding (idempotent)..."
  python -m app.seed.seed
fi
echo "[entrypoint] starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
