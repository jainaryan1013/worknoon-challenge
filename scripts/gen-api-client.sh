#!/usr/bin/env sh
# Regenerate the frontend API client from the backend OpenAPI. See docs/repo-structure.md §5.
# Backend must be running on :8000.
set -e
cd "$(dirname "$0")/../apps/frontend"
npm run gen-client
