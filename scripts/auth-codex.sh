#!/usr/bin/env bash
# Codex CLI auth setup via `codex login`, persisted to the hsb-codex-auth
# named volume.
#
# Flow:
#   1. Seed /root/.codex/config.toml with forced_login_method="chatgpt"
#      IF absent. (Existing config.toml is preserved — operators may have
#      [mcp_servers.*] blocks they wrote by hand.)
#   2. Run `codex login` in a one-off container with the auth volume
#      mounted. The CLI prints an OAuth URL — operator approves in any
#      browser (the container has network_mode: host, so a localhost
#      callback works on the host machine).
#   3. Verify auth.json landed in the volume.
#
# Multi-org: persists to <HSB_PROJECT>_hsb-codex-auth (matches the rest
# of the project pattern). Override with HSB_PROJECT before invoking make.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"
cd "$SCRIPT_DIR/.."

CONTAINER_NAME="hsb-run-auth-codex-$$"

cleanup() {
  "$SCRIPT_DIR/kill-stale.sh" auth-codex >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

run_codex() {
  # Run codex in a one-off container with the auth volume mounted.
  # First arg controls TTY; remaining args are passed to codex.
  local mode="$1"; shift
  local tty_flag=""
  [[ "$mode" == "tty" ]] || tty_flag="-T"
  compose run --rm $tty_flag -e BROWSER=true \
    --name "$CONTAINER_NAME" hsb codex "$@"
}

seed_config_in_volume() {
  # Write config.toml inside the named volume IF MISSING. Uses a one-off
  # alpine container so we don't need the hsb image just for `test -f`.
  local vol="$1"
  docker run --rm -v "${vol}:/codex" alpine sh -c '
    if [ ! -f /codex/config.toml ]; then
      printf "%s\n%s\n" \
        "# Auto-seeded by scripts/auth-codex.sh." \
        "forced_login_method = \"chatgpt\"" \
        > /codex/config.toml
      echo "seeded"
    else
      echo "preserved"
    fi
  '
}

say ""
say "=== Codex CLI Auth Setup ==="
say ""

"$SCRIPT_DIR/kill-stale.sh" auth-codex
say ""

# Pre-check: is there a valid token already?
EXISTING_VOL=$(auth_volume hsb-codex-auth || true)
if [[ -n "$EXISTING_VOL" ]] && volume_has_file "$EXISTING_VOL" 'auth.json'; then
  info "Existing Codex auth found in volume '$EXISTING_VOL'."
  info "Skipping login — auth.json is already present."
  say ""
  say "  → Run 'make up' to start the service."
  say "  → To force a fresh auth: 'docker volume rm $EXISTING_VOL' then re-run."
  exit 0
fi

# Make sure the named volume exists by running an empty container against it.
# `compose run` lazily creates volumes declared in compose.yml, so the first
# call below will create hsb-codex-auth if it doesn't exist.
info "Ensuring hsb-codex-auth volume exists..."
compose run --rm -T --name "${CONTAINER_NAME}-init" hsb true >/dev/null

VOL=$(auth_volume hsb-codex-auth)
if [[ -z "$VOL" ]]; then
  fail "hsb-codex-auth volume did not materialize after compose run. Bailing."
  exit 1
fi

info "Seeding config.toml (if missing)..."
SEED_RESULT=$(seed_config_in_volume "$VOL")
case "$SEED_RESULT" in
  seeded)    ok "config.toml seeded with forced_login_method = \"chatgpt\"." ;;
  preserved) info "config.toml already exists — left untouched." ;;
  *)         warn "Unexpected seed result: $SEED_RESULT" ;;
esac
say ""

info "Starting interactive codex login..."
say ""
say "──────────────────────────────────────────────────────────────────────"
say "  codex will print an OAuth URL. Open it in any browser, sign in to"
say "  ChatGPT, and approve. The CLI will exit on success."
say ""
say "  • Local terminal  → the URL may auto-open; approve and wait."
say "  • Remote/headless → copy the URL into a browser on any device."
say "──────────────────────────────────────────────────────────────────────"
say ""

if run_codex tty login; then
  say ""
  ok "codex login completed."
else
  fail "codex login failed or was cancelled."
  exit 1
fi

# Final verification.
say ""
info "Verifying auth.json is present..."
if volume_has_file "$VOL" 'auth.json'; then
  ok "Codex authentication complete and persisted to volume '$VOL'."
  say ""
  say "  → Run 'make up' to start the service."
  say "  → HSB_RUNTIME_BACKLOG=codex selects Codex for the backlog agent."
else
  fail "auth.json missing from '$VOL' after login. Re-run 'make auth-codex'."
  exit 1
fi
