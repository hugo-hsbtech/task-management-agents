# Codex Auth Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add Codex CLI authentication tooling for both the containerised flow (`make auth-codex`) and the local-host flow (`./scripts/auth-codex-host.sh`), so operators can complete `codex login` and persist the resulting `~/.codex/auth.json` to a named Docker volume (container) or to their home directory (host).

**Architecture:**
- The `codex` binary is the open-source CLI from `@openai/codex` (npm). It performs OAuth with `forced_login_method = "chatgpt"` (a config.toml setting hard-checked at runtime by `src/llm_providers/providers/_codex_config.py`).
- Container path mirrors `scripts/auth-github.sh`: one-off Compose container, OAuth in browser, token persisted to a new `hsb-codex-auth` named volume mounted at `/root/.codex`.
- Host path is simpler: seed `~/.codex/config.toml` if missing, then run `codex login` directly. No Docker involvement. The script errors with an install hint if `codex` isn't on PATH (does NOT auto-install globally on the user's machine).

**Tech stack:** bash, docker compose, npm-distributed `@openai/codex` CLI.

**Branch:** Stack on `feat/backlog-agent-codex` (current HEAD `6f1229c`). All commits land in PR #22.

---

## Context for every task

- Worktree: `/home/ubuntu/hugo/task-management-agents/.worktrees/feat/backlog-agent-codex`
- Existing auth pattern to mirror: `scripts/auth-github.sh` (device-code with token persistence), `scripts/_lib.sh` (compose helpers).
- Existing config check (do NOT modify): `src/llm_providers/providers/_codex_config.py::assert_codex_oauth_only` requires:
  - `~/.codex/config.toml` containing `forced_login_method = "chatgpt"` (and optionally `[mcp_servers.*]` blocks)
  - `~/.codex/auth.json` present
- Codex CLI distribution: `@openai/codex@0.130.0` from npm, installs the `codex` binary. Authentication subcommand: `codex login` (browser flow by default; `codex login --help` for any device-code flag — script must detect and use whichever the CLI exposes).

---

## Task 1: Install Codex CLI in the container and add the auth volume

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add codex CLI install to Dockerfile**

  In `Dockerfile`, BELOW the existing `gh` install block (around lines 21-28) and ABOVE the `uv` install (line 30), add a new `RUN` block:

  ```dockerfile
  # Codex CLI: install from npm so `codex login` is available inside the
  # container (selectable backend for backlog agent — see src/llm_providers
  # /providers/openai.py::_CodexBackend).
  RUN npm install -g @openai/codex \
      && codex --version
  ```

  Rationale for `codex --version` at the end of the layer: fails the build early if the install didn't deposit a binary.

- [ ] **Step 2: Add the codex auth volume to docker-compose.yml**

  In `docker-compose.yml`:

  2a. In the `volumes:` block of the `hsb` service (existing entries `./.mcp.json`, `hsb-mcp-auth`, `hsb-gh-auth`, `hsb-claude-state`), add a new line ALPHABETICALLY between `hsb-claude-state` and the next one (or at end, matching the existing grouping):

  ```yaml
        - hsb-codex-auth:/root/.codex
  ```

  2b. In the top-level `volumes:` block at the bottom (existing entries `hsb-mcp-auth`, `hsb-gh-auth`, `hsb-claude-state`), add:

  ```yaml
    hsb-codex-auth:
  ```

- [ ] **Step 3: Build verification**

  ```bash
  cd /home/ubuntu/hugo/task-management-agents/.worktrees/feat/backlog-agent-codex
  docker compose build hsb 2>&1 | tail -20
  ```
  Expected: build succeeds, the `codex --version` line in the RUN block prints a version (e.g. `0.130.0`).

  ⚠️ If `docker compose build` is unavailable in this environment, skip this step and report the limitation. The next task will exercise the same binary inside a `compose run` invocation, which is the real validation.

- [ ] **Step 4: Compose-config verification (always runs)**

  ```bash
  docker compose config 2>&1 | grep -E "(hsb-codex-auth|/root/.codex)" | head -5
  ```
  Expected: both the volume reference and the mount path appear in the resolved config.

- [ ] **Step 5: Commit**

  ```bash
  git add Dockerfile docker-compose.yml
  git commit -m "feat(docker): install @openai/codex CLI and add hsb-codex-auth volume"
  ```

---

## Task 2: Add `scripts/auth-codex.sh` (containerised flow)

**Files:**
- Create: `scripts/auth-codex.sh`

This mirrors `scripts/auth-github.sh`. Read that file end-to-end before starting; copy its structure (script-dir bootstrap, `_lib.sh` sourcing, `compose` wrapper, pre-check for existing valid token, final verification).

Key adaptations:
- Auth target: `codex login` (not `gh auth login`)
- Persistent volume name: `hsb-codex-auth` (replaces `hsb-gh-auth`)
- Volume mount: `/root/.codex/` (replaces `/root/.config/gh`)
- Pre-check file: `auth.json` (replaces `hosts.yml`)
- BEFORE running `codex login`, seed `/root/.codex/config.toml` IF MISSING with:

  ```toml
  # Auto-seeded by scripts/auth-codex.sh — required by
  # src/llm_providers/providers/_codex_config.py::assert_codex_oauth_only.
  forced_login_method = "chatgpt"
  ```

  Do NOT overwrite an existing config.toml — operators may have additional `[mcp_servers.*]` blocks.

- [ ] **Step 1: Create `scripts/auth-codex.sh`**

  Write the file with exact content below. Make it executable (`chmod +x scripts/auth-codex.sh`).

  ```bash
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
  ```

- [ ] **Step 2: Make it executable**

  ```bash
  chmod +x scripts/auth-codex.sh
  ```

- [ ] **Step 3: Syntax check**

  ```bash
  bash -n scripts/auth-codex.sh && echo "syntax ok"
  ```
  Expected: `syntax ok`

  If `shellcheck` is available, also run:
  ```bash
  shellcheck scripts/auth-codex.sh 2>&1 | tail -20
  ```
  Expected: no errors. Warnings on style are OK; flag anything `error`-level.

- [ ] **Step 4: Smoke-run pre-check path**

  Without an existing volume, the script will reach the "Ensuring volume exists" step which requires a real docker daemon. If docker is available in this environment:

  ```bash
  ./scripts/auth-codex.sh 2>&1 | head -20
  ```

  If docker is NOT available, skip this step and rely on Task 5's manual verification by the operator.

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/auth-codex.sh
  git commit -m "feat(scripts): add auth-codex.sh (containerised Codex OAuth)"
  ```

---

## Task 3: Add `scripts/auth-codex-host.sh` (local-host flow)

**Files:**
- Create: `scripts/auth-codex-host.sh`

The host flow is simpler — no Docker. It checks for the `codex` binary, errors out with an install hint if missing, seeds `~/.codex/config.toml`, then runs `codex login` directly.

- [ ] **Step 1: Create `scripts/auth-codex-host.sh`**

  ```bash
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
  #   - Runs `codex login` which writes ~/.codex/auth.json on success.
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
  
  if [[ -f "$AUTH_FILE" ]]; then
    info "Existing auth.json found at $AUTH_FILE."
    info "Skipping login — Codex is already authenticated."
    say ""
    say "  → To force a fresh auth: rm '$AUTH_FILE' then re-run."
    exit 0
  fi
  
  mkdir -p "$CODEX_HOME"
  
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
  
  info "Starting codex login..."
  say ""
  say "──────────────────────────────────────────────────────────────────────"
  say "  codex will print an OAuth URL. Open it in any browser, sign in to"
  say "  ChatGPT, and approve."
  say "──────────────────────────────────────────────────────────────────────"
  say ""
  
  if codex login; then
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
    say "      HSB_RUN_CODEX_INTEGRATION=1 uv run pytest tests/integration/backlog/test_backlog_agent_codex.py -v"
  else
    fail "auth.json missing after login. Re-run ./scripts/auth-codex-host.sh."
    exit 1
  fi
  ```

- [ ] **Step 2: Make it executable**

  ```bash
  chmod +x scripts/auth-codex-host.sh
  ```

- [ ] **Step 3: Syntax check**

  ```bash
  bash -n scripts/auth-codex-host.sh && echo "syntax ok"
  ```
  Expected: `syntax ok`

- [ ] **Step 4: Dry-run the "no binary" path**

  ```bash
  # Simulate `codex` not on PATH by sandboxing PATH.
  PATH=/usr/bin:/bin ./scripts/auth-codex-host.sh 2>&1 | head -10
  ```
  Expected: script exits 1 with the install-hint message. (If `codex` happens to live in `/usr/bin`, adjust the sandbox PATH to exclude it.)

- [ ] **Step 5: Commit**

  ```bash
  git add scripts/auth-codex-host.sh
  git commit -m "feat(scripts): add auth-codex-host.sh (local-host Codex OAuth)"
  ```

---

## Task 4: Wire `auth-codex` into the Makefile

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add the target**

  In `Makefile`, locate the `auth-github` block:

  ```make
  .PHONY: auth-github
  auth-github: ## GitHub gh auth login (persists per HSB_PROJECT in named volume)
  	@./scripts/auth-github.sh
  ```

  IMMEDIATELY BELOW it (before `kill-stale`), add:

  ```make
  .PHONY: auth-codex
  auth-codex: ## Codex CLI login (persists per HSB_PROJECT in named volume)
  	@./scripts/auth-codex.sh
  ```

  Keep the surrounding ordering and tab indentation consistent.

- [ ] **Step 2: Verify make picks up the target**

  ```bash
  make help 2>&1 | grep -i codex
  ```
  Expected: a line `auth-codex     Codex CLI login (persists per HSB_PROJECT in named volume)`.

- [ ] **Step 3: Commit**

  ```bash
  git add Makefile
  git commit -m "feat(make): add auth-codex target"
  ```

---

## Task 5: Final verification + update PR body

- [ ] **Step 1: Full unit + llm_providers test sweep — confirm no regressions**

  ```bash
  uv run pytest tests/unit/ tests/llm_providers/ -q 2>&1 | tail -5
  ```
  Expected: all pass (still 486 + 112).

- [ ] **Step 2: Confirm all scripts parse and Makefile target exists**

  ```bash
  bash -n scripts/auth-codex.sh && bash -n scripts/auth-codex-host.sh && echo "scripts ok"
  make help 2>&1 | grep -E "auth-(codex|github|linear)"
  ```
  Expected: `scripts ok`, then all three auth targets listed.

- [ ] **Step 3: Push and update PR body**

  ```bash
  git push origin feat/backlog-agent-codex
  ```

  Then append to PR #22 body via gh:

  ```bash
  gh pr view 22 --json body --jq .body > /tmp/pr-body.md
  cat >> /tmp/pr-body.md <<'EOF'
  
  ## Update: auth tooling
  
  - `make auth-codex` — containerised flow. `codex login` runs inside the `hsb-agents` image, prints an OAuth URL, persists `auth.json` to the new `hsb-codex-auth` named volume.
  - `./scripts/auth-codex-host.sh` — host flow. Same shape, but runs the local `codex` binary and writes to `$CODEX_HOME` (default `~/.codex/`).
  - Both scripts seed `config.toml` with `forced_login_method = "chatgpt"` if missing; existing config is preserved (operators may have `[mcp_servers.*]` blocks).
  - Dockerfile now installs `@openai/codex` via npm.
  EOF
  gh pr edit 22 --body-file /tmp/pr-body.md
  ```

  Expected: `gh pr edit` succeeds; `gh pr view 22 --web` (if opened) shows the new section.
