#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"
cd "$SCRIPT_DIR/.."
"$SCRIPT_DIR/kill-stale.sh" shell
compose run --name "hsb-run-shell-$$" --rm hsb /bin/bash
