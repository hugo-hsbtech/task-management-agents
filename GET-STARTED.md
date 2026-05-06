# Get Started with HSBTech

> Operator onboarding for the HSBTech AI Engineering Workflow. From clone to first running cycle in ~30 minutes once your Linear and GitHub access are squared away.

This guide is for developers who want to **use** HSBTech (drive a Linear backlog through the agent pipeline). For project architecture and design rules, see [README.md](./README.md). For full milestone-acceptance UAT, see [`.planning/MILESTONE-UAT.md`](./.planning/MILESTONE-UAT.md).

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Install](#install)
3. [Authenticate (one-time setup)](#authenticate-one-time-setup)
4. [Verify your install](#verify-your-install)
5. [Your first cycle](#your-first-cycle)
6. [Common workflows](#common-workflows)
7. [Operating modes](#operating-modes)
8. [Knowledge Store](#knowledge-store)
9. [Troubleshooting](#troubleshooting)
10. [Where to go next](#where-to-go-next)

---

## Prerequisites

| Requirement | Why | Notes |
|-------------|-----|-------|
| **Python ≥ 3.12** | Runtime — pinned in `pyproject.toml` | `python3.12 --version` |
| **`git` ≥ 2.30** | Worktree support for parallel mode | `git --version` |
| **`gh` CLI** | GitHub PR delivery surface | `gh auth status` should be green |
| **Linear workspace** (sandbox/test) | System of record — agents read and write here | NOT your production workspace; agents will mutate state |
| **Browser** | One-time Linear MCP OAuth flow | Required only for setup; not for runtime |
| **Anthropic Claude account** | Claude Agent SDK runtime | OAuth2 token via `claude setup-token` — NOT an API key |

**You will NOT need:**

- An `ANTHROPIC_API_KEY` — HSBTech refuses to start with one set (G1 guardrail). Use OAuth2 only.
- A vector DB / embedding store — the Knowledge Store is flat markdown.
- Any cloud infrastructure beyond Linear + GitHub.

---

## Install

```bash
# Clone and enter the repo
git clone <repo-url> hsb
cd hsb

# Create venv (Python 3.12+)
python3.12 -m venv .venv
source .venv/bin/activate

# Install with dev + eval extras (pulls pytest, pytest-asyncio, hypothesis, arize-phoenix)
pip install -e ".[dev,eval]"

# Confirm Typer CLI registered
hsb --help
```

You should see:

```
Usage: hsb [OPTIONS] COMMAND [ARGS]...

Commands:
  create-issue, update-issue, add-comment, link-pr      [Linear ops]
  run, run-next-step, show-state, show-next-action      [Orchestration]
  backlog, builder, git, qa                             [Per-agent groups]
```

If `hsb` is not found, check that `.venv/bin` is on your `PATH` (`which hsb` should resolve).

---

## Authenticate (one-time setup)

> The original Phase 1 spec is at [`.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md`](./.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md). It predates the Linear-MCP corrections in Step 2 below; **this guide supersedes it** for operator setup. Treat HUMAN-SETUP.md as historical context only.

### Step 0 — Prepare your environment

Before authenticating, do a quick preflight to make sure nothing in your environment will break the OAuth handshake or the agent pre-flight check. Skipping this step is the most common cause of the failure modes listed in [Troubleshooting](#troubleshooting).

#### 0a — Confirm port 22227 is free

`mcp-remote` always binds the OAuth callback listener to **`127.0.0.1:22227`** (a fixed port; not configurable). If anything else holds it — most often a stale `mcp-remote` from a previous attempt that crashed without cleanup — the next invocation exits with `EADDRINUSE`, the agent reports `linear: failed`, and OAuth never completes.

```bash
# Find anything listening on 22227
ss -tlnp 2>/dev/null | grep 22227     # Linux
lsof -i :22227                         # macOS / BSD

# If a stale mcp-remote is listed, kill it
kill <pid>

# Confirm the port is free
ss -tlnp 2>/dev/null | grep 22227 || echo "port 22227 free"
```

#### 0b — Audit your user-level Claude Code MCP servers

The Claude Agent SDK that powers HSBTech inherits MCP server definitions from your user-level Claude Code config (`~/.claude.json` and any project-level `.mcp.json`). The HSBTech agents enforce a strict pre-flight: **every** MCP server reported at session init must be in `connected` state. If any user-level server (e.g. `claude.ai Google Drive`, `notion`, `github`) is in `needs-auth` or `failed`, every HSBTech agent invocation will raise — even though the failing server is unrelated to Linear.

```bash
# List user-level MCP servers
jq '.mcpServers | keys' ~/.claude.json 2>/dev/null

# Inspect any cached "needs-auth" entries
cat ~/.claude/mcp-needs-auth-cache.json 2>/dev/null
```

For every server listed, either:

- **Re-authenticate it** inside Claude Code (`/mcp` → reauth the server), or
- **Remove the entry** from `~/.claude.json`'s `mcpServers` block until you have time to authenticate it

The HSBTech agents only need `linear` (and the in-process `agents` SDK server). Any other server that leaks in from your user config must still report `connected` or it will block agents.

#### 0c — Confirm `~/.mcp-auth/` is in expected state

```bash
ls ~/.mcp-auth/ 2>/dev/null
```

- **Empty or missing:** clean slate, proceed to Step 1 / 2.
- **Has `mcp-remote-<version>/<hash>_tokens.json`:** OAuth was completed previously. You can skip Step 2 and jump to Step 2d to validate. If 2d fails, wipe the cache (`rm -rf ~/.mcp-auth/mcp-remote-*/`) and redo Step 2.

#### 0d — Confirm Node toolchain

```bash
node --version    # ≥ 18 recommended
npx --version     # bundled with node
```

`npx` will download `mcp-remote` on first use; nothing to install up-front.

### Step 1 — Anthropic OAuth2 token (NOT API key)

The G1 guardrail in `_sdk_options.py:assert_oauth2_only()` refuses to run if `ANTHROPIC_API_KEY` is set in the environment. Use OAuth2 only.

```bash
# Run the Anthropic CLI token setup (opens a browser)
claude setup-token

# Copy the token output, then add to .env (gitignored)
echo "CLAUDE_CODE_OAUTH_TOKEN=<your-token>" >> .env

# Confirm: ANTHROPIC_API_KEY must NOT be set
env | grep -i ANTHROPIC_API_KEY
# (should produce no output)
```

If you previously had `ANTHROPIC_API_KEY` set anywhere (`.env`, shell config, CI), unset it everywhere before running HSBTech.

### Step 2 — Linear MCP OAuth (one-time, out-of-band)

The Linear MCP server (`mcp.linear.app/mcp`) uses OAuth 2.1, brokered locally by `mcp-remote` (a Node helper that proxies STDIO ↔ remote MCP and handles the OAuth dance). The token is cached at `~/.mcp-auth/mcp-remote-<version>/` (e.g. `~/.mcp-auth/mcp-remote-0.1.37/`) and reused by every subsequent agent invocation.

> **Important:** OAuth must complete *before* you run any HSBTech agent. The agents' MCP pre-flight check refuses to start unless every configured MCP server is already in `connected` state. So you cannot rely on "the first agent run will pop a browser" — by the time the SDK reports `linear: pending`, the pre-flight has already raised. Run the OAuth handshake out-of-band with `mcp-remote` directly, as below, *then* run an agent.

#### 2a — Run the OAuth handshake

```bash
# Foreground process — prints the auth URL and waits for the callback
npx -y mcp-remote https://mcp.linear.app/mcp
```

Expected output:

```
[…] Discovered authorization server: https://mcp.linear.app
[…] Connecting to remote server: https://mcp.linear.app/mcp
[…] OAuth callback server running at http://127.0.0.1:22227
Please authorize this client by visiting:
https://mcp.linear.app/authorize?…&redirect_uri=http%3A%2F%2Flocalhost%3A22227%2Foauth%2Fcallback&…

[…] Authentication required. Waiting for authorization…
```

1. Open the printed URL in your browser
2. Click **Authorize Linear**
3. Browser is redirected to `http://localhost:22227/oauth/callback?code=…&state=…` and shows "Authorization successful! You may close this window."
4. The `mcp-remote` terminal prints `Auth code received → Completing authorization → Connected to remote server → Proxy established successfully`
5. Press **Ctrl+C** to stop `mcp-remote` — the token is now cached and HSBTech agents will reuse it on every invocation

#### 2b — Verify the token landed

```bash
ls ~/.mcp-auth/mcp-remote-*/
# Should list 3 files: <hash>_client_info.json, <hash>_code_verifier.txt, <hash>_tokens.json
```

If those files exist, OAuth is done. The path is *not* `~/.mcp-remote/` — older docs/READMEs may say so; that location is unused.

#### 2c — Remote shell, local browser (VPS / SSH)

If your shell is on a VPS or other remote machine and your browser runs locally, the redirect to `http://localhost:22227/...` hits your *local* browser's localhost — which has no `mcp-remote` listening. The browser shows "site can't be reached" and `mcp-remote` keeps waiting on the VPS. You need to forward the callback to the VPS-side `mcp-remote`. Three options, in order of preference for a Claude-Code-on-VPS setup:

**Option A — Paste the callback URL into Claude Code (most common for this project):**

If you're driving the VPS through Claude Code (the typical HSBTech operator setup), this is the simplest path:

1. Run `npx -y mcp-remote https://mcp.linear.app/mcp` in a Claude Code Bash session.
2. Copy the printed `https://mcp.linear.app/authorize?...` URL into your local browser.
3. Click **Authorize Linear**. Your browser tries to redirect to `http://localhost:22227/oauth/callback?code=...&state=...` and fails (no listener locally). **Copy that full failed-redirect URL** from your browser's address bar.
4. Paste the URL into the Claude Code chat and ask Claude to forward it. Claude will run:
   ```bash
   curl "http://localhost:22227/oauth/callback?code=...&state=..."
   ```
   from the VPS, where `mcp-remote` is listening. The waiting `mcp-remote` process completes the token exchange.

This works because Claude Code's Bash tool runs in the same VPS shell as `mcp-remote`, so a `curl` to `localhost:22227` reaches the right listener.

**Option B — SSH port-forward (preferred when you have shell access without Claude Code):**

Open a fresh SSH session with port-forwarding so your *local* `localhost:22227` is tunnelled to the VPS:

```bash
ssh -L 22227:localhost:22227 <vps-host>
# In the forwarded session:
npx -y mcp-remote https://mcp.linear.app/mcp
```

After clicking Authorize, your local browser's redirect to `localhost:22227` is tunnelled to the VPS automatically — no copy-paste needed.

**Option C — Manual `curl` from a second VPS shell:**

If you have multiple VPS shells but no Claude Code and no port-forwarding, copy the failed-redirect URL and `curl` it yourself:

```bash
# In a second VPS shell, while mcp-remote is still running in the first:
curl "http://localhost:22227/oauth/callback?code=...&state=..."
# Returns: "Authorization successful! You may close this window."
```

In all three options the visible result on the VPS is the same: `mcp-remote` prints `Auth code received → Completing authorization → Connected to remote server → Proxy established successfully`, then you Ctrl+C and the token is cached.

#### 2d — Validate end-to-end

After the token is cached, sanity-check with a no-op Linear read through the agent:

```bash
source .venv/bin/activate
python -c "import asyncio; from hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('List Linear teams. Return JSON: {\"operation\":\"read\",\"result\":\"success\",\"linear_entities\":[],\"error\":null}'))"
```

The agent should connect, list your teams, and return success. If it raises `RuntimeError: Linear MCP server failed to connect`, see the relevant Troubleshooting entry below before continuing.

### Step 3 — Test workspace identifiers

Pick a sandbox Linear team (NOT production), then:

```bash
# Linear → Settings → Workspace → Teams → click your sandbox team
# Copy the team ID from the URL
export LINEAR_TEST_TEAM_ID=<team-id>

# Create one issue you don't mind being mutated repeatedly
export LINEAR_TEST_ISSUE_ID=LIN-XXX
```

Persist these in `.env` if you want them across shells:

```bash
echo "LINEAR_TEST_TEAM_ID=<team-id>" >> .env
echo "LINEAR_TEST_ISSUE_ID=LIN-XXX" >> .env
```

### Step 4 — GitHub access

```bash
# Authenticate gh CLI with `repo` scope (read + write)
gh auth status
# Should show: "Logged in to github.com as <your-handle>"
```

For Phase 2+ live integration tests against `hsb-test-fixture`:

```bash
# Clone or fork the test fixture repo
gh repo clone hugo-hsbtech/hsb-test-fixture
export HSB_TEST_FIXTURE_PATH=$PWD/hsb-test-fixture
```

---

## Verify your install

A 30-second smoke test that everything is wired correctly:

```bash
# Unit tests (no live services needed)
pytest tests/unit/ -x -q
# Expected: 106 passed in ~30s

# Code-based evals (no live services)
pytest tests/evals/code_based/ -x -q
# Expected: 18 passed

# Integration tests collect-only (no live runs)
pytest tests/integration/ --collect-only -q
# Expected: 59 tests collected, 0 errors
```

If any of these fail, stop and check your install before proceeding. Do not skip pre-commit hooks or use `--no-verify`.

---

## Your first cycle

This is the MVP cycle benchmark — driving a single Task from `todo` to `done` through the full agent pipeline.

### Step 1 — Seed a test task

In your sandbox Linear workspace, create:

1. **EPIC:** `[TEST] First HSBTech cycle`
2. **User Story:** `[TEST] Operator can verify the agent pipeline` (child of the EPIC)
3. **Task:** A simple, scoped change like `Add a CHANGELOG.md entry for v0.1.0` (child of the User Story)
   - State: `todo`
   - Description: include acceptance criteria like "File `CHANGELOG.md` exists with a heading `## v0.1.0`"
   - No blocking dependencies

Note the Task ID:

```bash
export TEST_WORK_ITEM_ID=LIN-XXX
```

### Step 2 — Inspect (dry-run)

Verify the agent system sees your task before running it:

```bash
hsb show-state
# Renders Linear EPICs / User Stories / Tasks / QA status / PR links

hsb show-next-action
# Shows the next decision the orchestrator would make — without executing
```

### Step 3 — Run one cycle

```bash
hsb run-next-step
```

What happens:

1. **Global Orchestrator** queries Linear, finds your task at the front of the risk-sorted ready queue
2. **Work Item Orchestrator** opens a single Claude Agent SDK session and:
   - **Step 1 (Intelligence):** queries the Knowledge Store for relevant entries → populates `knowledge_context`
   - Calls **Builder** (`mcp__agents__run_builder`) → implements the scoped change
   - Calls **Git** (`mcp__agents__run_git`) → creates branch `feature/LIN-XXX-...`, commits, opens a PR targeting the EPIC branch
   - Calls **QA** (`mcp__agents__run_qa`) → reviews the PR diff against acceptance criteria
   - If QA approves: marks the task `done`, posts a lifecycle summary comment to Linear
   - If QA finds issues: creates fix subtasks, loops Builder→Git→QA up to 3 times
   - **Step 5 (Knowledge):** evaluates the cycle, writes a Knowledge Store entry if ingestion criteria met

3. Open the GitHub PR → review → merge manually (HSBTech never auto-merges)

### Step 4 — Continuous loop

Once you have multiple ready tasks:

```bash
python run_loop.py
```

This subprocess-launches `hsb run` repeatedly until backlog is empty or you `Ctrl+C`.

---

## Common workflows

### Decompose a plan into a Linear backlog

```bash
# Write your plan to plan.md (markdown with EPIC + User Stories + Tasks)
$EDITOR plan.md

# Backlog Agent reads plan.md and creates the full hierarchy in Linear
hsb backlog plan plan.md
```

The Backlog Agent is **idempotent** (BKPK-05): a second run produces zero new EPICs. It uses `IDEMPOTENCY RULE: list_issues pre-flight` to detect existing items.

### Run multiple tasks in parallel

```bash
hsb run --parallel
```

Main Orchestrator launches multiple Work Item Orchestrators concurrently with `asyncio.gather`, each in its own git worktree under `.worktrees/`. Optimistic-lock claiming via Linear `updatedAt` re-read prevents double-claims (T-4-01 mitigation).

Cleanup is automatic: `try/finally` removes each worktree, `git worktree prune` runs at startup of every parallel dispatch.

### Validate a User Story (UAT)

When all child tasks of a User Story reach `qa_status = approved`, the Global Orchestrator automatically dispatches the UAT Agent. It reads the User Story acceptance criteria, validates each one with evidence, and produces:

- `overall_status`: `approved` or `changes_required`
- `scenarios[]`: per-criterion pass/fail with observable evidence
- `scope_violations[]`: any out-of-scope findings (rejected by G10)

If `changes_required`, fix subtasks are created via the Linear Agent (UATA-03). After they reach QA-approved, UAT re-triggers — up to 3 cycles total (G6).

### Inspect risk priority

The Risk Agent (deterministic, pure Python) computes:

- `quality_score`: starts at 100, deducts −10/QA failure, −5/fix subtask, −15 if UAT failed, −5/rework cycle (RISK-01)
- `risk_level`: low (≥80) / medium (60-79) / high (<60)
- `priority_queue`: sorted by score descending, tiebreak by `updatedAt` ascending (RISK-02)

```bash
# Show ready-task queue with risk scores (visible in `hsb show-state` output)
hsb show-state
```

The Risk Agent's `detect_improvement_triggers()` (skill 14) is the only LLM call in the agent — and it's structurally air-gapped (`allowed_tools=[]`, `mcp_servers=None`, model=haiku, max_turns=3). Triggers are returned as suggestions; they NEVER write to Linear without explicit operator delegation (RISK-04).

### Add knowledge manually

You can pre-seed the Knowledge Store with patterns or guidance:

```bash
mkdir -p knowledge/patterns
$EDITOR knowledge/patterns/asyncio-cli-boundary.md
```

Required frontmatter (8 fields):

```yaml
---
title: AsyncIO + Typer CLI boundary pattern
type: pattern
context: All HSBTech CLI handlers must wrap async work in asyncio.run() at the Typer body
evidence:
  linear_issue: LIN-123
  pr: https://github.com/owner/repo/pull/45
  files: ["src/hsb/cli/main.py"]
insight: Typer handlers run in sync context; placing asyncio.run() inside an already-running coroutine raises RuntimeError
recommendation: Always wrap async agent calls at the CLI body via asyncio.run(coroutine())
applicability: Any new CLI subcommand that calls an async agent function
date: 2026-05-06
---
```

`applicability` MUST be specific (NOT "all tasks", "n/a", "tbd", or empty) — the G9 pre-write hook validator rejects entries violating this.

---

## Operating modes

| Mode | Command | When to use |
|------|---------|-------------|
| **Single-step debug** | `hsb run-next-step` | Stepping through one task at a time; debugging |
| **Cascade (sequential)** | `hsb run` | Default — one task at a time, ordered by Risk Agent priority |
| **Parallel** | `hsb run --parallel` | Multi-task throughput; independent EPICs |
| **Continuous loop** | `python run_loop.py` | Drain the backlog until empty or interrupted |

The same Work Item Orchestrator runs in all four modes — only the dispatch envelope differs.

---

## Knowledge Store

Path: `knowledge/<category>/<entry>.md`

Categories (created automatically): `architecture`, `qa`, `implementation`, `backlog`, `risk`, plus any new ones you create.

Retrieval: Glob + Grep over the directory tree (no vector DB at MVP). The WIO's Step 1 (skill 10) reads relevant entries before dispatching the Builder.

Ingestion: WIO's Step 5 (skill 11) evaluates QA findings + implementation patterns against ingestion criteria. Writes are validated by the `KnowledgeStorageInput` Pydantic model — entries with vague `applicability` fields are rejected (G9).

If retrieval precision degrades as the store grows past ~50 entries, the documented upgrade is `rank-bm25` (no vector DB, no new framework dependency). See AI-SPEC §2 alternatives.

---

## Troubleshooting

### `AssertionError: ANTHROPIC_API_KEY must not be set`

You have `ANTHROPIC_API_KEY` exported somewhere. The G1 guardrail refuses to run with it set.

```bash
unset ANTHROPIC_API_KEY
# Check shell rc files (~/.bashrc, ~/.zshrc) and any `.env` you may have sourced
grep -r "ANTHROPIC_API_KEY" ~/.bashrc ~/.zshrc ~/.profile .env 2>/dev/null
```

Use OAuth2 (`claude setup-token` + `CLAUDE_CODE_OAUTH_TOKEN`) instead.

### `RuntimeError: Linear MCP server failed to connect: [...status: 'failed']`

The most common cause is a **stale `mcp-remote` process** still holding the OAuth callback port (`127.0.0.1:22227`) from a previous attempt that crashed before completing OAuth. Every new `mcp-remote` invocation then exits with `EADDRINUSE` and the agent's pre-flight reports `linear: failed`.

```bash
# Identify what's holding port 22227
ss -tlnp 2>/dev/null | grep 22227    # Linux
lsof -i :22227                        # macOS / BSD

# Confirm it's a stale mcp-remote
ps -p <pid> -o pid,etime,cmd

# Kill it
kill <pid>

# Verify port is free
ss -tlnp 2>/dev/null | grep 22227 || echo "port 22227 free"
```

Then redo Step 2. (Step 0a is the prevention.)

A secondary cause is a corrupt or partial token cache. If killing the stale process doesn't help, also wipe the cache:

```bash
rm -rf ~/.mcp-auth/mcp-remote-*/
# Re-run Step 2
```

### `RuntimeError: ...failed to connect: [{'name': '<other server>', 'status': 'needs-auth'}]`

The agent's pre-flight check refuses to start unless **every** MCP server reported at session init is `connected`. The Claude Agent SDK inherits MCP servers from your user-level Claude Code config, so a `needs-auth` server you never use for HSBTech (e.g. `claude.ai Google Drive`, `notion`) will still block agents.

```bash
# Inspect what's leaking in
jq '.mcpServers | keys' ~/.claude.json 2>/dev/null
cat ~/.claude/mcp-needs-auth-cache.json 2>/dev/null
```

Resolution: either re-authenticate the offending server inside Claude Code (`/mcp` → reauth), or remove its entry from `~/.claude.json`'s `mcpServers` block. Step 0b is the prevention.

### OAuth browser flow doesn't open / wrong machine

`mcp-remote` always binds the callback to `127.0.0.1:22227`. If your shell is on a remote host but your browser runs locally, the redirect cannot reach the listener. See [Step 2c](#2c--remote-shell-local-browser) for the SSH port-forward and manual `curl` callback options.

If `mcp-remote` says `Browser opened automatically` but you don't see anything, it's running headless — open the printed URL manually and proceed as in Step 2c Option B.

### `RuntimeError: error_max_turns` raised mid-cycle

The G7 guardrail caught the WIO hitting its `max_turns` ceiling without converging. The task is automatically marked `blocked` for human review.

Resolution: open the Linear task, read the comment trail to see what step was looping, fix the underlying issue (likely a vague acceptance criterion or a flaky build step), unblock the task, rerun.

### Builder agent committed a `git` operation

This should be impossible (3-defense capability boundary), but if you see it:

1. **Stop everything.** This is a regression of structural enforcement.
2. Check `src/hsb/agents/builder_agent.py` — `BuilderOptions` should NOT include any `git` Bash patterns
3. Check `tests/unit/test_builder_contract.py::test_builder_output_extra_field_rejected` — should be passing
4. File a `BLOCKER` issue and revert the offending change

This is exactly the scenario the 3-defense pattern is designed to prevent.

### QA cycle cap reached at 3

The task hit `qa_cycle_count = 3` and entered tech-debt-annotation mode (QAAG-04). The PR is `approved` with a `tech_debt_annotation` describing what's deferred. Read the annotation, file follow-up Linear tasks for the deferred work, merge the PR.

If the cycle cap is being hit too often (more than ~10% of tasks), the Risk Agent's `detect_improvement_triggers()` will surface a pattern after 2+ similar findings. The trigger is `linear_state == "suggested"` — review and explicitly delegate via `hsb risk approve-trigger <trigger-id>` before any Linear write happens.

### Tests fail in `_require_*` helper

Live integration tests check for specific env vars and skip if missing. If you want them to RUN:

```bash
# Per the operator setup
export LINEAR_TEST_TEAM_ID=...
export LINEAR_TEST_ISSUE_ID=LIN-XXX
export HSB_TEST_FIXTURE_PATH=...
# Then run with -m integration
pytest tests/integration/ -v -m integration
```

If you want them to SKIP (default), don't set the env vars. The unit suite always runs without env vars.

---

## Where to go next

| Goal | Where to look |
|------|---------------|
| Understand the architecture | [README.md](./README.md) — full project explanation |
| Run the full milestone-acceptance UAT | [`.planning/MILESTONE-UAT.md`](./.planning/MILESTONE-UAT.md) — 24-step run-list (~60–90 min) |
| Read the agent contracts | [`agents/AGENT-CONTRACTS.md`](./agents/AGENT-CONTRACTS.md) — JSON schemas |
| Read agent responsibilities | [`agents/AGENTS.md`](./agents/AGENTS.md) — what each agent does and doesn't |
| Read runtime golden rules | [`runtime/RUNTIME-EXECUTION.md`](./runtime/RUNTIME-EXECUTION.md) |
| Read original behavioral specs | [`skills/`](./skills/) — 15 markdown files (skills 00–14); migrated to `.claude/skills/` |
| See per-phase planning history | [`.planning/phases/`](./.planning/phases/) — CONTEXT, RESEARCH, AI-SPEC, VALIDATION, VERIFICATION, PLAN, SUMMARY per phase |
| Review milestone audit | [`.planning/v1.0-MILESTONE-AUDIT.md`](./.planning/v1.0-MILESTONE-AUDIT.md) — 3 iterations: gaps_found → tech_debt → passed |
| Configure Phoenix tracing for production | `.planning/phases/05-enhancement-agents/05-AI-SPEC.md` §7 |
| Plan v2.0 features | After `/gsd-complete-milestone v1.0`, use `/gsd-new-milestone` to start v2.0 — semantic search, ML risk scoring, multi-project intelligence are the documented next-up items |

---

## Quick reference card

```
# One-time setup
ss -tlnp | grep 22227                 # Step 0a — port 22227 must be free
jq '.mcpServers|keys' ~/.claude.json  # Step 0b — audit user-level MCPs
claude setup-token                    # Step 1 — OAuth2 token
echo "CLAUDE_CODE_OAUTH_TOKEN=..." >> .env
npx -y mcp-remote https://mcp.linear.app/mcp   # Step 2a — Linear OAuth (Ctrl+C after success)
ls ~/.mcp-auth/mcp-remote-*/          # Step 2b — verify token cached
export LINEAR_TEST_TEAM_ID=... LINEAR_TEST_ISSUE_ID=LIN-XXX

# Daily use
hsb show-state                        # Inspect Linear state
hsb show-next-action                  # Dry-run next decision
hsb run-next-step                     # Run ONE task lifecycle
hsb run                               # Cascade mode (default)
hsb run --parallel                    # Parallel mode
python run_loop.py                    # Continuous loop

# Plan decomposition
hsb backlog plan plan.md              # Plan → Linear hierarchy

# Test
pytest tests/unit/ -x -q              # 106 unit tests, no live deps
pytest tests/integration/ -v -m integration   # Live runs (env vars required)
```

Welcome to HSBTech.
