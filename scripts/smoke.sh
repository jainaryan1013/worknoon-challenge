#!/usr/bin/env bash
# Compose smoke test: bring the production stack up and assert it's healthy.
# Verifies the single-command path (docs/components/07-infra.md §8) without a
# browser. Run: make smoke
set -euo pipefail

cd "$(dirname "$0")/.."

# The production stack reads .env. For an unattended smoke we don't need a real
# key, so write a temporary keyless one (fake provider) if none exists.
ENV_CREATED=""
if [ ! -f .env ]; then
  echo "smoke: no .env found — writing a temporary keyless one (LLM_PROVIDER=fake)…"
  cat > .env <<'EOF'
LLM_PROVIDER=fake
SEED_ENABLED=true
FRONTEND_ORIGIN=http://localhost:8080
POSTGRES_USER=refund
POSTGRES_PASSWORD=refund
POSTGRES_DB=refund
EOF
  ENV_CREATED=1
fi

cleanup() {
  docker-compose down -v >/dev/null 2>&1 || true
  [ -n "$ENV_CREATED" ] && rm -f .env
}
trap cleanup EXIT

echo "smoke: building + starting stack…"
docker-compose up -d --build

ok=""
for _ in $(seq 1 45); do
  if curl -fsS http://localhost:8000/api/health 2>/dev/null | grep -q '"db": *"ok"'; then
    ok=1
    break
  fi
  sleep 2
done

if [ -z "$ok" ]; then
  echo "smoke: FAIL — backend did not become healthy"
  docker-compose logs --tail=50 backend || true
  exit 1
fi
echo "smoke: backend /api/health is ok"

if curl -fsS http://localhost:8080/ 2>/dev/null | grep -qi 'id="root"'; then
  echo "smoke: frontend served by nginx"
else
  echo "smoke: FAIL — frontend not served"
  exit 1
fi

echo "smoke: OK"
