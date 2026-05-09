#!/usr/bin/env bash
# GitHub CLI auth setup, persisted to the hsb-gh-auth named volume.
#
# Two modes:
#   1. PAT mode    — if GITHUB_TOKEN is set in .env, pipes it to
#                    `gh auth login --with-token` (non-interactive).
#   2. Device mode — `gh auth login --web` prints a one-time code; user
#                    opens github.com/login/device, enters code, approves.
#
# Token lands at /root/.config/gh/hosts.yml inside the named volume.
# git's credential.helper is wired up by docker-entrypoint.sh on each
# container start (gh auth setup-git is not persistable on its own).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"
cd "$SCRIPT_DIR/.."

CONTAINER_NAME="hsb-run-auth-github-$$"

cleanup() {
  "$(dirname "$0")/kill-stale.sh" auth-github >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

token_from_env() {
  [[ -f .env ]] || return 0
  grep -E '^GITHUB_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}

run_gh() {
  # Run gh in a one-off container with the auth volume mounted.
  # First arg controls TTY; remaining args are passed to gh.
  #
  # BROWSER=true neutralises gh's auto-open attempt. Without this, on headless
  # hosts (VPS, slim containers) gh tries xdg-open / x-www-browser / wslview,
  # all of which are missing → harmless but noisy warning. Auth still works
  # via device-code; the user opens the URL on whatever device they have.
  local mode="$1"; shift
  local tty_flag=""
  [[ "$mode" == "tty" ]] || tty_flag="-T"
  docker compose run --rm $tty_flag -e BROWSER=true \
    --name "$CONTAINER_NAME" hsb gh "$@"
}

say ""
say "=== GitHub CLI Auth Setup ==="
say ""

"$(dirname "$0")/kill-stale.sh" auth-github
say ""

# Pre-check: is there a valid token already?
EXISTING_VOL=$(auth_volume hsb-gh-auth || true)
if [[ -n "$EXISTING_VOL" ]] && volume_has_file "$EXISTING_VOL" 'hosts.yml'; then
  info "Existing GitHub auth found in volume '$EXISTING_VOL'."
  info "Validating token (gh auth status)..."
  if run_gh notty auth status --hostname github.com >/dev/null 2>&1; then
    ok "GitHub token is valid — auth already configured."
    say ""
    info "Confirming required scopes..."
    SCOPES_OUT=$(run_gh notty auth status --hostname github.com 2>&1 || true)
    if printf '%s' "$SCOPES_OUT" | grep -q "'repo'"; then
      ok "Token has 'repo' scope."
    else
      warn "Token may be missing 'repo' scope. Output:"
      printf '%s\n' "$SCOPES_OUT" | sed 's/^/    /'
      say ""
      warn "Re-run 'make clean && make auth-github' to re-authenticate with full scopes."
    fi
    say ""
    say "  → Run 'make up' to start the service."
    say "  → To force a fresh auth: 'make clean' then 'make auth-github'."
    exit 0
  fi
  warn "Existing token rejected by GitHub — re-authentication required."
  say ""
fi

# Choose flow: PAT (if .env has GITHUB_TOKEN) or interactive device flow.
TOKEN_FROM_ENV=$(token_from_env || true)

if [[ -n "$TOKEN_FROM_ENV" ]]; then
  info "GITHUB_TOKEN found in .env — using non-interactive --with-token flow."
  say ""
  if printf '%s' "$TOKEN_FROM_ENV" \
       | docker compose run --rm -T --name "$CONTAINER_NAME" \
           hsb gh auth login --hostname github.com --git-protocol https --with-token; then
    say ""
    ok "Token accepted."
  else
    fail "gh auth login --with-token failed. Check that GITHUB_TOKEN has 'repo' scope."
    exit 1
  fi
else
  info "No GITHUB_TOKEN in .env — starting interactive device-code flow."
  say ""
  say "──────────────────────────────────────────────────────────────────────"
  say "  gh will print a one-time code, then prompt you to open"
  say "  https://github.com/login/device in a browser."
  say ""
  say "  • Local terminal  → press Enter when prompted; gh polls until done."
  say "  • Remote/headless → copy the URL+code into a browser on any device."
  say "──────────────────────────────────────────────────────────────────────"
  say ""
  if run_gh tty auth login \
       --hostname github.com \
       --git-protocol https \
       --web \
       --scopes "repo,read:org,gist"; then
    say ""
    ok "Device flow complete."
  else
    fail "gh auth login --web failed or was cancelled."
    exit 1
  fi
fi

# Final verification.
say ""
info "Verifying final auth state..."
if VERIFY_OUT=$(run_gh notty auth status --hostname github.com 2>&1); then
  printf '%s\n' "$VERIFY_OUT" | sed 's/^/    /'
  say ""
  ok "GitHub authentication complete and persisted to volume '$(auth_volume hsb-gh-auth)'."
  say ""
  say "  → git's credential helper will be wired up automatically on container start"
  say "    (see scripts/docker-entrypoint.sh)."
  say "  → Run 'make up' to start the service."
else
  fail "Auth verification failed:"
  printf '%s\n' "$VERIFY_OUT" | sed 's/^/    /' >&2
  exit 1
fi
