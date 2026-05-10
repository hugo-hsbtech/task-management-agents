#!/usr/bin/env bash
# Gemini OAuth setup via gcloud application-default login.
# Persists to the hsb-gcloud-auth named volume.
#
# Multi-org: tokens are persisted to <HSB_PROJECT>_hsb-gcloud-auth.
# Set HSB_PROJECT before invoking make:
#   HSB_PROJECT=org-acme make auth-gemini

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"
cd "$SCRIPT_DIR/.."

CONTAINER_NAME="hsb-run-auth-gemini-$$"

cleanup() {
  "$SCRIPT_DIR/kill-stale.sh" auth-gemini >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

run_gcloud() {
  # Run gcloud in a one-off container with the auth volume mounted.
  local mode="$1"; shift
  local tty_flag=""
  [[ "$mode" == "tty" ]] || tty_flag="-T"
  compose run --rm $tty_flag \
    --name "$CONTAINER_NAME" hsb gcloud "$@"
}

say ""
say "=== Gemini OAuth Setup (Vertex AI) ==="
say ""

"$SCRIPT_DIR/kill-stale.sh" auth-gemini
say ""

# Pre-check: is there a valid token already?
EXISTING_VOL=$(auth_volume hsb-gcloud-auth || true)
if [[ -n "$EXISTING_VOL" ]] && volume_has_file "$EXISTING_VOL" 'application_default_credentials.json'; then
  info "Existing Gemini auth found in volume '$EXISTING_VOL'."
  ok "Gemini auth already configured."
  say ""
  say "  → Run 'make up' to start the service."
  say "  → To force a fresh auth: 'make clean' then 'make auth-gemini'."
  exit 0
fi

info "Starting Google Cloud Application Default Credentials (ADC) flow."
say ""
say "──────────────────────────────────────────────────────────────────────"
say "  gcloud will print a URL for you to authorize access in a browser."
say ""
say "  • Local terminal  → gcloud may attempt to open the browser automatically."
say "  • Remote/headless → copy the URL into a browser on any device, approve,"
say "    and gcloud will receive the token."
say "──────────────────────────────────────────────────────────────────────"
say ""

# We use --no-browser to ensure it works consistently in all environments
# and gives the user a URL they can copy-paste if needed.
if run_gcloud tty auth application-default login --no-browser; then
  say ""
  ok "ADC flow complete."
else
  fail "gcloud auth application-default login failed or was cancelled."
  exit 1
fi

# Final verification.
say ""
info "Verifying final auth state..."
if EXISTING_VOL=$(auth_volume hsb-gcloud-auth || true) && [[ -n "$EXISTING_VOL" ]] && volume_has_file "$EXISTING_VOL" 'application_default_credentials.json'; then
  ok "Gemini authentication complete and persisted to volume '$EXISTING_VOL'."
  say ""
  say "  → Run 'make up' to start the service."
else
  fail "Auth verification failed: application_default_credentials.json missing."
  exit 1
fi
