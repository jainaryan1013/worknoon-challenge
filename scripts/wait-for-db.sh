#!/usr/bin/env sh
# Optional startup helper — compose healthchecks already gate this. See docs/components/07-infra.md §3.
set -e
echo "wait-for-db: rely on compose 'depends_on: service_healthy'."
