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

> This section mirrors [`.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md`](./.planning/phases/01-foundation-and-linear-integration/HUMAN-SETUP.md). The original spec is the source of truth — this is the operator-friendly summary.

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

### Step 2 — Linear MCP browser OAuth (one-time)

The Linear MCP server (`mcp.linear.app/mcp`) uses OAuth 2.1. The first call opens a browser tab; the token is cached at `~/.mcp-remote/` and reused for all subsequent runs.

```bash
source .venv/bin/activate

# Trigger the OAuth flow with a no-op Linear read
python -c "import asyncio; from hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('List Linear teams. Return JSON: {\"operation\":\"read\",\"result\":\"success\",\"linear_entities\":[],\"error\":null}'))"
```

A browser tab will open → log into Linear → grant access → close the tab. The Python call completes and prints the agent's tool calls. **Subsequent calls reuse the cached token without prompting.**

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

### Linear MCP browser flow doesn't open

The token cache at `~/.mcp-remote/` may be stale or the OAuth callback may be blocked.

```bash
# Clear the cache and retry
rm -rf ~/.mcp-remote/
# Re-run the trigger snippet from "Authenticate Step 2"
```

If you're on a remote server without browser, see the `mcp-remote` docs for headless flows.

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
claude setup-token                    # OAuth2 token
echo "CLAUDE_CODE_OAUTH_TOKEN=..." >> .env
python -c "...run_linear_agent..."    # Linear MCP browser flow
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
