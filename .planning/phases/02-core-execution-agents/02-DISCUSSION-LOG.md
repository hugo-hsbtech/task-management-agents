# Phase 2: Core Execution Agents - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 02-core-execution-agents
**Areas discussed:** plan.md input format, QA Agent Linear scope, gh stack vs manual stacking, Standalone test strategy

---

## plan.md Input Format

| Option | Description | Selected |
|--------|-------------|----------|
| Free-form markdown | Agent reads any markdown, LLM extracts structure | ✓ |
| Required template with headings | Specific heading format enforced | |
| Semi-structured: sections expected | Top-level sections expected, not enforced | |

**User's choice:** Free-form markdown

---

| Option | Description | Selected |
|--------|-------------|----------|
| User-specified path at runtime | `--plan <path>` argument | ✓ |
| Convention: /docs/plan.md always | Fixed path, no argument | |
| Either: path arg or fallback | Optional arg + fallback | |

**User's choice:** User-specified path at runtime (`--plan <path>`)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Section quote in Linear description | Relevant excerpt from plan.md embedded in issue | ✓ |
| Section heading reference | Pointer like `Plan source: §'Auth'` | |
| You decide | Claude picks traceability mechanism | |

**User's choice:** Section quote in Linear description

---

## QA Agent Linear Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full capability: QA writes to Linear | QA Agent calls Linear Agent internally in Phase 2 | ✓ |
| Contract-only: QA outputs, Phase 3 writes | Findings contract only; orchestrator persists | |
| Hybrid: QA writes cycle count, not subtasks | Partial coupling | |

**User's choice:** Full capability — QA writes to Linear in Phase 2

---

| Option | Description | Selected |
|--------|-------------|----------|
| Inside QA Agent SKILL.md | LLM reads cycle count from input, switches behavior | ✓ |
| Python wrapper enforces it | Python checks count before invoking QA session | |
| You decide | Claude decides | |

**User's choice:** Cycle-cap logic lives in QA Agent SKILL.md

---

## gh stack vs Manual Stacking

| Option | Description | Selected |
|--------|-------------|----------|
| Manual-only with gh CLI | No gh stack, plain `gh pr create --base` and manual rebase cascade | ✓ |
| Try gh stack, fallback to manual | Attempt private preview extension, fall back if unavailable | |
| Defer cascade to Phase 3 | GITA-04 deferred until orchestrator exists | |

**User's choice:** Manual-only — no `gh stack` dependency ever

---

| Option | Description | Selected |
|--------|-------------|----------|
| Always target EPIC branch | All task PRs use EPIC branch as base | ✓ |
| Read Linear dependencies to chain PRs | Check dependencies, chain PR bases accordingly | |
| You decide | Claude picks | |

**User's choice:** Always target EPIC branch (no chained task-to-task PR bases)

---

## Standalone Test Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Integration tests against real services | Real Linear workspace + real GitHub repo | ✓ |
| Unit tests with mocked external calls | Mock Linear MCP and gh CLI | |
| Layered: unit for contracts, integration for agents | Both approaches | |

**User's choice:** Integration tests against real services (+ unit tests for pydantic contracts)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Real GitHub repo, test branch | Dedicated `hsb-test-fixture` repo | ✓ |
| Local temp dir, git init per run | In-process fixture, no GitHub needed for Builder | |
| You decide | Claude picks | |

**User's choice:** Dedicated real GitHub repo (`hsb-test-fixture`) on a test branch

---

## Claude's Discretion

- SKILL.md migration for all 4 Phase 2 agents
- `qa_cycle_count` read source (from input contract vs live Linear fetch)
- Test fixture repo structure and cleanup strategy
- Builder validation auto-detection heuristic

## Deferred Ideas

- `gh stack` integration — never (unstable private preview)
- Chained task-to-task PR bases — deferred indefinitely; all tasks target EPIC branch
- Simulation/dry-run mode — out of scope per REQUIREMENTS.md
