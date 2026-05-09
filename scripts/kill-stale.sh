#!/usr/bin/env bash
set -euo pipefail

# Target only `docker compose run` one-off containers, not the main service.
# Compose names them: <project>-hsb-run-<hash>
#
# Optional tag arg narrows the match so parallel invocations don't clobber
# each other:
#   kill-stale.sh            → matches every -hsb-run-* container
#   kill-stale.sh shell      → matches only -hsb-run-shell-* containers
#
# Callers that want isolation should launch with
#   docker compose run --name "hsb-run-<tag>-$$" ...
# and pass <tag> here.

TAG="${1:-}"
NAME_FILTER="hsb-run-${TAG}"

kill_stale() {
  local stale
  stale=$(docker ps -q \
    --filter "ancestor=hsb-agents:local" \
    --filter "name=${NAME_FILTER}" 2>/dev/null || true)

  if [[ -z "$stale" ]]; then
    echo "No stale hsb-agents run containers${TAG:+ (tag: $TAG)}."
    return 0
  fi

  echo "Removing stale containers${TAG:+ (tag: $TAG)}:"
  docker ps \
    --filter "ancestor=hsb-agents:local" \
    --filter "name=${NAME_FILTER}" \
    --format "  {{.ID}}  {{.Names}}  {{.Status}}"
  docker rm -f $stale >/dev/null
  echo "Done."
}

kill_stale
