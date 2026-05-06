# Phase 5: Enhancement Agents - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 adds three enhancement agents on top of the validated Phase 1–4 delivery loop:

- **Intelligence Agent** — enriches work items before Builder execution by querying the Knowledge Store, then persists reusable knowledge after QA review. Implemented by embedding skills 10+11 inline into the WIO system prompt.
- **UAT Agent** — validates User Stories from a user-acceptance perspective after all related task PRs are QA-approved. Triggered automatically by Global Orchestrator. Claude Agent SDK session with skill 08 embedded inline.
- **Risk Agent** — scores work items for quality and risk using deterministic Python math (skills 12+13), produces a priority queue consumed by Global Orchestrator, and uses LLM reasoning only for Auto-Improvement Trigger detection (skill 14).

No changes to Phase 1–3 infrastructure. Phase 4 Global Orchestrator gains one new capability: UAT-readiness detection and Risk Agent import.

</domain>

<decisions>
## Implementation Decisions

### UAT Agent — Orchestration

- **D-01:** Global Orchestrator detects User Stories with all child tasks QA-approved and dispatches the UAT Agent automatically — no new CLI command. Phase 5 extends Global Orchestrator with User Story readiness detection alongside the existing EPIC readiness detection (GORD-04 pattern).
- **D-02:** UAT fix subtasks are standard Task-type Linear items. WIO drives them through the normal lifecycle (Builder → Git → QA). After the fix tasks reach QA-approved, Global Orchestrator re-triggers UAT on the parent User Story. No special UAT fix loop logic.
- **D-03:** UAT Agent is a Claude Agent SDK session. Skill 08 content (`skills/08-UAT-VALIDATION.md`) is embedded inline in the system prompt — same injection pattern established in Phase 3 for WIO. No sub-subagent dispatch.

### Intelligence Agent — WIO Integration

- **D-04:** Skills 10+11 (`skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md` + `skills/11-KNOWLEDGE-STORAGE.md`) are embedded inline into the WIO system prompt, extending the existing skill injection set (skills 02+03+04+05+06). This is consistent with WORC-02 (no sub-subagent dispatch). Phase 3's context budget benchmark validates that inline injection is safe; if skill 10+11 push context limits, the planner should consider a skill index approach (brief summaries with on-demand full reads) as noted in Phase 3 specifics.
- **D-05:** Intelligence enrichment output is passed to Builder via the existing `knowledge_context` field in the Implementation contract (AGENT-CONTRACTS.md §4). No contract changes needed.
- **D-06:** After QA result (approved or changes_required), the WIO's Intelligence step evaluates the findings and implementation notes and writes Knowledge Store entries inline — no post-cycle subprocess. Stays within the single Agent SDK session.

### Intelligence Agent — Knowledge Write Criteria

- **D-07:** Knowledge Store writes are LLM judgment calls. The WIO's Intelligence step evaluates both QA findings and clean-pass implementation notes using the ingestion criteria from `skills/11-KNOWLEDGE-STORAGE.md` (recurring finding, architectural drift, reusable workaround, decision that should influence future work). Both paths use the same judgment mechanism — there is no severity gate or repeat-count threshold.

### Risk Agent — Architecture

- **D-08:** Risk Agent is implemented as a pure Python class (`src/hsb/agents/risk_agent.py`) for skills 12+13 — quality scoring and adaptive prioritization are deterministic math (subtract-penalty formula, sort by score). No LLM session for these operations.
- **D-09:** Auto-Improvement Trigger detection (skill 14) requires LLM reasoning to identify patterns and generate suggested work item descriptions. This is implemented as a separate Claude Agent SDK invocation within `risk_agent.py` — called only when triggered explicitly (RISK-04: Risk Agent does not create Linear work items without explicit delegation through the Linear Agent).
- **D-10:** Global Orchestrator calls Risk Agent as a Python import. Phase 5 adds one new step to Global Orchestrator: after building the ready-task list, call `risk_agent.get_priority_queue(ready_tasks, linear_state)` and use the returned sorted list. Minimal change to Phase 4's Global Orchestrator.

### Claude's Discretion

- **SKILL.md migration scope**: Skills 08, 10, 11, 12, 13, 14 — whether each skill becomes its own SKILL.md file (per-skill pattern from Phases 1–4) or agent-level SKILL.md files that combine multi-skill agents — Claude decides, following the established per-skill pattern.
- **Risk Agent Quality Score aggregation**: Exact implementation of EPIC score = weighted average of Tasks (vs. simple average) and the default neutral score for tasks without QA/UAT history — Claude decides following `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` aggregation rules.
- **Knowledge Store entry deduplication**: Whether to grep existing entries before writing a new one (to avoid exact duplicates) — Claude decides. The ingestion rules in skill 11 guide this.
- **UAT Agent dispatch mechanism**: Whether Global Orchestrator dispatches the UAT Agent as a subprocess (like WIOs in parallel mode) or inline — Claude decides based on what keeps the architecture consistent.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 Skill Specs (behavior source of truth)
- `skills/08-UAT-VALIDATION.md` — UAT Agent behavioral spec; embed as SKILL.md at `.claude/skills/uat-validation/SKILL.md`
- `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md` — Intelligence Agent enrichment skill; embed as SKILL.md at `.claude/skills/knowledge-context-enrichment/SKILL.md`
- `skills/11-KNOWLEDGE-STORAGE.md` — Intelligence Agent storage skill; embed as SKILL.md at `.claude/skills/knowledge-storage/SKILL.md`; defines ingestion criteria and Knowledge Store entry format
- `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` — Risk Agent scoring skill; embed as SKILL.md at `.claude/skills/quality-scoring-risk-analysis/SKILL.md`
- `skills/13-ADAPTIVE-PRIORITIZATION.md` — Risk Agent prioritization skill; embed as SKILL.md at `.claude/skills/adaptive-prioritization/SKILL.md`
- `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md` — Risk Agent improvement triggers skill; embed as SKILL.md at `.claude/skills/auto-improvement-triggers/SKILL.md`

### Agent Contracts and Architecture
- `agents/AGENT-CONTRACTS.md` — JSON schemas for all agent contracts; Phase 5 agents: UAT (§7), Knowledge Enrichment (§9), Knowledge Storage (§10), Quality Scoring (§11), Adaptive Prioritization (§12), Auto-Improvement Triggers (§13)
- `agents/AGENTS.md` — agent responsibilities and capability boundaries; Agent Mapping table confirms Intelligence Agent = skills 10+11, Risk Agent = skills 12+13+14
- `runtime/RUNTIME-EXECUTION.md` — runtime execution model; "no sub-subagent dispatch" and "one action per WIO cycle" golden rules still apply in Phase 5

### Prior Phase Context (Phase 5 depends on these being built)
- `.planning/phases/01-foundation-and-linear-integration/01-CONTEXT.md` — Python layout, OAuth2, Linear Agent service interface, Knowledge Store directory structure (FOUND-04)
- `.planning/phases/02-core-execution-agents/02-CONTEXT.md` — integration test strategy (real external services, no mocking), QA cycle cap
- `.planning/phases/03-work-item-orchestrator-and-single-cycle-mvp/03-CONTEXT.md` — WIO inline skill injection architecture (D-01), Intelligence deferred to Phase 5 (D-03), context budget benchmark note in specifics
- `.planning/phases/04-global-main-orchestrators-and-parallel-mode/04-CONTEXT.md` — Global Orchestrator pure Python class, Phase 5 extends it with UAT detection + Risk Agent import

### Critical Failure Mode References
- `.planning/research/PITFALLS.md` — critical failure modes; Pitfall 2 (QA runaway) and Pitfall 4 (stale state) are relevant for UAT fix loop; Pitfall 5 (context exhaustion) is relevant for Intelligence skill injection
- `.planning/research/STACK.md` — exact tool names, library versions, SDK patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from prior phases)
- `skills/08-UAT-VALIDATION.md`, `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md`, `skills/11-KNOWLEDGE-STORAGE.md`, `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md`, `skills/13-ADAPTIVE-PRIORITIZATION.md`, `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md` — all behavioral specs are migration-ready; add YAML frontmatter and commit to `.claude/skills/<name>/SKILL.md`
- `src/hsb/agents/global_orchestrator.py` (Phase 4) — Phase 5 adds UAT-readiness detection and a `risk_agent.get_priority_queue()` call; the Pure Python class pattern is unchanged
- `src/hsb/agents/work_item_orchestrator.py` (Phase 3) — Phase 5 extends the skill injection set (add skills 10+11) and adds Intelligence step before Builder and after QA in the lifecycle
- `src/hsb/agents/linear_agent.py` (Phase 1) — UAT Agent calls this for all Linear writes (persist UAT status, create fix subtasks); Risk Agent calls it if Auto-Improvement Triggers are approved for Linear persistence
- `knowledge/` directory (Phase 1 FOUND-04) — already structured with category subdirectories; Phase 5 Intelligence Agent writes into these

### Established Patterns (from Phases 1–4)
- Python package layout: `src/hsb/agents/` — Phase 5 adds `intelligence_agent.py`, `uat_agent.py`, `risk_agent.py`; `src/hsb/contracts/` adds corresponding pydantic models
- SKILL.md migration: add YAML frontmatter (`name`, `description`, `allowed-tools`) to existing skill content, commit to `.claude/skills/<name>/SKILL.md`
- Integration tests use real Linear test workspace and real `hsb-test-fixture` GitHub repo — no mocking
- OAuth2 only — all Linear integration through `mcp-remote` OAuth2 flow; no API keys anywhere

### Integration Points
- Global Orchestrator imports Risk Agent (`from hsb.agents.risk_agent import RiskAgent`) — adds priority scoring before returning ready-task list
- Global Orchestrator adds User Story readiness check: query Linear for User Stories whose child tasks are all `qa_status = approved` → dispatch UAT Agent
- WIO system prompt injection adds skills 10+11 content; WIO lifecycle gains two new steps: Intelligence (before Builder) and Knowledge Storage evaluation (after QA)
- Risk Agent's LLM invocation (skill 14 only) uses Claude Agent SDK — same SDK import as WIO

</code_context>

<specifics>
## Specific Ideas

- The Implementation contract (AGENT-CONTRACTS.md §4) already has a `knowledge_context: {}` field — no schema change needed for the Intelligence → Builder handoff. Phase 5 simply populates this field.
- The WIO context budget was validated in Phase 3's MVP benchmark. Skills 10+11 add ~7KB to the injection. If context pressure appears, the Phase 3 "skill index" fallback applies: inject brief summaries of skills 10+11 and have the WIO read the full content on demand.
- Risk Agent quality score formula is deterministic: start from 100, subtract -10 per QA failure, -5 per fix subtask, -15 if UAT failed, -5 per rework cycle. Minimum = 0. Source: `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md`.
- UAT re-trigger: after UAT fix subtasks complete QA-approval, Global Orchestrator re-detects the User Story as UAT-ready (same detection logic, new cycle). No special state flag needed — the check is stateless from Global Orchestrator's perspective.

</specifics>

<deferred>
## Deferred Ideas

- Semantic search over Knowledge Store (REQUIREMENTS.md ADVL-01) — v2 scope; Phase 5 uses Glob+Grep for retrieval (INTL-01 baseline)
- ML-based risk scoring (REQUIREMENTS.md ADVL-03) — v2 scope; Phase 5 uses the deterministic formula
- Multi-project knowledge sharing (REQUIREMENTS.md MLTI-02) — v2 scope
- Observability/Reporting Agent (skill 09) — not in Phase 5 requirements; deferred to future milestone
- Auto-Improvement Triggers creating Linear work items automatically — RISK-04 explicitly states no creation without explicit delegation; the delegation mechanism beyond the Linear Agent write call is deferred to a future CLI extension

</deferred>

---

*Phase: 05-enhancement-agents*
*Context gathered: 2026-05-06*
