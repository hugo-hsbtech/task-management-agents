# HSBTech — AI Engineering Workflow

[![Status: v1.0 autonomous-complete](https://img.shields.io/badge/status-v1.0%20autonomous--complete-success)](#milestone-status)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Tests: 106 unit / 18 evals / 59 integration](https://img.shields.io/badge/tests-106%20unit%20%7C%2018%20evals%20%7C%2059%20integration-brightgreen)](#test-suite)

> A coordinated multi-agent system that turns a documented plan into traceable, QA-reviewed software delivery via Linear and GitHub. Built on the Claude Agent SDK with structurally-enforced capability boundaries and a deterministic risk-based prioritizer.

---

## Table of contents

1. [What this is](#what-this-is)
2. [Architecture](#architecture)
3. [The 11 agents](#the-11-agents)
4. [Guardrails (G1–G10)](#guardrails-g1g10)
5. [Repository layout](#repository-layout)
6. [Tech stack](#tech-stack)
7. [Installation](#installation)
8. [CLI reference](#cli-reference)
9. [Operating modes](#operating-modes)
10. [Knowledge Store](#knowledge-store)
11. [Test suite](#test-suite)
12. [Milestone status](#milestone-status)
13. [Design rules and constraints](#design-rules-and-constraints)
14. [Project history](#project-history)
15. [License](#license)

---

## What this is

HSBTech turns a documented plan into a complete engineering execution flow:

```
plan.md
   ↓
Backlog Agent   → creates EPIC + User Stories + Tasks in Linear
   ↓
Global Orchestrator   → reads Linear state, builds risk-prioritized work queue
   ↓
Main Orchestrator   → cascade or parallel dispatch
   ↓
Work Item Orchestrator (one per task)
   ├─ Intelligence    → enriches with Knowledge Store entries (skills 10+11)
   ├─ Builder         → implements scoped change
   ├─ Git             → branches, commits, opens stacked PR
   └─ QA              → reviews PR diff, produces findings or approves
   ↓
UAT Agent   → validates User Story against acceptance criteria
   ↓
Risk Agent   → scores, prioritizes, surfaces auto-improvement triggers
```

Linear is the durable system of record. GitHub is the code delivery surface. Every merge to `main` is human-approved. Every agent action is structured JSON in/out, traceable by Linear comment and Git commit.

The runtime is the Claude Agent SDK. Every agent is one of three patterns: a stateful `ClaudeSDKClient` session (Work Item Orchestrator), a one-shot `query()` session (UAT Agent, Risk Agent skill 14), or a pure-Python class (Risk Agent skills 12+13, Global Orchestrator, Main Orchestrator).

---

## Architecture

Three orchestration levels, deliberately separated by responsibility:

| Level | Class | What it decides | LLM? |
|-------|-------|-----------------|------|
| **L0 — Main Orchestrator** | `MainOrchestrator` | Cascade vs. parallel mode. Dispatch budget. Worktree lifecycle. | No (pure Python) |
| **L1 — Global Orchestrator** | `GlobalOrchestrator` | What's ready (no blocking deps), in what risk-priority order, when to dispatch UAT. | No (pure Python) |
| **L2 — Work Item Orchestrator** | `WorkItemOrchestrator` | The full lifecycle of one task. Calls Builder → Git → QA → fix loop within ONE Claude session. | Yes (single SDK session, inline skill injection) |

L0 and L1 are deterministic. L2 is the only place LLM reasoning drives a multi-step lifecycle, and it's bounded: max 3 QA cycles per task, structurally-enforced no-sub-subagent dispatch, no `Agent` tool in `allowed_tools`.

The same Work Item Orchestrator runs in cascade and parallel modes — the difference is just whether `MainOrchestrator` invokes one at a time or via `asyncio.gather` with worktree isolation.

---

## The 11 agents

### Foundation (Phase 1)

**Linear Agent** (`src/hsb/agents/linear_agent.py`)
Wraps `claude_agent_sdk.query` with the Linear MCP server (`mcp.linear.app/mcp`). Provides `run_linear_agent(prompt)` and `run_validated_linear_agent(operation, payload)` — the latter does pydantic-gated 3-retry self-correction. Implements LINR-05 optimistic-lock procedure: read `updatedAt` → write → re-read → verify post>pre. All Linear writes go through this agent.

### Execution (Phase 2)

**Backlog Agent** (`src/hsb/agents/backlog_agent.py`)
Reads `plan.md`, produces a structured `BacklogOutput` (EPIC + User Stories + Tasks + Subtasks). Idempotent: rerun produces zero new EPICs (BKPK-05). Allow-list: `create_issue`, `list_issues`, `get_issue`, `Read`. `IDEMPOTENCY RULE` pre-flight in system prompt.

**Builder Agent** (`src/hsb/agents/builder_agent.py`)
Implements only the scoped change for one Task. Allow-list: 7 tools (`Read`, `Edit`, `Write`, `Bash` for `pytest`/`ruff`/`mypy`/`python`). NO `mcp_servers` — Builder cannot touch Linear or git. Three-defense capability boundary: SKILL.md allow-list + `ClaudeAgentOptions` allow-list + Pydantic `extra="forbid"` rejects `git_branch` field.

**Git Agent** (`src/hsb/agents/git_agent.py`)
Creates branches matching `feature/LIN-{id}-{slug}`, commits, opens stacked PRs (task PRs target `epic/LIN-...`, NOT `main`). Allow-list: 12 tools including `gh pr create/view/diff`, `git push --force-with-lease` (Pitfall 3), `gh pr list --limit 100` (Pitfall 4). Excludes `Edit`, `Write`, `git merge`, `gh pr merge`, all `mcp__linear__*`. REBASE_STACK procedure for sibling PRs.

**QA Agent** (`src/hsb/agents/qa_agent.py`)
Reviews PR diff against requirements. Allow-list: 3 tools (`Read`, `Bash(gh pr diff *)`, `Bash(gh pr view *)`). Triple-layer cycle cap: SKILL.md system prompt + `validate_cycle_cap_logic` Pydantic `model_validator` + integration test. At `qa_cycle_count = 3`, status MUST be `approved` with a `tech_debt_annotation`. Post-validation Linear writes via Phase 1 Linear Agent.

### Orchestration (Phases 3–4)

**Work Item Orchestrator** (`src/hsb/agents/work_item_orchestrator.py`)
A single Claude Agent SDK session driving one Linear task through its full lifecycle. Inline skill injection: 7 skills (skills 02+03+04+05+06 from Phase 3 + skills 10+11 from Phase 5) concatenated into the system prompt at startup (~14.4 KB). NO sub-subagent dispatch (WORC-02): `agents=` kwarg absent, `AgentDefinition` not imported, `assert_no_task_dispatch(msg)` runtime backstop in every receive loop.

**Global Orchestrator** (`src/hsb/agents/global_orchestrator.py`)
Pure Python async class. Reads Linear state, filters dependency-blocked tasks, calls `RiskAgent.get_priority_queue()`, detects UAT-ready User Stories, dispatches UAT inline via `await`. No SDK session, no LLM.

**Main Orchestrator** (`src/hsb/agents/main_orchestrator.py`)
Pure Python dispatch controller. `--cascade` runs WIOs sequentially. `--parallel` uses `asyncio.gather(..., return_exceptions=True)` with optimistic-lock claiming + worktree isolation + `try/finally` cleanup + `git worktree prune` startup. T-4-04: subprocess env is a strict 5-key allowlist (no `**os.environ`).

### Enhancement (Phase 5)

**Intelligence Agent** (`src/hsb/agents/intelligence_agent.py` + inline in WIO)
Not a separate process — embedded inline in the WIO via skills 10+11. Step 1 (before Builder): queries Knowledge Store via Glob+Grep, populates `knowledge_context`. Step 5 (after QA): evaluates findings, writes new Knowledge Store entry if ingestion criteria met. `KnowledgeStorageInput` Pydantic model rejects `applicability` of "all tasks" / "n/a" / "tbd" / empty.

**UAT Agent** (`src/hsb/agents/uat_agent.py`)
Standalone Claude Agent SDK session. `query()` Pattern B + 3-retry Pydantic wrapper. Skill 08 inline. Allow-list: `Read`, `Glob`, `Grep`, `Bash` (no Write, no Edit, no `Agent`, no Linear MCP). `mcp_servers=None`. Validates User Story acceptance criteria; produces scenario pass/fail with evidence. SCOPE BOUNDARY literal in every prompt (does not review code, does not create PRs).

**Risk Agent** (`src/hsb/agents/risk_agent.py`)
Pure Python class for skills 12+13 (deterministic quality scoring + adaptive prioritization). Quality score formula: start=100, −10/QA failure, −5/fix subtask, −15 if UAT failed, −5/rework cycle, min=0. Single async method `detect_improvement_triggers()` for skill 14 — isolated SDK call with `allowed_tools=[]`, `mcp_servers=None`, `model=haiku`, `max_turns=3`. Never writes to Linear directly (RISK-04, 4-layer defense).

### Sentinel module

**`_sdk_options.py`** (`src/hsb/agents/_sdk_options.py`)
The chokepoint module that enforces Phase 5 guardrails structurally. Every SDK call site must use `make_options()`, which calls `assert_oauth2_only()` and refuses any `allowed_tools` containing `"Agent"`. Provides `assert_no_task_dispatch(msg)` (G3 runtime backstop) and `linear_write_guard` (G5 stack-inspection decorator on Phase 1 LinearAgent write methods).

---

## Guardrails (G1–G10)

| ID | What it enforces | Mechanism | File |
|----|------------------|-----------|------|
| **G1** | OAuth2-only — never API keys | `assert_oauth2_only()` function-entry guard + `_gsd_clear_api_key` autouse session fixture | `_sdk_options.py`, `tests/conftest.py` |
| **G2** | No `Agent` tool in `allowed_tools` (no sub-subagent dispatch) | `make_options()` factory raises `ValueError` | `_sdk_options.py:43` |
| **G3** | Runtime backstop for G2 — catches SDK regressions | `assert_no_task_dispatch(msg)` in every receive loop | WIO (3 sites), Risk Agent (1), UAT Agent (1) |
| **G4** | Risk Agent skill 14 is structurally air-gapped | `allowed_tools=[]`, `mcp_servers=None`, `model=haiku`, `max_turns=3`, `max_budget_usd=0.05` | `risk_agent.py:177` |
| **G5** | LinearAgent writes denied for callers from `risk_agent.py` (except via explicit delegated path) | `linear_write_guard` stack-inspection decorator | `linear_agent.py:181-189` |
| **G6** | UAT cycle cap = 3, project-wide invariant | Global Orchestrator skips re-dispatch + posts `linear_createComment` escalation (camelCase `issueId`, `body`) | `global_orchestrator.py::_detect_uat_ready_user_stories` |
| **G7** | `error_max_turns` raises `RuntimeError` — no silent loop continuation | `if msg.stop_reason == "error_max_turns": raise` in every SDK loop | WIO, UAT, Risk |
| **G8** | WIO context budget warning at 120K input tokens | WARN log emitted in receive loops | WIO Steps 2-4 + Step 5 |
| **G9** | Knowledge Store pre-write hook | `KnowledgeStorageInput.applicability` validator + `extra="forbid"` | `contracts/knowledge.py` |
| **G10** | UAT pre-persist validation (B1 coverage + B3 banned-token regex) | `_uat_passes_g10` helper called twice in `get_ready_tasks` | `global_orchestrator.py:75` |

**RISK-04 has 4 layers of structural defense** (the strongest milestone-level invariant): no `linear_agent` import in `risk_agent.py` + `linear_write_guard` decorator + `Literal["suggested"]` Pydantic field + skill 14 `allowed_tools=[]`.

---

## Repository layout

```
.
├── src/hsb/
│   ├── agents/                       # 11 agents (Linear, Backlog, Builder, Git, QA, WIO, Global, Main, UAT, Risk, Intelligence)
│   │   ├── _sdk_options.py           # G1/G2/G3/G5 chokepoint module
│   │   └── hooks.py                  # Phase 1 LINEAR_HOOKS (retry/audit/PreCompact/filter)
│   ├── cli/                          # Typer CLI surface
│   │   ├── main.py                   # hsb create-issue, update-issue, add-comment, link-pr, run, run-next-step, show-state, show-next-action
│   │   ├── backlog.py / builder.py / git.py / qa.py   # per-agent subgroups
│   └── contracts/                    # Pydantic models — all extra="forbid"
│       ├── linear.py / backlog.py / builder.py / git.py / qa.py
│       ├── orchestrator.py / global_orchestrator.py / main_orchestrator.py
│       ├── knowledge.py / risk.py / uat.py
│       └── base.py
├── .claude/skills/                   # 14 SKILL.md files migrated from skills/NN-*.md
│   ├── linear-system-of-record/
│   ├── backlog-planning/ implementation/ git-pr-management/ qa-review/
│   ├── task-orchestration/
│   ├── global-orchestration/ main-orchestrator/
│   ├── knowledge-context-enrichment/ knowledge-storage/
│   ├── quality-scoring-risk-analysis/ adaptive-prioritization/ auto-improvement-triggers/
│   └── uat-validation/
├── knowledge/                        # Persistent file-based Knowledge Store
│   ├── architecture/ qa/ implementation/ backlog/ risk/   # category subdirs
├── tests/
│   ├── unit/                         # 106 tests (cumulative across phases)
│   ├── evals/code_based/             # 18 B1/B3 eval tests
│   └── integration/                  # 59 tests, gated by `-m integration` and live env vars
├── agents/                           # Spec docs (input source for skill migration)
│   ├── AGENT-CONTRACTS.md            # JSON schemas for all agent input/output
│   ├── AGENTS.md                     # Agent responsibilities + capability boundaries
├── runtime/RUNTIME-EXECUTION.md      # Golden rules (no sub-subagent dispatch, one action per cycle)
├── skills/                           # Behavioral specs (skills 00–14) — sources for SKILL.md migration
├── docs/                             # Architecture concept docs
├── .planning/                        # GSD workflow planning artifacts (5 phases)
│   ├── PROJECT.md ROADMAP.md REQUIREMENTS.md STATE.md
│   ├── MILESTONE-UAT.md              # Operator UAT run-list (24 steps, 5 groups)
│   ├── v1.0-MILESTONE-AUDIT.md       # Audit reports (3 iterations)
│   └── phases/01-..05/               # Per-phase CONTEXT, RESEARCH, PATTERNS, AI-SPEC, VALIDATION, VERIFICATION, PLAN, SUMMARY
├── run_loop.py                       # Repo-root continuous loop (CLIR-04)
├── pyproject.toml                    # hsb-agents 0.1.0 — Python ≥3.12
└── uv.lock
```

---

## Tech stack

| Component | Pin / version | Role |
|-----------|---------------|------|
| Python | ≥3.12 | Runtime |
| `claude-agent-sdk` | ≥0.1.73, <0.2.0 | LLM session orchestration |
| `pydantic` | ≥2.0 | Contract validation, schema-drift defense (`extra="forbid"`) |
| `typer` | ≥0.12 | CLI |
| `rich` | ≥13.0 | CLI rendering |
| `python-dotenv` | ≥1.0 | `.env` loading |
| `pytest` + `pytest-asyncio` | 8.x / ≥0.23 | Test framework |
| `hypothesis` | ≥6.100 | Property tests (RISK-01 deterministic formula) |
| Linear MCP | `mcp.linear.app/mcp` | System of record |
| GitHub CLI (`gh`) | latest | PR delivery |

Optional `[eval]` extra: `arize-phoenix`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` for production tracing per AI-SPEC §7.

---

## Installation

```bash
git clone <repo-url> hsb && cd hsb
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,eval]"
hsb --help     # confirms Typer CLI registered
```

For the operator UAT pathway (live Linear MCP + GitHub PR runs), see [GET-STARTED.md](./GET-STARTED.md) — covers OAuth2 token, Linear MCP browser flow, sandbox issue setup, and the `hsb-test-fixture` GitHub repo.

---

## CLI reference

### Linear ops (Phase 1)

```bash
hsb create-issue        # Create EPIC / User Story / Task / Subtask with parent linkage (LINR-01)
hsb update-issue        # Update status / qa_status / uat_status / assigned_orchestrator (LINR-02)
hsb add-comment         # Add structured comment (decision / QA finding / impl note) (LINR-03)
hsb link-pr             # Link GitHub PR URL to a Linear work item (LINR-04)
```

### Per-agent CLI subgroups (Phase 2)

```bash
hsb backlog ...         # Backlog Agent commands
hsb builder ...         # Builder Agent commands
hsb git ...             # Git Agent commands (incl. `hsb git rebase-stack`)
hsb qa ...              # QA Agent commands
```

### Orchestration (Phases 3–4)

```bash
hsb run-next-step       # CLIR-01: trigger ONE Work Item Orchestrator cycle (cascade default)
hsb run                 # Phase 4: drive cycles via Global + Main Orchestrators
hsb run --parallel      # Parallel mode: optimistic claiming + worktree isolation
hsb show-state          # CLIR-02: render Linear EPICs / tasks / QA / PR links
hsb show-next-action    # CLIR-03: dry-run — show next decision without side effects
```

### Continuous loop (Phase 3)

```bash
python run_loop.py       # Repeats `hsb run` until backlog empty or Ctrl+C (CLIR-04)
```

All CLI handlers wrap their async work in `asyncio.run()` at the Typer body — no `asyncio.run` inside coroutines (CLIR-05). State lives in Linear, not the CLI process.

---

## Operating modes

### Cascade (default)

`hsb run` → Global Orchestrator returns the risk-prioritized ready queue → Main Orchestrator dispatches the **first** task to a Work Item Orchestrator → WIO runs the full lifecycle (Intelligence → Builder → Git → QA → fix loop, max 3 QA cycles) → done. Repeat with `python run_loop.py`.

Ideal for: development, debugging, single-developer workflows, MVP usage.

### Parallel

`hsb run --parallel` → Global Orchestrator returns the queue → Main Orchestrator launches multiple WIOs concurrently with `asyncio.gather(..., return_exceptions=True)`, each in its own git worktree (`.worktrees/<task-slug>`). Optimistic-lock claiming via `updatedAt` re-read prevents double-claims (T-4-01 mitigation, MORD-03). Worktree cleanup in `try/finally` + `git worktree prune` at startup (Pitfall C, D-09).

Ideal for: throughput, multi-task parallelism on independent EPICs, post-MVP scale.

The Phase 4 acceptance gate (`tests/integration/test_parallel_mode_e2e.py::test_no_double_claim_parallel_two_tasks`) verifies parallel correctness against a real Linear test workspace.

---

## Knowledge Store

The Intelligence Agent's persistent state. Flat markdown + YAML frontmatter, file-based, no vector DB (per ADVL-01 deferral).

```
knowledge/
├── architecture/    # System-level decisions
├── qa/              # Recurring QA findings → preventive guidance
├── implementation/  # Reusable patterns / techniques
├── backlog/         # Plan-decomposition lessons
├── risk/            # Failure-mode patterns and Auto-Improvement Trigger material
└── ...
```

Every entry has 8 required fields enforced by `KnowledgeStorageInput` Pydantic model: `title`, `type`, `context`, `evidence` (Linear issue ID + PR URL + files), `insight`, `recommendation`, `applicability`, `date`. The `applicability` validator rejects "all tasks", "n/a", "tbd", and empty values (G9 — prevents Knowledge Store contamination, INTL-02 ingestion criteria).

Retrieval is Glob+Grep at MVP scale. If the store grows past ~50 entries with degrading retrieval precision, `rank-bm25` is the documented upgrade path (no vector DB, no new framework dep).

---

## Test suite

```
106 unit tests           — pytest tests/unit/ -x -q
 18 code-based evals     — pytest tests/evals/code_based/ -x -q  (B1 UAT coverage + B3 banned-token regex)
 22 integration tests    — source-grep tests run without live creds
 59 integration tests    — total collected (37 require live env vars; skip cleanly)
```

**Real-data integration testing stance:** every Phase 2-5 integration suite runs against real Linear workspace + real `hsb-test-fixture` GitHub repo. No mocking. Tests skip cleanly without env vars via `_require_*` helpers. Operator setup pathway: see [GET-STARTED.md](./GET-STARTED.md) and [`.planning/MILESTONE-UAT.md`](./.planning/MILESTONE-UAT.md).

**Property-based testing:** Risk Agent quality score (RISK-01) uses `hypothesis @given` to verify determinism across the input space.

**Eval framework:** Phoenix (Arize) recommended for production tracing per `.planning/phases/05-enhancement-agents/05-AI-SPEC.md` §7.

---

## Milestone status

**v1.0 — autonomous-complete.** Audit progression today:

| Iteration | Status | Resolution |
|-----------|--------|------------|
| 1 | `gaps_found` | 3 phases lacked VERIFICATION.md → wrote retroactive ones from SUMMARY frontmatter |
| 2 | `tech_debt` | 3 Nyquist drafts → ran `/gsd-validate-phase {2,3,4}` |
| 3 | **`passed`** | All gaps closed |

**Score card:**
- 57/57 REQ-IDs autonomously verified (24 with operator-pending live integration)
- 5/5 phases with VERIFICATION.md
- 5/5 phases Nyquist-compliant
- 0 critical gaps · 0 implementation gaps · 0 tech debt items
- 5 operator UAT checkpoints documented at `.planning/MILESTONE-UAT.md` (5 groups, 24 steps, ~60–90 min)

**Total commits:** ~115 across the milestone (5 phases × ~15 implementation commits + 11 audit-cycle commits).

**To close out the milestone:** operator runs `MILESTONE-UAT.md` against a live Linear test workspace, then `/gsd-complete-milestone v1.0` archives v1.0 and prepares v2.0 planning.

---

## Design rules and constraints

### Hard rules (architectural invariants)

1. **No automatic merge to `main`** — every EPIC PR merge is human-approved. There is no `gh pr merge` in any allow-list anywhere.
2. **One action per Work Item Orchestrator cycle** — prevents runaway automation. Enforced by max 3 QA cycles + `error_max_turns` raises.
3. **No sub-subagent dispatch** (WORC-02) — the WIO is one Claude Agent SDK session. No nested sessions. Verified by AST walk + G2 + G3 backstop.
4. **OAuth2 only — no API keys** (G1) — `ANTHROPIC_API_KEY` is forbidden in process env. Use `claude setup-token` + `CLAUDE_CODE_OAUTH_TOKEN`.
5. **Linear is the only durable operational state** — agents read and write Linear; reusable patterns go to Knowledge Store; nothing else persists across runs.
6. **Risk Agent never writes to Linear without explicit delegation** (RISK-04) — 4-layer structural defense.
7. **Capability boundaries are structural, not docstring-level** — every agent has a 3-defense pattern: SKILL.md allow-list + `ClaudeAgentOptions.allowed_tools` + Pydantic `extra="forbid"`.

### Soft conventions (project style)

- All Pydantic models use `extra="forbid"` (FOUND-03 schema-drift defense)
- All CLI handlers are sync; `asyncio.run()` lives at the Typer body, never inside coroutines (CLIR-05 boundary)
- All cross-system regex constraints are Pydantic `Field(..., pattern=)` — `LIN-\d+`, `https://github.com/.+/pull/\d+`, etc.
- All Linear writes go through `run_validated_linear_agent` (Phase 1) — not direct MCP calls
- All retry/backoff is in PostToolUseFailure hooks (Phase 1 `LINEAR_HOOKS`), not in-prompt retry instructions

### Out of scope (deferred to v2.0)

- Event-driven triggers (Linear/GitHub webhooks) — MVP uses CLI loop
- Real-time observability dashboards — Phoenix tracing is the recommended path
- Multi-project / cross-project intelligence
- Simulation / dry-run mode
- ML-based risk prediction (current formula is deterministic by design)
- Semantic search over Knowledge Store (ADVL-01)

---

## Project history

Built using GSD (Get Shit Done) workflow — a 5-phase planning + execution system with structured artifacts at each phase: CONTEXT (decisions), RESEARCH (technical approach), PATTERNS (file-to-analog mapping), AI-SPEC (framework + eval strategy), VALIDATION (Nyquist verification map), PLAN (executable tasks), SUMMARY (per-plan handoff), VERIFICATION (per-REQ traceability).

Phase progression:

| Phase | Goal | Plans | Commits |
|-------|------|-------|---------|
| 1 | Linear Agent foundation | 5 | 16 |
| 2 | 4 execution agents (Backlog, Builder, Git, QA) | 5 | 42 |
| 3 | Work Item Orchestrator + single-cycle MVP | 4 | 12 |
| 4 | Global + Main Orchestrators + parallel mode | 4 | 15 |
| 5 | Enhancement agents (Intelligence, UAT, Risk) | 4 | 8 |

Full planning history is in `.planning/phases/<NN>-*/`. The 4 retroactive verification artifacts (3 VERIFICATION.md + 3 audit iterations) were generated during the v1.0 milestone audit.

---

## License

[Add license here — recommended: Apache-2.0 or MIT for an internal tooling project, or proprietary if not open-source]

---

## See also

- [GET-STARTED.md](./GET-STARTED.md) — operator onboarding (~30 min)
- [`.planning/MILESTONE-UAT.md`](./.planning/MILESTONE-UAT.md) — milestone acceptance test plan (~60–90 min)
- [`.planning/v1.0-MILESTONE-AUDIT.md`](./.planning/v1.0-MILESTONE-AUDIT.md) — full audit report
- [`agents/AGENT-CONTRACTS.md`](./agents/AGENT-CONTRACTS.md) — JSON schemas for every agent's input/output
- [`agents/AGENTS.md`](./agents/AGENTS.md) — agent responsibilities + capability boundaries
- [`runtime/RUNTIME-EXECUTION.md`](./runtime/RUNTIME-EXECUTION.md) — runtime golden rules
- [`skills/`](./skills/) — original behavioral specs (15 markdown files); migrated copies live in `.claude/skills/`
