#!/usr/bin/env bash
# Linear OAuth setup via mcp-remote running inside the hsb container.
#
# Flow:
#   1. Pick a free callback port and start mcp-remote with that port mapped.
#   2. Print the authorization URL.
#   3. Wait for either:
#        a) browser-driven callback to localhost:<port> (auto-completes), or
#        b) user-pasted callback URL (we deliver it via `docker exec curl`).
#   4. Verify the token file landed in the hsb-mcp-auth named volume.
#
# Multi-org: tokens are persisted to <HSB_PROJECT>_hsb-mcp-auth, so different
# Linear orgs can be authed by setting HSB_PROJECT before invoking make:
#   HSB_PROJECT=org-acme make auth-linear
# Default project is "task-management-agents" (matches Compose's default).
#
# The FIFO stdin keeps mcp-remote alive past auth: it transitions to a STDIO
# proxy after the token exchange and would otherwise crash on EOF before the
# tokens.json write completes. We tear the container down ourselves once the
# token file appears.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_lib.sh
. "$SCRIPT_DIR/_lib.sh"
cd "$SCRIPT_DIR/.."

CONTAINER_NAME="hsb-run-auth-linear-$$"
LOG_FILE=$(mktemp /tmp/auth-linear-XXXXX.log)
PASTE_FILE=$(mktemp /tmp/auth-linear-paste-XXXXX.txt)
STDIN_FIFO=$(mktemp -u /tmp/auth-linear-stdin-XXXXX.fifo)
mkfifo "$STDIN_FIFO"
# Open read+write so this exec doesn't block waiting for a reader. Holding
# the write-end open keeps mcp-remote's stdin from EOFing mid-token-exchange.
exec 9<>"$STDIN_FIFO"

DOCKER_PID=""
READ_PID=""

cleanup() {
  exec 9>&- 2>/dev/null || true
  [[ -n "$READ_PID"   ]] && kill "$READ_PID"   2>/dev/null || true
  "$SCRIPT_DIR/kill-stale.sh" auth-linear >/dev/null 2>&1 || true
  [[ -n "$DOCKER_PID" ]] && wait "$DOCKER_PID" 2>/dev/null || true
  rm -f "$STDIN_FIFO" "$LOG_FILE" "$PASTE_FILE"
}
trap cleanup EXIT INT TERM

tokens_present() {
  docker exec "$CONTAINER_NAME" \
    find /root/.mcp-auth -name '*tokens.json' 2>/dev/null \
    | grep -q . 2>/dev/null
}

deliver_callback() {
  local url="$1" path
  path=$(printf '%s' "$url" | sed -E 's|^https?://[^/]+||')
  if [[ -z "$path" || "$path" == "$url" ]]; then
    warn "That doesn't look like a localhost callback URL."
    return 1
  fi
  if docker exec "$CONTAINER_NAME" \
       curl -sf "http://localhost:${CALLBACK_PORT}${path}" >/dev/null; then
    ok "Callback delivered to container."
    return 0
  fi
  fail "Failed to deliver callback. Check the URL and try again."
  return 1
}

# Background reader: blocks on /dev/tty for one line, writes it to PASTE_FILE.
# Main loop respawns this after consuming a bad paste.
spawn_reader() {
  : > "$PASTE_FILE"
  ( read -r line < /dev/tty && printf '%s' "$line" > "$PASTE_FILE" ) &
  READ_PID=$!
}

CALLBACK_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")

say ""
say "=== Linear OAuth Setup ==="
say ""

"$SCRIPT_DIR/kill-stale.sh" auth-linear
say ""

EXISTING_VOL=$(auth_volume hsb-mcp-auth || true)
if [[ -n "$EXISTING_VOL" ]] && volume_has_file "$EXISTING_VOL" '*tokens.json'; then
  info "Existing Linear auth found in volume '$EXISTING_VOL'."
  info "Validating token (starting mcp-remote)..."
  EXPECT_REAUTH=0
else
  info "No existing Linear auth — starting fresh OAuth flow."
  info "Starting mcp-remote (callback port: $CALLBACK_PORT)..."
  EXPECT_REAUTH=1
fi

compose run --rm -T --name "$CONTAINER_NAME" \
  hsb npx -y mcp-remote "https://mcp.linear.app/mcp" "${CALLBACK_PORT}" \
  < "$STDIN_FIFO" > "$LOG_FILE" 2>&1 &
DOCKER_PID=$!

# Wait up to 30s for one of three terminal states:
#   1. Auth URL printed     → fresh OAuth flow
#   2. Proxy established    → existing tokens still valid; nothing to do
#   3. Container exited     → error
AUTH_URL=""
ALREADY_AUTHED=0
for _ in $(seq 1 30); do
  AUTH_URL=$(grep -A1 "Please authorize this client by visiting" "$LOG_FILE" 2>/dev/null \
    | grep -oE 'https://[^[:space:]]+' | head -1 || true)
  [[ -n "$AUTH_URL" ]] && break

  if grep -q "Proxy established successfully" "$LOG_FILE" 2>/dev/null; then
    ALREADY_AUTHED=1
    break
  fi

  if ! kill -0 "$DOCKER_PID" 2>/dev/null; then
    fail "Container exited before producing an auth URL. Output:"
    tail -30 "$LOG_FILE" >&2
    exit 1
  fi
  sleep 1
done

if [[ "$ALREADY_AUTHED" == "1" ]]; then
  if tokens_present; then
    ok "Linear token is valid — auth already configured."
    say ""
    say "  → Run 'make up' to start the service."
    say "  → To force a fresh auth: 'make clean' then 'make auth-linear'."
    exit 0
  fi
  fail "Proxy connected but no token file in the auth volume — inconsistent state."
  fail "Try: docker volume rm '$EXISTING_VOL'  then re-run."
  exit 1
fi

if [[ -z "$AUTH_URL" ]]; then
  fail "Auth URL not detected within 30s. Output:"
  tail -30 "$LOG_FILE" >&2
  exit 1
fi

if [[ "$EXPECT_REAUTH" == "0" ]]; then
  warn "Existing token rejected by Linear — re-authentication required."
  say ""
fi

ok "mcp-remote is running and waiting for the OAuth callback."
say ""
say "Open this URL to authorize Linear access:"
say ""
say "    $AUTH_URL"
say ""
say "──────────────────────────────────────────────────────────────────────"
say "  After approving, your browser is redirected to:"
say "    http://localhost:${CALLBACK_PORT}/oauth/callback?code=..."
say ""
say "  • Local browser  → auth completes automatically; just wait."
say "  • Remote/headless → the redirect will fail to load. Copy the FULL"
say "    URL from your browser's address bar and paste it below."
say "──────────────────────────────────────────────────────────────────────"
say ""
printf 'Paste callback URL (or wait for browser): '

spawn_reader

# Main loop: tokens appearing wins; container death loses; paste gets delivered.
while true; do
  if tokens_present; then
    say ""
    ok "Token exchange complete."
    break
  fi

  if ! kill -0 "$DOCKER_PID" 2>/dev/null; then
    say ""
    fail "Container exited unexpectedly. Last output:"
    tail -30 "$LOG_FILE" >&2
    exit 1
  fi

  if [[ -s "$PASTE_FILE" ]]; then
    pasted=$(tr -d '[:space:]' < "$PASTE_FILE")
    : > "$PASTE_FILE"
    say ""
    info "Delivering pasted callback..."
    if deliver_callback "$pasted"; then
      info "Waiting for token file..."
      for _ in $(seq 1 10); do
        tokens_present && break
        sleep 1
      done
    else
      printf '> '
      spawn_reader
    fi
  fi

  sleep 1
done

# Verify against the named volume the running container is mounting.
if tokens_present; then
  VOL=$(docker inspect --format \
    '{{range .Mounts}}{{if eq .Destination "/root/.mcp-auth"}}{{.Name}}{{end}}{{end}}' \
    "$CONTAINER_NAME" 2>/dev/null || true)
  ok "Token file present in volume '${VOL:-hsb-mcp-auth}'."
  say ""
  say "Run 'make up' to start the service."
else
  fail "Token file missing after auth flow ended. Re-run 'make auth-linear'."
  exit 1
fi
