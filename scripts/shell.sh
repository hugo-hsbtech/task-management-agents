#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
"$(dirname "$0")/kill-stale.sh" shell
docker compose run --name "hsb-run-shell-$$" --rm hsb /bin/bash
