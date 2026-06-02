#!/usr/bin/env bash
# Wait for the frontend to accept requests, then run the Playwright suite.
# Uses Node's global fetch (always present in the Playwright image) so we don't
# depend on wget/curl being available inside the nginx container.
set -euo pipefail

URL="${E2E_BASE_URL:-http://frontend:80}"
echo "e2e: waiting for frontend at $URL …"
for _ in $(seq 1 60); do
  if node -e "fetch('$URL/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"; then
    echo "e2e: frontend is ready"
    break
  fi
  sleep 1
done

npx playwright test
