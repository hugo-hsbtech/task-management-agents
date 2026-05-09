#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"$(dirname "$0")/kill-stale.sh"
docker compose up -d "$@"
