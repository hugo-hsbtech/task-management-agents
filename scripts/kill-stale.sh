#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"

# Target only `docker compose run` one-off containers, not the main service.
# Compose names them: <project>-hsb-run-<hash>. Scripts that override with
# --name still get the project label automatically (com.docker.compose.project).
#
# Optional tag arg narrows the match so parallel invocations don't clobber
# each other:
#   kill-stale.sh            → matches every -hsb-run-* container
#   kill-stale.sh shell      → matches only -hsb-run-shell-* containers
#
# Callers that want isolation should launch with
#   compose run --name "hsb-run-<tag>-$$" ...
# and pass <tag> here.
#
# All filters are scoped to the current HSB_PROJECT so containers from
# another org's project name are left alone.

TAG="${1:-}"
NAME_FILTER="hsb-run-${TAG}"
PROJECT_LABEL="com.docker.compose.project=${HSB_PROJECT}"

kill_stale() {
  local stale
  stale=$(docker ps -q \
    --filter "ancestor=hsb-agents:local" \
    --filter "label=${PROJECT_LABEL}" \
    --filter "name=${NAME_FILTER}" 2>/dev/null || true)

  if [[ -z "$stale" ]]; then
    echo "No stale hsb-agents run containers${TAG:+ (tag: $TAG)} in project '${HSB_PROJECT}'."
    return 0
  fi

  echo "Removing stale containers${TAG:+ (tag: $TAG)} in project '${HSB_PROJECT}':"
  docker ps \
    --filter "ancestor=hsb-agents:local" \
    --filter "label=${PROJECT_LABEL}" \
    --filter "name=${NAME_FILTER}" \
    --format "  {{.ID}}  {{.Names}}  {{.Status}}"
  docker rm -f $stale >/dev/null
  echo "Done."
}

kill_stale
