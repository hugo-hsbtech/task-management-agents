#!/usr/bin/env bash
# Codex CLI auth setup on the LOCAL HOST (not inside the container).
#
# Use this when you want to run the backlog agent against Codex from
# your dev shell — e.g. for `pytest -m live_codex` or the
# tests/integration/backlog/test_backlog_agent_codex.py integration test.
#
# Side effects:
#   - Requires the `codex` binary on PATH. Errors with an install hint
#     if missing — does NOT install globally without consent.
#   - Creates ~/.codex/config.toml with forced_login_method = "chatgpt"
#     IF MISSING. Existing config.toml is preserved.
#   - Runs `codex login --device-auth` which writes ~/.codex/auth.json on
#     success. Device-auth flow prints a URL + short code instead of using
#     a localhost OAuth callback — works on headless / remote / SSH hosts.
#
# CODEX_HOME override is respected (the same env var is honoured by
# src/llm_providers/providers/_codex_config.py).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CONFIG_FILE="$CODEX_HOME/config.toml"
AUTH_FILE="$CODEX_HOME/auth.json"

say ""
say "=== Codex CLI Auth Setup (host) ==="
say "    CODEX_HOME=$CODEX_HOME"
say ""

if ! command -v codex >/dev/null 2>&1; then
  fail "codex binary not found on PATH."
  say ""
  say "  Install with one of:"
  say "    npm install -g @openai/codex     # recommended (matches Dockerfile)"
  say "    brew install openai/openai/codex"
  say ""
  say "  Then re-run: ./scripts/auth-codex-host.sh"
  exit 1
fi

ok "codex binary found: $(command -v codex) ($(codex --version 2>/dev/null || echo 'version unknown'))"
say ""

mkdir -p "$CODEX_HOME"

# Seed config.toml UNCONDITIONALLY (idempotent: only writes if missing).
# This MUST run before the auth.json early-exit below so a partially
# initialised CODEX_HOME — auth.json present, config.toml missing — heals
# on re-run. assert_codex_oauth_only() requires both files to exist.
if [[ -f "$CONFIG_FILE" ]]; then
  info "config.toml already exists at $CONFIG_FILE — left untouched."
  if ! grep -qE '^forced_login_method\s*=\s*"chatgpt"' "$CONFIG_FILE"; then
    warn "  config.toml does not set forced_login_method = \"chatgpt\"."
    warn "  assert_codex_oauth_only() will reject this at runtime."
    warn "  Add the line manually, or rm $CONFIG_FILE and re-run."
  fi
else
  info "Seeding $CONFIG_FILE..."
  cat > "$CONFIG_FILE" <<'TOML'
# Auto-seeded by scripts/auth-codex-host.sh.
forced_login_method = "chatgpt"
TOML
  ok "config.toml seeded."
fi
say ""

# Now check whether login is already done.
if [[ -f "$AUTH_FILE" ]]; then
  info "Existing auth.json found at $AUTH_FILE."
  info "Skipping login — Codex is already authenticated."
  say ""
  say "  → To force a fresh auth: rm '$AUTH_FILE' then re-run."
  exit 0
fi

info "Starting codex login (device-auth flow)..."
say ""
say "──────────────────────────────────────────────────────────────────────"
say "  codex will print a verification URL and a short code."
say "  Open the URL on ANY device with a browser, enter the code, sign in"
say "  to ChatGPT, and approve. No localhost callback is used."
say "──────────────────────────────────────────────────────────────────────"
say ""

if codex login --device-auth; then
  say ""
  ok "codex login completed."
else
  fail "codex login failed or was cancelled."
  exit 1
fi

say ""
if [[ -f "$AUTH_FILE" ]]; then
  ok "Authenticated. auth.json at $AUTH_FILE."
  say ""
  say "  → You can now run live Codex tests:"
  say "      HSB_RUN_INTEGRATION=1 uv run pytest tests/integration/backlog/test_backlog_agent_codex.py -v"
else
  fail "auth.json missing after login. Re-run ./scripts/auth-codex-host.sh."
  exit 1
fi
