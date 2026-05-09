# Shared helpers for scripts/. Source this — do NOT execute.
#
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   . "$SCRIPT_DIR/_lib.sh"
#
# Intentionally does not call `set -euo pipefail` — that would mutate the
# sourcing shell. The caller is expected to set its own shell options.

# ── Logging ──────────────────────────────────────────────────────────────────
say()  { printf '%s\n' "$*"; }
ok()   { printf '\e[32m[ok]\e[0m   %s\n' "$*"; }
info() { printf '\e[36m[..]\e[0m   %s\n' "$*"; }
warn() { printf '\e[33m[!!]\e[0m   %s\n' "$*"; }
fail() { printf '\e[31m[xx]\e[0m   %s\n' "$*" >&2; }

# ── Compose project ──────────────────────────────────────────────────────────
#
# All Compose calls go through `compose` so the project name is consistent
# across scripts. Override per org by exporting HSB_PROJECT before invoking
# make, e.g.:
#
#     HSB_PROJECT=org-acme make auth-linear
#     HSB_PROJECT=org-acme make up
#
# The default matches Compose's own directory-name default, so existing
# single-project setups keep their existing volumes (no migration).
export HSB_PROJECT="${HSB_PROJECT:-task-management-agents}"

compose() {
  docker compose -p "$HSB_PROJECT" "$@"
}

# ── Docker named-volume helpers ──────────────────────────────────────────────

# Find a named volume by its suffix, scoped to the current project.
# Usage:   auth_volume hsb-mcp-auth → "<HSB_PROJECT>_hsb-mcp-auth"
auth_volume() {
  local suffix="$1"
  docker volume ls --format '{{.Name}}' \
    | grep "^${HSB_PROJECT}_${suffix}\$" | head -1
}

# Return 0 if the named volume contains a file matching the given glob.
# Usage:   volume_has_file <vol> '*tokens.json'
#          volume_has_file <vol> 'hosts.yml'
volume_has_file() {
  local vol="$1" pattern="$2"
  [[ -z "$vol" ]] && return 1
  docker run --rm -v "${vol}:/auth" alpine \
    find /auth -name "$pattern" 2>/dev/null | grep -q . 2>/dev/null
}
