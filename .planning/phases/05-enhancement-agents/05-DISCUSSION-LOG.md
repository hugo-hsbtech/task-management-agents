# Phase 5: Enhancement Agents - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 05-enhancement-agents
**Areas discussed:** UAT orchestration, Intelligence in WIO lifecycle, Risk Agent + Global Orchestrator wiring, Knowledge write criteria

---

## UAT Orchestration

### Who triggers the UAT Agent?

| Option | Description | Selected |
|--------|-------------|----------|
| Global Orchestrator detects it | Global Orchestrator reads full Linear state; Phase 5 adds User Story readiness detection to dispatch UAT Agent automatically | ✓ |
| Dedicated CLI command | Human runs `hsb run-uat LIN-200`; operator-triggered, keeps WIO/Global Orchestrator unchanged | |
| Main Orchestrator handles UAT dispatch | Main Orchestrator extended to detect User Stories with all tasks QA-approved | |

**User's choice:** Global Orchestrator detects it (recommended)
**Notes:** Automatic detection consistent with GORD-01–04 pattern; avoids new CLI command

---

### When UAT creates fix subtasks, who drives the fix loop?

| Option | Description | Selected |
|--------|-------------|----------|
| WIO handles them as normal tasks | UAT fix subtasks are Task-type Linear items handled by standard WIO lifecycle; Global Orchestrator re-triggers UAT after fixes pass QA | ✓ |
| UAT Agent owns its own fix loop | UAT Agent creates fix subtasks AND monitors through resolution | |

**User's choice:** WIO handles them as normal tasks (recommended)
**Notes:** Reuses existing lifecycle infrastructure; no special UAT fix logic needed

---

### How is the UAT Agent invoked?

| Option | Description | Selected |
|--------|-------------|----------|
| Claude Agent SDK session | UAT requires semantic reasoning; skill 08 embedded inline in system prompt | ✓ |
| Pure Python | Deterministic scripting — cannot perform semantic UAT evaluation meaningfully | |

**User's choice:** Claude Agent SDK session (recommended)

---

## Intelligence in WIO Lifecycle

### How does the Intelligence Agent fit into the WIO lifecycle?

| Option | Description | Selected |
|--------|-------------|----------|
| Embed skills 10+11 inline into WIO prompt | Consistent with WORC-02; extends WIO system prompt injection; same SDK session | ✓ |
| Separate SDK session called before WIO starts | Separate subprocess; passes enrichment report as `knowledge_context`; cleaner WIO context but adds subprocess coordination | |
| WIO calls Intelligence as a @tool | Intelligence exposed as @tool inside WIO session; changes WIO's tool surface | |

**User's choice:** Embed skills 10+11 inline into WIO prompt (recommended)

---

### Where does Intelligence enrichment output go?

| Option | Description | Selected |
|--------|-------------|----------|
| Passed to Builder as knowledge_context | Implementation contract §4 already has this field; no contract changes | ✓ |
| Posted as a Linear comment only | Looser coupling; adds Linear roundtrip | |

**User's choice:** Passed to Builder as knowledge_context (recommended)

---

### Who triggers Knowledge Store writes after QA?

| Option | Description | Selected |
|--------|-------------|----------|
| WIO handles it inline after QA result | WIO adds Knowledge Storage step after QA in same SDK session; no post-cycle subprocess | ✓ |
| Post-cycle Intelligence Agent run | Separate Intelligence Agent session after WIO completes | |

**User's choice:** WIO handles it inline after QA result (recommended)

---

## Risk Agent + Global Orchestrator Wiring

### How does Phase 5 wire Risk Agent into Global Orchestrator?

| Option | Description | Selected |
|--------|-------------|----------|
| Global Orchestrator calls Risk Agent as Python import | `risk_agent.get_priority_queue()` called after building ready-task list; minimal change | ✓ |
| Risk Agent pre-computes and caches in knowledge/ | Periodic pre-computation; stale-cache risk | |
| Risk Agent as optional Global Orchestrator step | Feature flag / config; conditional branching | |

**User's choice:** Global Orchestrator calls Risk Agent as Python import (recommended)

---

### Does Risk Agent need LLM reasoning?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure Python for scoring/prioritization, LLM only for improvement triggers | Skills 12+13 are deterministic math; skill 14 needs LLM for pattern detection and work item generation | ✓ |
| Full Claude Agent SDK session | Adds LLM cost to every orchestration cycle for deterministic operations | |

**User's choice:** Pure Python + LLM only for improvement triggers (recommended)

---

## Knowledge Write Criteria

### What triggers a new Knowledge Store write from a QA finding?

| Option | Description | Selected |
|--------|-------------|----------|
| LLM judgment call — WIO decides | WIO's Intelligence step evaluates findings using skill 11 ingestion criteria; most accurate signal | ✓ |
| Only repeated findings (same category + module) | Deterministic grep-based check; misses novel architectural decisions | |
| Every QA finding with severity high or critical | Severity-gated; simple rule; may produce noise from one-off bugs | |

**User's choice:** LLM judgment call — WIO decides (recommended)

---

### What triggers a Knowledge Store write from a successful implementation?

| Option | Description | Selected |
|--------|-------------|----------|
| WIO decides (LLM judgment) — same as QA path | After clean QA approval, WIO evaluates implementation notes for reusable patterns | ✓ |
| Never — only QA findings trigger writes | Simpler; misses patterns from well-executed tasks | |

**User's choice:** WIO decides (LLM judgment) — same as QA path (recommended)

---

## Claude's Discretion

- SKILL.md migration scope for skills 08, 10, 11, 12, 13, 14 — follow per-skill pattern from Phases 1–4
- Risk Agent quality score aggregation details (weighted vs simple average, default neutral score)
- Knowledge Store entry deduplication before writes
- UAT Agent dispatch mechanism (subprocess vs inline in Global Orchestrator)

## Deferred Ideas

- Semantic search / vector retrieval for Knowledge Store — v2 (ADVL-01)
- ML-based risk scoring — v2 (ADVL-03)
- Observability/Reporting Agent (skill 09) — not in Phase 5 requirements
- Auto-Improvement Triggers automatic Linear creation — deferred; RISK-04 requires explicit delegation
