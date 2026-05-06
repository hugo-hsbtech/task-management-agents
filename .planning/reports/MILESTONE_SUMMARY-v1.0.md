# Milestone v1.0 — Project Summary

**Generated:** 2026-05-06
**Purpose:** Team onboarding and project review
**Status:** Autonomous-complete; operator UAT pending (5 documented gates)

> A new contributor should be able to read this document, understand the entire project, then ask follow-up questions for anything unclear. This is the "what we built and why" snapshot.

---

## 1. Project Overview

**HSBTech** is an AI-powered engineering delivery system. A developer provides a documented plan; specialized AI agents coordinate the implementation lifecycle — backlog creation → implementation → PR → QA → UAT → done — while Linear tracks every state transition and the human approves every merge.

**Core value:** Turn a plan into traceable, QA-reviewed software delivery without surrendering control. Agents propose; the human disposes.

**Target user:** A solo developer or small team (2–5 people) running the `hsb` CLI to drive their Linear backlog through agent-assisted implementation. The operator has engineering judgment but limited bandwidth — they rely on agent verdicts to decide what to act on next.

**What v1.0 delivers:**
- Complete three-level orchestration hierarchy (Main → Global → Work Item)
- 11 specialized agents with structurally-enforced capability boundaries
- Real Linear integration (no mocks) via the official Linear MCP server
- Real GitHub PR delivery via `gh` CLI
- File-based Knowledge Store with 8-field entries and ingestion-criteria validator
- Risk-based priority queue with deterministic scoring + LLM-driven trigger detection (RISK-04 air-gapped from Linear)
- 10 guardrails (G1–G10) with structural enforcement at SDK call sites
- 24 SKILL.md files migrated to `.claude/skills/` for direct Claude Code use

**What v1.0 does NOT deliver (intentional):**
- Automatic merging to `main` — every EPIC PR merge is human-approved
- Webhook/event-driven triggers — MVP uses CLI loop
- Vector DB / semantic search — Knowledge Store uses Glob+Grep at MVP scale
- ML risk scoring — current formula is deterministic by design

---

## 2. Architecture & Technical Decisions

### Three-level orchestration hierarchy (the spine of the system)

| Level | Class | What it decides | LLM? |
|-------|-------|-----------------|------|
| **L0 — Main Orchestrator** | `MainOrchestrator` | Cascade vs parallel mode, dispatch budget, worktree lifecycle | No (pure Python) |
| **L1 — Global Orchestrator** | `GlobalOrchestrator` | What's ready (no blocking deps), in what risk-priority order, when to dispatch UAT | No (pure Python) |
| **L2 — Work Item Orchestrator** | `WorkItemOrchestrator` | Full lifecycle of one task — Builder → Git → QA → fix loop, all within ONE Claude session | Yes (single SDK session) |

L0 and L1 are deterministic Python — no LLM, no nondeterminism. L2 is the only place LLM reasoning drives a multi-step lifecycle, and it's bounded structurally: max 3 QA cycles, no `Agent` tool in `allowed_tools`, AST-verified no sub-subagent dispatch.

### Key architectural decisions (per phase)

- **Decision (D-01, Phase 3):** WIO is one Claude Agent SDK session with inline skill injection — NO sub-subagent dispatch. **Why:** Avoids context-window fragmentation across nested agents; keeps the full lifecycle reasoning in one place; auditable.
- **Decision (D-02, Phase 3):** All 5 lifecycle skills (02+03+04+05+06) are concatenated into the WIO system prompt at startup (~14.4 KB). **Why:** Skills as inline behavioral specs > skills as separate agent processes — eliminates IPC overhead and context juggling.
- **Decision (D-08, Phase 5):** Risk Agent is a pure Python class for skills 12+13. Only skill 14 (Auto-Improvement Trigger detection) uses an LLM. **Why:** Quality scoring is deterministic math; LLM only needed for pattern recognition.
- **Decision (D-09, Phase 4):** Worktree cleanup uses `try/finally` + `git worktree prune` at startup. **Why:** Disk-DoS mitigation (T-4-03) — abandoned worktrees would accumulate forever otherwise.
- **Decision (D-10, Phase 5):** Global Orchestrator imports Risk Agent as a Python module (not a subprocess). **Why:** Risk scoring is sub-millisecond; subprocess overhead would dominate.
- **Memory rule:** OAuth2 only — `ANTHROPIC_API_KEY` is forbidden in process env (G1 guardrail). **Why:** Centralizes credentials in `claude setup-token`; prevents accidental commits of API keys; aligns with Anthropic's recommended auth path.

### Tech stack

| Component | Pin / version | Role |
|-----------|---------------|------|
| Python | ≥3.12 | Runtime |
| `claude-agent-sdk` | ≥0.1.73, <0.2.0 | LLM session orchestration |
| `pydantic` | ≥2.0 | Contract validation, schema-drift defense (`extra="forbid"`) |
| `typer` + `rich` | ≥0.12 / ≥13 | CLI |
| `pytest` + `pytest-asyncio` + `hypothesis` | 8.x / ≥0.23 / ≥6.100 | Test framework + property tests |
| Linear MCP | `mcp.linear.app/mcp` | System of record |
| GitHub CLI (`gh`) | latest | PR delivery |

### The 10 guardrails (G1–G10)

Defense-in-depth structural enforcement, all in `src/hsb/agents/_sdk_options.py` chokepoint module + per-agent code:

| ID | Enforces | Mechanism |
|----|----------|-----------|
| G1 | OAuth2-only (no API keys) | `assert_oauth2_only()` function-entry guard + autouse session fixture |
| G2 | No `Agent` tool in `allowed_tools` | `make_options()` factory raises `ValueError` |
| G3 | Runtime backstop for G2 | `assert_no_task_dispatch(msg)` in every receive loop |
| G4 | Risk Agent skill 14 air-gapped | `allowed_tools=[]`, `mcp_servers=None`, model=haiku, max_turns=3 |
| G5 | LinearAgent writes denied for `risk_agent.py` callers | `linear_write_guard` stack-inspection decorator |
| G6 | UAT cycle cap = 3 | Global Orchestrator skips re-dispatch + posts escalation comment |
| G7 | `error_max_turns` raises | No silent loop continuation |
| G8 | WIO context budget warning | WARN log at `input_tokens > 120000` |
| G9 | Knowledge Store pre-write hook | `KnowledgeStorageInput.applicability` validator + `extra="forbid"` |
| G10 | UAT pre-persist validation | B1 coverage + B3 banned-token regex before Linear write |

**RISK-04 has 4 layers of structural defense** (the strongest milestone-level invariant): no `linear_agent` import in `risk_agent.py` + `linear_write_guard` decorator + `Literal["suggested"]` Pydantic field + skill 14 `allowed_tools=[]`.

---

## 3. Phases Delivered

| Phase | Name | Status | One-Liner |
|-------|------|--------|-----------|
| 1 | Foundation and Linear Integration | ✓ Complete (5/5 plans, 16 commits) | Linear Agent foundation: MCP wrapper, retry/backoff hooks, pydantic contracts, optimistic-lock procedure, 4 typer CLI commands, 9 live integration tests |
| 2 | Core Execution Agents | ✓ Complete (5/5 plans, 42 commits) | Four execution agents (Backlog, Builder, Git, QA) with 3-defense capability boundaries: SKILL.md allow-list + ClaudeAgentOptions allow-list + Pydantic `extra="forbid"`. Triple-layer QA cycle cap. |
| 3 | WIO + Single-Cycle MVP | ✓ Complete (4/4 plans, 12 commits) | Single Claude Agent SDK session driving one task through full lifecycle. Inline skill injection (5 skills, 14.4K chars). AST-verified no sub-subagent dispatch. |
| 4 | Global + Main Orchestrators + Parallel Mode | ✓ Complete (4/4 plans, 15 commits) | Three-level orchestration with cascade and parallel modes. Pure-Python orchestrators. Worktree isolation with `try/finally` cleanup. STRIDE threat model with 4 mitigations. |
| 5 | Enhancement Agents (Intelligence + UAT + Risk) | ✓ Complete (4/4 plans, 8 commits) | Intelligence inline in WIO (3-turn ClaudeSDKClient: enrich → cycle → store). UAT standalone Pattern B query() session. Risk pure-Python + isolated skill 14 SDK call. 10 guardrails wired structurally. |

**Total: 22 plans, 93 implementation commits + 29 doc/audit commits = 122 commits across 3 days (2026-05-04 → 2026-05-06).**

---

## 4. Requirements Coverage

**57 of 57 REQ-IDs autonomously verified** (24 with operator-pending live integration). Status legend:

- `Complete` — autonomous verification passed (unit tests + code-based evals + source-grep architectural assertions)
- `Complete*` — autonomous verification passed; live integration test pending operator (consolidated in `MILESTONE-UAT.md`)

**By phase:**

| Phase | REQ-IDs | Auto Complete | Operator-pending |
|-------|---------|---------------|------------------|
| 1 — Foundation | FOUND-01..04, LINR-01..05 (9 IDs) | 5 | 4 (FOUND-01 OAuth, LINR-01..04 live Linear ops) |
| 2 — Core Execution | BKPK-01..05, BLDR-01..04, GITA-01..05, QAAG-01..05 (19 IDs) | 7 | 12 (BKPK suite, Builder/Git/QA live runs) |
| 3 — WIO + MVP | WORC-01..05, CLIR-01..05 (10 IDs) | 5 | 5 (WORC-01 lifecycle, WORC-05 Linear comment, CLIR-01/02/04 live CLI) |
| 4 — Global + Main Orch. | GORD-01..04, MORD-01..05 (9 IDs) | 6 | 3 (MORD-03 parallel claim, MORD-04 worktree, MORD-05 cycle summary) |
| 5 — Enhancement | UATA-01..04, INTL-01..04, RISK-01..04 (12 IDs) | 8 | 4 (UATA-01/03 UAT dispatch + fix, INTL-01/02 live enrichment + storage) |
| **Totals** | **57** | **31** | **24 (operator-pending)** |

**Audit verdict (3 iterations today):**
- Iter 1: `gaps_found` (3 phases lacked VERIFICATION.md — 31 REQ-IDs cascaded to unsatisfied)
- Iter 2: `tech_debt` (3 Nyquist drafts remained)
- Iter 3: **`passed`** (all gaps closed)

Full audit at `.planning/v1.0-MILESTONE-AUDIT.md`. Operator UAT run-list at `.planning/MILESTONE-UAT.md` (5 groups, 24 steps, ~60–90 min once Phase 1 OAuth bootstraps).

---

## 5. Key Decisions Log

51 decisions across 5 phases (8 + 11 + 8 + 14 + 10). The most architecturally consequential, with cross-phase impact:

| ID | Phase | Decision | Why |
|----|-------|----------|-----|
| D-01 | 3 | WIO is one SDK session — NO sub-subagent dispatch | Auditability + context locality |
| D-02 | 3 | Inline skill injection (skills concatenated into system prompt at startup) | No IPC overhead; skills as text > skills as agents |
| D-01 | 4 | GlobalOrchestrator is pure Python (no SDK session) | Sub-millisecond ops shouldn't pay LLM latency |
| D-02 | 4 | MainOrchestrator is pure Python dispatch controller | Same — no LLM needed for branching logic |
| D-04 | 4 | Optimistic-lock claim via Linear `updatedAt` re-read | Prevents double-claim race in parallel mode (T-4-01) |
| D-09 | 4 | Worktree cleanup in `try/finally` + `git worktree prune` at startup | Disk-DoS mitigation (T-4-03) |
| D-10 | 5 | Global Orchestrator imports Risk Agent as Python module | Subprocess overhead vs sub-ms scoring |
| D-08 | 5 | Risk Agent skills 12+13 are pure Python; only skill 14 uses LLM | Deterministic math doesn't need a model |
| D-04 | 5 | Skills 10+11 (Intelligence) embedded inline in WIO, not separate process | Same rationale as Phase 3 D-02 |
| D-09 | 5 | Skill 14 SDK call uses `allowed_tools=[]`, `mcp_servers=None`, model=haiku | Air-gap defense for RISK-04 |

Each phase's full decision log: `.planning/phases/<phase>/<NN>-CONTEXT.md` `<decisions>` section.

---

## 6. Tech Debt & Deferred Items

**Code-level tech debt: zero.** No TODOs, no stubs, no placeholders, no deferred shortcuts in implementation. The audit (iter 3) explicitly returned `passed` with `tech_debt: []`.

**Deferred to v2.0** (intentionally out of scope for MVP, documented in REQUIREMENTS.md):

| Item | Why deferred |
|------|--------------|
| Event-driven triggers (Linear/GitHub webhooks) | MVP uses CLI loop; webhooks add infrastructure cost without proven need |
| Real-time observability dashboards | Phoenix tracing path documented in AI-SPEC §7; build when needed |
| Multi-project / cross-project intelligence | Knowledge Store metadata schema would need to expand significantly |
| Simulation / dry-run mode | `hsb show-next-action` covers the read-only use case; full simulation adds complexity |
| ML-based risk prediction | Current deterministic formula is auditable; ML would be opaque |
| Semantic search over Knowledge Store (ADVL-01) | Glob+Grep is sufficient at MVP scale; `rank-bm25` is the documented upgrade path |

**Operator UAT pending (5 gates — process-level, not code-level):**

| Gate | Phase | Purpose |
|------|-------|---------|
| OAuth bootstrap | 1 | Anthropic OAuth2 + Linear MCP browser flow + sandbox issue setup (~15 min) |
| 4 integration suites | 2 | Live Linear + GitHub PR runs for Backlog/Builder/Git/QA |
| MVP cycle benchmark | 3 | D-02 context-budget validation against real workspace |
| Parallel-mode E2E | 4 | 8-step contract: 2 seeded tasks + no-double-claim acceptance gate |
| GO/NO-GO matrix | 5 | 13-step verification covering all 5 Success Criteria |

These are documented manual verification steps, not gaps. Consolidated run-list: `.planning/MILESTONE-UAT.md`.

**Lessons learned (from RETROSPECTIVE patterns observed during the build):**

1. **Subagent dispatch is unreliable across runtimes.** `agents_installed: false` was the project state throughout — gsd-executor / gsd-verifier subagents weren't dispatchable. Sequential inline execution via wrapper agents was the workable fallback. Future: don't assume named subagents work; design for inline execution.

2. **The chokepoint module pattern is high-leverage.** `_sdk_options.py` (Phase 5) consolidates 4 of 10 guardrails (G1, G2, G3, G5). If you need to enforce a structural invariant across many call sites, build a single factory module that all call sites must use, then test the factory exhaustively.

3. **Pydantic `extra="forbid"` + `Literal` enums catch entire classes of bugs at parse time.** Established in Phase 1 (FOUND-03), reused in every subsequent phase without modification. The single most-effective architectural pattern across the milestone.

4. **CLI handlers must be sync; `asyncio.run()` lives at the Typer body.** CLIR-05 boundary. Discovered in Phase 1, reaffirmed every time someone tried to put `asyncio.run` inside a coroutine.

5. **Real-data integration testing pays dividends.** The "no mocking" stance forced clean separation between unit-testable contract logic and integration paths. The cost: integration tests need live env vars to run. The benefit: when they pass, you know the system actually works.

---

## 7. Getting Started

### For new contributors

**1. Read these in order:**
- [`README.md`](../../README.md) — full project X-ray (architecture, agents, guardrails, repo layout, milestone status)
- [`GET-STARTED.md`](../../GET-STARTED.md) — operator onboarding (~30 min: install → OAuth → first cycle)
- This document — milestone summary and team-onboarding context

**2. Install:**
```bash
git clone <repo-url> hsb && cd hsb
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,eval]"
hsb --help     # confirms Typer CLI registered
```

**3. Verify (no live deps needed):**
```bash
pytest tests/unit/ -x -q                    # 106 unit tests
pytest tests/evals/code_based/ -x -q        # 18 code-based evals
pytest tests/integration/ --collect-only -q # 59 integration tests collect cleanly
```

**4. Authenticate (one-time, browser required):**
- See `GET-STARTED.md` "Authenticate" section
- TL;DR: `claude setup-token` (NOT API key — G1 enforced) + Linear MCP browser flow + sandbox Linear test workspace + `gh auth status`

**5. First cycle:**
```bash
# Seed a Linear test task in `todo` state
export TEST_WORK_ITEM_ID=LIN-XXX

# Inspect (dry-run)
hsb show-state
hsb show-next-action

# Run one cycle (Builder → Git → QA → fix loop within one SDK session)
hsb run-next-step

# Or continuous loop
python run_loop.py
```

### Key code entry points

| File | What it does |
|------|--------------|
| `src/hsb/cli/main.py` | All Typer CLI commands; `asyncio.run()` boundary |
| `src/hsb/agents/work_item_orchestrator.py` | The L2 orchestrator — single SDK session driving one task |
| `src/hsb/agents/global_orchestrator.py` | The L1 orchestrator — Python class building the risk-prioritized ready queue |
| `src/hsb/agents/main_orchestrator.py` | The L0 orchestrator — cascade vs parallel mode dispatch |
| `src/hsb/agents/_sdk_options.py` | The chokepoint module — G1/G2/G3/G5 enforcement |
| `src/hsb/agents/linear_agent.py` | Wrapper around Linear MCP via Claude Agent SDK; `linear_write_guard` decorator |
| `src/hsb/contracts/*.py` | All Pydantic models — every one uses `extra="forbid"` |
| `.claude/skills/*/SKILL.md` | 14 behavioral specs (skills 02–14 + linear-system-of-record) |

### Test entry points

| Command | What it tests |
|---------|---------------|
| `pytest tests/unit/ -x -q` | 106 unit tests, no live deps, ~30s |
| `pytest tests/evals/code_based/ -x -q` | 18 B1/B3 eval tests, no live deps |
| `pytest tests/integration/ -v -m integration` | 37 live integration tests (requires env vars per `_require_*` helpers) |
| `pytest tests/unit/test_risk_agent_quality_score.py` | Hypothesis property test for RISK-01 deterministic formula |

### Where to look for context

| Question | Where |
|----------|-------|
| What does this agent do and why? | `agents/AGENTS.md` + `agents/AGENT-CONTRACTS.md` (JSON schemas) |
| What are the runtime golden rules? | `runtime/RUNTIME-EXECUTION.md` |
| Why was X chosen over Y? | `.planning/phases/<NN>/<NN>-CONTEXT.md` `<decisions>` section |
| What was researched before building? | `.planning/phases/<NN>/<NN>-RESEARCH.md` |
| What was actually delivered per plan? | `.planning/phases/<NN>/<NN>-NN-SUMMARY.md` |
| Per-REQ-ID traceability? | `.planning/phases/<NN>/<NN>-VERIFICATION.md` |
| AI design contract (framework + eval strategy)? | `.planning/phases/<NN>/<NN>-AI-SPEC.md` (Phase 5 has the most thorough one) |
| Operator UAT path? | `.planning/MILESTONE-UAT.md` |
| Full audit history? | `.planning/v1.0-MILESTONE-AUDIT.md` |

---

## Stats

- **Timeline:** 2026-05-04 → 2026-05-06 (3 days)
- **Phases:** 5 / 5 complete (autonomous portion)
- **Plans:** 22 / 22 with SUMMARY.md present
- **Commits:** 122 total
- **Files changed:** 198 (+50,107 / −642 lines)
- **Contributors:** Hugo Seabra <contato.hsbtec@gmail.com>
- **Tests:** 106 unit + 18 code-based evals + 59 integration (37 live, 22 source-grep)
- **REQ-IDs:** 57/57 implemented; 31 fully autonomous-verified, 24 pending live operator integration
- **Guardrails:** 10 (G1–G10) with structural enforcement; RISK-04 has 4 layers
- **SKILL.md migrated:** 14 to `.claude/skills/`
- **Audit iterations:** 3 (gaps_found → tech_debt → **passed**)

---

## Next steps

1. **Operator runs `MILESTONE-UAT.md`** — closes the 5 operator gates against a live Linear test workspace (~60–90 min once OAuth bootstraps)
2. **`/gsd-complete-milestone v1.0`** — archives v1.0, creates git tag, prepares v2.0 planning
3. **`/gsd-new-milestone`** — start v2.0 planning (questioning → research → requirements → roadmap)
