# Phase 5: Enhancement Agents — Research

**Researched:** 2026-05-06
**Domain:** Multi-agent enhancement layer (Intelligence inline / UAT standalone / Risk pure-Python) on top of validated Phase 1–4 delivery loop
**Confidence:** HIGH — all critical patterns are locked by prior-phase decisions and documented in AI-SPEC; the open questions are scoped to implementation integration details that are deterministic once the attachment points are identified.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**UAT Agent — Orchestration**
- D-01: Global Orchestrator detects User Stories with all child tasks QA-approved and dispatches the UAT Agent automatically — no new CLI command. Phase 5 extends Global Orchestrator with User Story readiness detection alongside the existing EPIC readiness detection (GORD-04 pattern).
- D-02: UAT fix subtasks are standard Task-type Linear items. WIO drives them through the normal lifecycle (Builder → Git → QA). After fix tasks reach QA-approved, Global Orchestrator re-triggers UAT on the parent User Story. No special UAT fix loop logic.
- D-03: UAT Agent is a Claude Agent SDK session. Skill 08 content (`skills/08-UAT-VALIDATION.md`) is embedded inline in the system prompt — same injection pattern established in Phase 3 for WIO. No sub-subagent dispatch.

**Intelligence Agent — WIO Integration**
- D-04: Skills 10+11 are embedded inline into the WIO system prompt, extending the existing skill injection set (skills 02+03+04+05+06). Consistent with WORC-02 (no sub-subagent dispatch). Phase 3's context budget benchmark validates that inline injection is safe; if skill 10+11 push context limits, the skill index approach applies (brief summaries with on-demand full reads).
- D-05: Intelligence enrichment output is passed to Builder via the existing `knowledge_context` field in the Implementation contract (AGENT-CONTRACTS.md §4). No contract changes needed.
- D-06: After QA result (approved or changes_required), the WIO's Intelligence step evaluates findings and implementation notes and writes Knowledge Store entries inline — no post-cycle subprocess. Stays within the single Agent SDK session.

**Intelligence Agent — Knowledge Write Criteria**
- D-07: Knowledge Store writes are LLM judgment calls. The WIO's Intelligence step evaluates both QA findings and clean-pass implementation notes using the ingestion criteria from `skills/11-KNOWLEDGE-STORAGE.md`. Both paths use the same judgment mechanism — no severity gate or repeat-count threshold.

**Risk Agent — Architecture**
- D-08: Risk Agent is a pure Python class (`src/hsb/agents/risk_agent.py`) for skills 12+13. No LLM session for quality scoring or adaptive prioritization.
- D-09: Auto-Improvement Trigger detection (skill 14) uses a separate Claude Agent SDK invocation within `risk_agent.py` — called only when triggered explicitly. RISK-04: Risk Agent does not create Linear work items without explicit delegation through the Linear Agent.
- D-10: Global Orchestrator calls Risk Agent as a Python import. Phase 5 adds one new step to Global Orchestrator: after building the ready-task list, call `risk_agent.get_priority_queue(ready_tasks, linear_state)` and use the returned sorted list.

### Claude's Discretion

- **SKILL.md migration scope**: Skills 08, 10, 11, 12, 13, 14 — whether each skill becomes its own SKILL.md file (per-skill pattern) or agent-level combined files — Claude decides following the established per-skill pattern.
- **Risk Agent Quality Score aggregation**: EPIC score = weighted average of Tasks vs. simple average; default neutral score for tasks without QA/UAT history — Claude decides following `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` aggregation rules.
- **Knowledge Store entry deduplication**: Whether to grep existing entries before writing a new one (to avoid exact duplicates) — Claude decides. The ingestion rules in skill 11 guide this.
- **UAT Agent dispatch mechanism**: Whether Global Orchestrator dispatches the UAT Agent as a subprocess (like WIOs in parallel mode) or inline — Claude decides based on what keeps the architecture consistent.

### Deferred Ideas (OUT OF SCOPE)

- Semantic search over Knowledge Store (ADVL-01) — v2 scope; Phase 5 uses Glob+Grep
- ML-based risk scoring (ADVL-03) — v2 scope; Phase 5 uses deterministic formula
- Multi-project knowledge sharing (MLTI-02) — v2 scope
- Observability/Reporting Agent (skill 09) — not in Phase 5 requirements
- Auto-Improvement Triggers creating Linear work items automatically — RISK-04 forbids; delegation mechanism beyond Linear Agent write call deferred to future CLI extension
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UATA-01 | UAT Agent validates a User Story from user-acceptance perspective after all related task PRs are QA-approved | Global Orchestrator query: User Stories where all child task `qa_status == approved` AND `uat_status != approved`; dispatch `uat_agent.py` via `await run_uat_and_validate(...)` |
| UATA-02 | UAT Agent produces UAT scenarios derived from acceptance criteria with expected vs actual behavior and pass/fail per scenario | `UATResult.scenarios: list[UATScenario]` — each scenario has `criterion_id`, `status`, `evidence`, `finding`; pydantic-validated before persistence |
| UATA-03 | UAT Agent creates UAT fix subtasks via the Linear Agent when UAT status is `changes_required` | Global Orchestrator inspects `UATResult.overall_status == "changes_required"` and calls `linear_agent.create_subtasks(findings)` using the contract from AGENT-CONTRACTS.md §7 |
| UATA-04 | UAT Agent operates only on User Story scope — does not review low-level code or create PRs | Enforced by: `allowed_tools=["Read","Glob","Grep","Bash"]` (no Write/Edit), no MCP write tools in skill 08, explicit `SCOPE BOUNDARY` constraint in every UAT prompt |
| INTL-01 | Intelligence Agent retrieves relevant knowledge entries from the Knowledge Store (Glob+Grep) before Builder execution | WIO Step 1 ("Enrich"): `await client.query("Enrich work item … from the Knowledge Store")` — skill 10 in system prompt guides Glob+Grep retrieval; result captured as `knowledge_context` |
| INTL-02 | Intelligence Agent persists a new knowledge entry when a QA finding, implementation pattern, or architectural decision meets minimum-evidence criteria | WIO Step 5 ("Store"): `await client.query("Evaluate QA findings and implementation notes. Apply skill 11 ingestion criteria. Write Knowledge Store entries only for insights that meet the signal threshold.")` |
| INTL-03 | Every knowledge entry written includes: title, type, context, evidence (Linear issue + PR + files), insight, recommendation, applicability, date | `KnowledgeStorageInput` pydantic model with all 8 required fields; post-write schema validation hook checks `evidence.linear_issue` matches `LIN-\d+` and `evidence.pr` matches GitHub PR URL pattern |
| INTL-04 | Intelligence Agent does not mutate Linear operational state directly | Enforced by WIO session design: Intelligence steps use `Read`, `Glob`, `Grep`, `Write` (for knowledge/ only); WIO passes enrichment report to Builder via `knowledge_context` field, never calling Linear MCP directly from Intelligence steps |
| RISK-01 | Risk Agent calculates a quality score and risk level (`low`/`medium`/`high`) for each work item | `RiskAgent.calculate_quality_score(work_item, qa_history, uat_results)` — deterministic Python math: start=100, -10/QA failure, -5/fix subtask, -15 if UAT failed, -5/rework cycle, min=0; risk level derived from score thresholds |
| RISK-02 | Risk Agent produces a prioritized work item queue with score and reason for each item | `RiskAgent.get_priority_queue(ready_tasks, linear_state) -> PriorityQueue` — sort by score descending, tiebreak by `updatedAt` ascending; returns `PriorityQueue(items=[...], scores={...})` |
| RISK-03 | Risk Agent detects repeated QA failure patterns and produces improvement trigger suggestions with suggested Linear work items | `RiskAgent.detect_improvement_triggers(qa_history, scores) -> list[AutoImprovementTrigger]` — calls `detect_auto_improvement_triggers(risk_summary)` via Haiku SDK for pattern reasoning; pattern_evidence requires ≥ 2 supporting refs |
| RISK-04 | Risk Agent does not execute improvements or create Linear work items without explicit delegation through the Linear Agent | Structural guarantee: skill 14 SDK call has `allowed_tools=[]`, no `mcp_servers` — the function literally cannot write to Linear. Global Orchestrator surfaces triggers as suggestions; human approves via CLI before Linear Agent is called |
</phase_requirements>

---

## Summary

Phase 5 adds three enhancement agent surfaces to the validated Phase 1–4 delivery loop. Unlike the new processes introduced in earlier phases, Phase 5 is primarily about **extending existing code rather than creating new standalone services**. Two of the three sub-systems (Intelligence inline in WIO, Risk Agent) are Python-only with a single isolated LLM call. Only the UAT Agent is a new Claude Agent SDK session.

The critical integration question for planning is: **where exactly in the existing files do Phase 5 changes attach?** The answer maps cleanly: `work_item_orchestrator.py` gains two new steps and extended skill injection; `global_orchestrator.py` gains a UAT-readiness check, a `risk_agent.get_priority_queue()` call, and UAT-trigger dispatch; three new source files are created (`uat_agent.py`, `risk_agent.py`, `intelligence_agent.py`); three new contract files are created (`src/hsb/contracts/uat.py`, `src/hsb/contracts/risk.py`, `src/hsb/contracts/knowledge.py`); and six new SKILL.md files are migrated to `.claude/skills/`.

The most complex integration decision is the **UAT Agent dispatch mechanism** (Claude's Discretion item). The recommendation below (§ Open Implementation Choices) is to dispatch UAT Agent **inline** (not subprocess) because it runs from within the Global Orchestrator's event loop — not from within a WIO subprocess — and the Global Orchestrator is a pure Python class with no parallelism requirements at the UAT trigger point.

**Primary recommendation:** Decompose into four plans — (1) Intelligence inline WIO extension, (2) UAT Agent new standalone session + Global Orchestrator UAT detection, (3) Risk Agent pure Python class + skill 14 LLM call, (4) Global Orchestrator Risk integration (priority queue insertion). Plans 1 and 3 are independent. Plans 2 and 4 depend on Plan 1 being validated first (Global Orchestrator must know Risk Agent's interface before it can call it). Plan 2 depends on Phase 4 Global Orchestrator being stable.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Knowledge Store retrieval before Builder | WIO (Agent SDK session, inline) | — | Skill 10 is injected into the existing WIO system prompt; retrieval uses the WIO's existing `Glob`/`Grep` tools; no new agent process |
| Knowledge Store write after QA | WIO (Agent SDK session, inline) | — | Skill 11 is injected into WIO; WIO writes markdown files to `knowledge/` using its existing `Write` tool; Linear state not touched |
| UAT validation of User Story | UAT Agent (new standalone SDK session) | Linear Agent (writes UAT status) | UAT Agent reads from Linear and file system; all Linear writes go through Linear Agent after UAT Agent returns UATResult |
| UAT readiness detection | Global Orchestrator (pure Python) | Linear Agent (reads state) | Pure state inspection: query Linear for User Stories with all child tasks `qa_status == approved`; deterministic filter, no LLM |
| UAT fix subtask creation | Linear Agent (Phase 1) | — | UAT Agent returns `UATResult`; Global Orchestrator passes findings to Linear Agent for subtask creation; UAT Agent never writes to Linear directly |
| Quality scoring (skills 12+13) | Risk Agent (pure Python class) | — | Deterministic math; no LLM; runs at Global Orchestrator dispatch time |
| Priority queue production | Risk Agent (pure Python class) | Global Orchestrator (consumes queue) | Sorted list returned by `RiskAgent.get_priority_queue()`; Global Orchestrator replaces its previous unsorted ready-tasks list with this |
| Auto-improvement trigger detection (skill 14) | Risk Agent (isolated Haiku SDK call) | Global Orchestrator (surfaces suggestions) | One-shot `query()` call with `allowed_tools=[]` and no `mcp_servers`; cannot write to Linear; returns suggestions to caller |
| Knowledge Store directory | Filesystem (git-tracked) | — | Already exists at `knowledge/` with category subdirs per FOUND-04; Phase 5 writes into these directories; no new infrastructure |

---

## Phase Boundary & Code Attachment Points

### Files Modified (extending Phase 1–4 code)

#### `src/hsb/agents/work_item_orchestrator.py` (Phase 3)

**What changes:**
1. `system_prompt` assembly gains two additional skill injections:
   ```python
   load_skill(".claude/skills/knowledge-context-enrichment/SKILL.md"),  # skill 10
   load_skill(".claude/skills/knowledge-storage/SKILL.md"),             # skill 11
   ```
2. The lifecycle sequence gains two new `client.query()` steps:
   - **Step 1 (new):** Intelligence enrichment — before the Builder step, query the WIO session to retrieve Knowledge Store context and populate `knowledge_context`.
   - **Step 5 (new):** Knowledge storage evaluation — after the QA result, query the WIO session to evaluate whether the cycle produced knowledge-worthy insights and write entries to `knowledge/`.
3. The `knowledge_context` value from Step 1 is injected into the Builder prompt (no contract schema change — the field already exists in AGENT-CONTRACTS.md §4).

**Function signatures affected:**
- `run_work_item_orchestrator(work_item_id: str, work_item_json: str) -> str` — unchanged signature; internal step additions only.
- `_assemble_system_prompt() -> str` — new helper (or inline expansion) to concatenate all 7 skill files.

**Context budget impact:** Skills 10+11 add ~7KB (~1,750 tokens) to the system prompt. System prompt total remains ~6,250 tokens (~3% of 200K window). Safe per AI-SPEC §4b.4.

#### `src/hsb/agents/global_orchestrator.py` (Phase 4)

**What changes:**
1. **Import:** `from hsb.agents.risk_agent import RiskAgent` at module top.
2. **UAT-readiness detection** — new method `_detect_uat_ready_user_stories(linear_state) -> list[str]`:
   - Query Linear for User Stories where all child tasks have `qa_status == approved` AND `uat_status` is not `approved` or `changes_required` (i.e., `pending` or `not_required` where UAT is applicable).
   - This mirrors the GORD-04 EPIC-readiness check pattern.
3. **Risk queue insertion** — after building `ready_tasks` from the existing dependency filter:
   ```python
   priority_queue = risk_agent.get_priority_queue(ready_tasks, linear_state)
   ready_tasks = priority_queue.items  # Replace unsorted list with risk-sorted list
   ```
4. **UAT dispatch** — after the ready-tasks list is built, for each UAT-ready User Story: `await run_uat_and_validate(user_story_id, acceptance_criteria, uat_cycle)`.
5. **Output contract** — the existing `GlobalOrchestratorOutput` pydantic model in `src/hsb/contracts/global_orchestrator.py` gains two new optional fields:
   - `uat_dispatched: list[str]` — User Story IDs that triggered UAT this cycle.
   - `improvement_triggers: list[AutoImprovementTrigger]` — from Risk Agent skill 14, surfaced for human approval.

### Files Created (new in Phase 5)

#### `src/hsb/agents/uat_agent.py`

```python
async def run_uat_and_validate(
    user_story_id: str,
    acceptance_criteria: list[str],
    uat_cycle: int,
) -> UATResult:
    """
    Standalone Claude Agent SDK session. Skill 08 inline. Pattern B from AI-SPEC §3.
    Returns validated UATResult. Raises RuntimeError after 3 failed validation attempts.
    """
```

Key implementation notes:
- `allowed_tools=["Read", "Glob", "Grep", "Bash"]` — no Write/Edit to prevent code mutation.
- `permission_mode="dontAsk"` — headless safe.
- `max_turns=20` — hard ceiling.
- `model="claude-sonnet-4-6"` — acceptance-criteria interpretation requires full reasoning.
- No `mcp_servers` for Linear writes — UAT Agent reads Linear state via `Glob`/`Grep` over exported context passed in the prompt; Linear writes happen through the Global Orchestrator → Linear Agent path after the UAT Agent returns.
- MCP access for reading Linear context: include `mcp_servers` for reads only, or pass the User Story JSON directly in the prompt (simpler, avoids MCP write risk). **Recommendation:** Pass the full User Story JSON in the prompt — no MCP needed, eliminates any risk of accidental MCP write.
- `UATResult` Pydantic validation with 3-retry loop per AI-SPEC §4b.1.

#### `src/hsb/agents/risk_agent.py`

```python
class RiskAgent:
    """
    Pure Python for skills 12+13. One isolated SDK call for skill 14.
    Skills 12+13 are deterministic math — no LLM, no MCP, no SDK.
    """

    def calculate_quality_score(
        self,
        work_item: WorkItemState,
        qa_history: list[QAFinding],
        uat_results: list[UATResult],
    ) -> QualityScore:
        """Deterministic formula. Pure Python."""

    def get_priority_queue(
        self,
        ready_tasks: list[str],
        linear_state: dict,
    ) -> PriorityQueue:
        """Sort by quality score descending. Tiebreak: updatedAt ascending. Pure Python."""

    async def detect_improvement_triggers(
        self,
        qa_history: list[QAFinding],
        scores: list[QualityScore],
    ) -> list[AutoImprovementTrigger]:
        """Isolated Haiku SDK call. Pattern C from AI-SPEC §3. No MCP. No tools."""
```

#### `src/hsb/agents/intelligence_agent.py`

This file is **thin** — it provides helper functions used by the WIO, not a standalone agent class. The "Intelligence Agent" executes inline within the WIO's `ClaudeSDKClient` session; there is no separate process or SDK session for it.

```python
def build_enrichment_prompt(work_item_id: str, work_item_json: str) -> str:
    """Constructs the WIO enrichment step prompt (Step 1)."""

def build_storage_prompt(qa_result: dict, implementation_notes: dict) -> str:
    """Constructs the WIO knowledge storage step prompt (Step 5)."""
```

#### `src/hsb/contracts/uat.py`

`UATScenario` and `UATResult` pydantic models — exact code from AI-SPEC §4b.1.

#### `src/hsb/contracts/risk.py`

`QualityScore`, `PriorityQueue`, `AutoImprovementTrigger` pydantic models — exact code from AI-SPEC §4b.1.

#### `src/hsb/contracts/knowledge.py`

```python
class KnowledgeEnrichmentOutput(BaseModel):
    work_item_id: str
    enrichment_report: dict  # matches AGENT-CONTRACTS.md §9 output structure
    retrieved_entries: list[str]  # file paths of Knowledge Store entries retrieved

class KnowledgeStorageInput(BaseModel):
    title: str
    type: Literal["architecture", "qa", "implementation", "backlog", "risk", "pattern", "anti_pattern"]
    context: str
    evidence: dict  # linear_issue, pr, files, qa_finding
    insight: str
    recommendation: str
    applicability: str = Field(..., description="Non-empty, not 'all tasks'")
    date: str  # YYYY-MM-DD

class KnowledgeStorageOutput(BaseModel):
    stored: bool
    location: str  # knowledge/category/YYYY-MM-DD-slug.md
    entry_id: str
    was_duplicate: bool  # True if deduplication check prevented write
```

### SKILL.md Files Created

Six new skill files must be created (per-skill pattern from Phases 1–4):

| Source | Destination | SKILL.md frontmatter notes |
|--------|-------------|---------------------------|
| `skills/08-UAT-VALIDATION.md` | `.claude/skills/uat-validation/SKILL.md` | `disable-model-invocation: true` (side effects); `allowed-tools: Read Glob Grep Bash` |
| `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md` | `.claude/skills/knowledge-context-enrichment/SKILL.md` | `disable-model-invocation: true`; `allowed-tools: Read Glob Grep` |
| `skills/11-KNOWLEDGE-STORAGE.md` | `.claude/skills/knowledge-storage/SKILL.md` | `disable-model-invocation: true`; `allowed-tools: Write` |
| `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` | `.claude/skills/quality-scoring-risk-analysis/SKILL.md` | `disable-model-invocation: true` (read-only risk reference) |
| `skills/13-ADAPTIVE-PRIORITIZATION.md` | `.claude/skills/adaptive-prioritization/SKILL.md` | `disable-model-invocation: true` |
| `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md` | `.claude/skills/auto-improvement-triggers/SKILL.md` | `disable-model-invocation: true`; `allowed-tools:` (empty — no tools for skill 14 LLM call) |

### Knowledge Store Layout

The `knowledge/` directory is already structured (FOUND-04). Phase 5 Intelligence Agent writes into these existing directories. No new directory creation needed.

```
knowledge/
  architecture/     # Architectural decision entries
  qa/               # Recurring QA finding entries
  implementation/   # Reusable implementation pattern entries
  patterns/         # Generalizable patterns
  anti-patterns/    # Anti-patterns discovered
  risk/             # Risk entries (fed to Risk Agent)
```

File naming convention: `YYYY-MM-DD-<slug>.md` where slug is a 3–5 word kebab-case summary of the title.

### `gh` CLI Usage for PR Data

The UAT Agent needs PR diff context to validate implementation. The recommended approach: pass the PR URL in the prompt and let the UAT Agent use `Bash` with `gh pr diff <pr-url>` and `gh pr view <pr-url>`. This keeps UAT Agent read-only on GitHub (no write operations possible via `gh pr diff`).

Key `gh` commands the UAT Agent will use:
- `gh pr view <url> --json title,body,state,url` — retrieve PR metadata
- `gh pr diff <url>` — retrieve the full diff (piped into the prompt context by the UAT Agent's `Bash` tool)

---

## Three Sub-System Designs

> References AI-SPEC sections rather than duplicating them.

### Sub-System 1: Intelligence Agent (Inline in WIO)

**SDK Pattern:** `ClaudeSDKClient` (Pattern A in AI-SPEC §3) — the existing WIO long-running session. No new SDK session.

**Implementation pattern:** Two additional `await client.query()` calls within the existing `async with ClaudeSDKClient(options=options) as client:` block.

**Step 1 (Enrich — before Builder):**
```
await client.query(
    f"Enrich work item {work_item_id} from the Knowledge Store before implementation. "
    f"Work item context: {work_item_json}"
)
```
The WIO (guided by skill 10 in its system prompt) runs `Glob` + `Grep` over `knowledge/` to retrieve relevant entries, produces an enrichment report, and stores it in the session context as `knowledge_context`. This value is then referenced in the Builder step prompt.

**Step 5 (Store — after QA result):**
```
await client.query(
    "Evaluate QA findings and implementation notes from this cycle. "
    "Apply skill 11 ingestion criteria. Write Knowledge Store entries only for "
    "insights that meet the signal threshold."
)
```
The WIO (guided by skill 11) uses its `Write` tool to create new markdown entries in `knowledge/<category>/`. It does not touch Linear.

**Deduplication (Claude's Discretion resolution — see §Open Implementation Choices):** The WIO's storage step (skill 11 instructions) should include a `Grep` check against existing entry titles before writing. This is implemented in the skill 11 prompt instructions, not in application code.

**Context budget:** Post Phase 5 injection, system prompt is ~6,250 tokens (~3% of 200K window). See AI-SPEC §4b.4 for the full budget analysis and mitigation options (skill index fallback, stateless re-injection, fork session).

### Sub-System 2: UAT Agent (Standalone SDK Session)

**SDK Pattern:** `query()` one-shot async generator (Pattern B in AI-SPEC §3) with Pydantic retry wrapper (Pattern from AI-SPEC §4b.1).

**Dispatch point:** `global_orchestrator.py` → `_detect_uat_ready_user_stories()` → `await run_uat_and_validate(user_story_id, acceptance_criteria, uat_cycle)`.

**Dispatch mechanism (Claude's Discretion resolution — see §Open Implementation Choices):** Inline `await` from within the Global Orchestrator's async method — NOT a subprocess. Rationale below.

**Scope boundary enforcement:** The SCOPE BOUNDARY literal string from AI-SPEC §4b.3 must appear in every UAT prompt call (not only in the skill 08 file) to survive context compaction.

**After UAT Agent returns:** Global Orchestrator inspects `UATResult.overall_status`. If `changes_required`, Global Orchestrator calls `linear_agent.create_subtasks(user_story_id, uat_result.findings)`. If `approved`, Global Orchestrator calls `linear_agent.update_issue(user_story_id, uat_status="approved")`.

**UAT cycle tracking:** `uat_cycle` is derived from the current Linear `uat_cycle_count` field on the User Story (or initialized to 1 if absent). Pre-dispatch guard: if `uat_cycle_count >= 3`, the Global Orchestrator escalates to human instead of dispatching UAT Agent (mirrors `max_qa_cycles` enforcement in the WIO).

### Sub-System 3: Risk Agent (Pure Python + Isolated Skill 14)

**SDK Pattern for skills 12+13:** None — pure Python class with deterministic math. No SDK, no MCP.

**SDK Pattern for skill 14:** `query()` minimal one-shot (Pattern C in AI-SPEC §3). `allowed_tools=[]`, no `mcp_servers`.

**Quality score formula (from `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md`):**
```
score = 100
score -= 10 * qa_failures
score -= 5 * fix_subtask_count
score -= 15 if uat_failed else 0
score -= 5 * rework_cycles
score = max(0, score)
```

**Risk level thresholds (from skill 12):**
- `score >= 75` → `low`
- `50 <= score < 75` → `medium`
- `score < 50` → `high`

**EPIC aggregation (Claude's Discretion resolution — see §Open Implementation Choices):** Weighted average where weight = number of QA findings for each task (tasks with more QA history have more influence on the EPIC score). Default neutral score for tasks without QA/UAT history: **85** (per `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` which specifies "e.g., 85").

**Priority score formula (from `skills/13-ADAPTIVE-PRIORITIZATION.md`):**
```
priority_score = (risk_weight * risk_score_numeric) + (qa_failures * qa_weight) + (blocker_flag * blocker_weight) + dependency_unlock_value
```
Where `risk_score_numeric` = 3 for HIGH, 2 for MEDIUM, 1 for LOW; weights are configurable constants defaulting to `risk_weight=3`, `qa_weight=1`, `blocker_weight=10`, `dependency_unlock_value` = count of tasks unblocked by completing this one.

**Tiebreaker:** When two items have identical `priority_score`, order by Linear `updatedAt` ascending (older items first). This ensures deterministic output across runs.

**Global Orchestrator integration:** `RiskAgent.get_priority_queue()` is called synchronously (the method is `def` not `async def` for skills 12+13). The skill 14 method is `async def` and awaited by the Global Orchestrator only when triggered.

---

## Data Contracts for Phase 5

> Based on AI-SPEC §4b.1. Full pydantic code is in that section — this table summarizes the contract landscape for planners.

### New Pydantic Models

| Model | File | Fields | Validates |
|-------|------|--------|-----------|
| `UATScenario` | `src/hsb/contracts/uat.py` | `criterion_id`, `criterion_text`, `status`, `evidence` (min 10 chars), `finding` (required when status=fail) | Per-scenario coverage completeness, evidence specificity |
| `UATResult` | `src/hsb/contracts/uat.py` | `user_story_id`, `overall_status`, `scenarios: list[UATScenario]`, `scope_violations: list[str]`, `uat_cycle: int >= 1` | Full acceptance-criteria coverage; no scope violations |
| `QualityScore` | `src/hsb/contracts/risk.py` | `work_item_id`, `score: float [0,100]`, `qa_failures`, `fix_subtask_count`, `uat_failed`, `rework_cycles`, `score_breakdown: dict` | Arithmetic invariant: `100 - sum(breakdown.values()) == score` |
| `PriorityQueue` | `src/hsb/contracts/risk.py` | `items: list[str]`, `scores: dict[str, float]` | All `items` have corresponding `scores` entry |
| `AutoImprovementTrigger` | `src/hsb/contracts/risk.py` | `title`, `description`, `pattern_evidence: list[str] (≥2)`, `suggested_type`, `linear_state: Literal["suggested"]` | `linear_state` is always "suggested" (Literal type enforces at parse time) |
| `KnowledgeEnrichmentOutput` | `src/hsb/contracts/knowledge.py` | `work_item_id`, `enrichment_report: dict`, `retrieved_entries: list[str]` | Output from WIO Step 1 |
| `KnowledgeStorageInput` | `src/hsb/contracts/knowledge.py` | All 8 INTL-03 required fields; `applicability` must not be empty or "all tasks" | Pre-write validation before `Write` tool call |
| `KnowledgeStorageOutput` | `src/hsb/contracts/knowledge.py` | `stored`, `location`, `entry_id`, `was_duplicate` | Confirms write or duplication skip |

### Existing Contract Fields Used (No Schema Changes)

| Contract (AGENT-CONTRACTS.md) | Field | How Phase 5 Uses It |
|-------------------------------|-------|---------------------|
| §4 Implementation Contract | `knowledge_context: {}` | WIO Step 1 populates this field before the Builder step; field already exists, no schema change |
| Global State Model | `uat_status: "not_required | pending | approved | changes_required"` | UAT Agent result stored here via Linear Agent |
| Global Orchestrator output (§D-03, Phase 4) | `ready_tasks`, `is_backlog_empty`, `is_epic_ready` | Phase 5 adds `uat_dispatched: list[str]` and `improvement_triggers: list[AutoImprovementTrigger]` as new optional fields |

---

## Integration Touchpoints

### 1. Global Orchestrator Extension (`src/hsb/agents/global_orchestrator.py`)

**New import at top:**
```python
from hsb.agents.risk_agent import RiskAgent
from hsb.agents.uat_agent import run_uat_and_validate
from hsb.contracts.risk import AutoImprovementTrigger
```

**New method: `_detect_uat_ready_user_stories(linear_state: dict) -> list[dict]`**

Logic:
1. Filter User Stories from `linear_state` where `type == "user_story"`.
2. For each User Story, fetch its child tasks (via `linear_agent.get_children(user_story_id)`).
3. A User Story is UAT-ready when ALL of:
   - All child tasks have `qa_status == "approved"`.
   - `uat_status` is NOT `"approved"` (re-trigger guard).
   - `uat_cycle_count < 3` (human escalation guard).

**Modified method: `get_ready_tasks(linear_state: dict) -> GlobalOrchestratorOutput`**

Insertion sequence:
```
1. [existing] Dependency filter → raw_ready_tasks
2. [new] risk_agent.get_priority_queue(raw_ready_tasks, linear_state) → sorted ready_tasks
3. [existing] EPIC readiness check (GORD-04 pattern)
4. [new] _detect_uat_ready_user_stories() → uat_ready list
5. [new] for each uat_ready: await run_uat_and_validate(...) → UATResult
6. [new] if UATResult.overall_status == "changes_required": linear_agent.create_subtasks(...)
7. [new] if UATResult.overall_status == "approved": linear_agent.update_issue(uat_status="approved")
8. [new] (periodically) risk_agent.detect_improvement_triggers(...) → triggers
```

**Priority queue contract (D-10):**
The Global Orchestrator's existing `ready_tasks` list (a `list[str]` of work item IDs) is replaced with the `PriorityQueue.items` list returned by `RiskAgent.get_priority_queue()`. The function signature of `get_ready_tasks()` does not change — the output contract's `ready_tasks` field is now risk-sorted.

### 2. WIO System Prompt Extension (`src/hsb/agents/work_item_orchestrator.py`)

**Current skill injection (7 skills post-Phase 5):**
```python
system_prompt = "\n\n---\n\n".join([
    load_skill(".claude/skills/backlog-planning/SKILL.md"),      # skill 02 (not actually used by WIO — check)
    load_skill(".claude/skills/implementation/SKILL.md"),        # skill 02
    load_skill(".claude/skills/qa-review/SKILL.md"),             # skill 03
    load_skill(".claude/skills/git-pr-management/SKILL.md"),     # skill 04
    load_skill(".claude/skills/linear-system-of-record/SKILL.md"),  # skill 05
    load_skill(".claude/skills/task-orchestration/SKILL.md"),    # skill 06
    load_skill(".claude/skills/knowledge-context-enrichment/SKILL.md"),  # skill 10 NEW
    load_skill(".claude/skills/knowledge-storage/SKILL.md"),             # skill 11 NEW
])
```

**Lifecycle steps (post-Phase 5):**
```
Step 1: [NEW] Intelligence enrichment (skill 10)
Step 2: Builder (skill 02) — receives knowledge_context from Step 1
Step 3: Git (skill 04)
Step 4: QA (skill 03) — max_qa_cycles=3 cap enforced
Step 5: [NEW] Knowledge storage evaluation (skill 11)
```

### 3. Linear Agent UAT Writes (`src/hsb/agents/linear_agent.py`)

The Phase 1 Linear Agent is **unchanged** as a class. Phase 5 calls existing Linear Agent methods with UAT-specific payloads:

- `linear_agent.update_issue(user_story_id, {"uat_status": "approved" | "changes_required", "uat_cycle_count": n})` — existing `update_issue()` method, new field values.
- `linear_agent.create_comment(user_story_id, uat_result_markdown)` — post UAT report as Linear comment (mirrors QA report persistence pattern from Phase 2).
- `linear_agent.create_subtasks(user_story_id, findings)` — existing subtask creation pattern (mirrors QA fix subtask creation).

No new methods needed in `linear_agent.py`. The existing interface from Phase 1 handles all UAT write operations.

### 4. Knowledge Store Directory Structure

`knowledge/` already exists (FOUND-04). Phase 5 writes files matching this naming convention:
```
knowledge/<category>/YYYY-MM-DD-<slug>.md
```

The Intelligence Agent (WIO skill 11 step) determines the category based on the entry `type` field. Category-to-directory mapping:
```python
CATEGORY_MAP = {
    "architecture": "architecture",
    "qa": "qa",
    "implementation": "implementation",
    "backlog": "backlog",        # note: skill 11 uses "backlog"; stack.md has this dir too
    "risk": "risk",
    "pattern": "patterns",      # note: dir is "patterns" not "pattern"
    "anti_pattern": "anti-patterns",
}
```

Each file has YAML frontmatter matching the `KnowledgeStorageInput` model fields, followed by markdown body.

### 5. `gh` CLI for PR Data (UAT Agent)

UAT Agent needs PR information. It uses `Bash` (in its `allowed_tools`) to call:
```bash
gh pr view <pr_url> --json title,body,state,additions,deletions,files
gh pr diff <pr_url>
```

The PR URL(s) are passed in the UAT prompt via the `related_prs` field from AGENT-CONTRACTS.md §7 input. The UAT Agent does not call GitHub API directly — it uses `gh` CLI, which uses the stored `GITHUB_TOKEN`.

---

## Validation Architecture

> Required section. `nyquist_validation: true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing in project) + Hypothesis (new for property-based tests) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `pytest tests/ -x -q --ignore=tests/evals/` |
| Full suite command | `pytest tests/ -v && poetry run promptfoo eval -c tests/evals/promptfoo.code.yaml` |

**New eval dependencies (add to `pyproject.toml`):**
```toml
[tool.poetry.group.eval.dependencies]
hypothesis = ">=6.100.0"
arize-phoenix = ">=4.0,<5.0"
openinference-instrumentation = ">=0.1.0"
opentelemetry-sdk = ">=1.25.0"
promptfoo = ">=0.85.0"
```

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Status |
|--------|----------|-----------|-------------------|-------------|
| UATA-01 | UAT dispatched when all child tasks QA-approved | integration | `pytest tests/integration/test_global_orchestrator_uat.py::test_uat_dispatch_on_all_tasks_approved -x` | Wave 0 |
| UATA-02 | UATResult.scenarios covers every AC; pass/fail per scenario | code + LLM-judge | `pytest tests/evals/code_based/test_uat_coverage.py -x` | Wave 0 |
| UATA-03 | Fix subtasks created in Linear when UAT `changes_required` | integration | `pytest tests/integration/test_uat_fix_subtasks.py -x` | Wave 0 |
| UATA-04 | UAT Agent produces no scope violations (no code-quality findings) | code | `pytest tests/evals/code_based/test_uat_scope.py -x` | Wave 0 |
| INTL-01 | Enrichment retrieval runs before Builder; `knowledge_context` populated | integration | `pytest tests/integration/test_wio_intelligence_enrichment.py -x` | Wave 0 |
| INTL-02 | Knowledge entry written after QA when ingestion criteria met | integration | `pytest tests/integration/test_wio_intelligence_storage.py -x` | Wave 0 |
| INTL-03 | All 8 required fields present in every written entry; regex checks pass | code | `pytest tests/unit/test_knowledge_storage_schema.py -x` | Wave 0 |
| INTL-04 | Intelligence steps never call Linear MCP write tools | unit | `pytest tests/unit/test_wio_allowed_tools.py -x` | Wave 0 |
| RISK-01 | Quality score deterministic; formula produces correct penalties | unit (Hypothesis) | `pytest tests/unit/test_risk_agent_quality_score.py -x` | Wave 0 |
| RISK-02 | Priority queue sorted score-descending; tiebreaker by updatedAt | unit | `pytest tests/unit/test_risk_agent_priority_queue.py -x` | Wave 0 |
| RISK-03 | AutoImprovementTrigger has ≥ 2 pattern_evidence refs | code | `pytest tests/unit/test_risk_agent_triggers.py -x` | Wave 0 |
| RISK-04 | Skill 14 SDK call has `allowed_tools=[]` and no `mcp_servers` | unit | `pytest tests/unit/test_risk_agent_skill14_config.py -x` | Wave 0 |

### Observable Behaviors per Success Criterion

**SC-1 (Intelligence enrichment report visible in work item comment):**
- Observable: After WIO Step 1 completes, `mcp__linear__get_issue(work_item_id).comments` contains a comment with "Enrichment Report" header and `knowledge_context` field populated.
- Test: Integration test — run WIO against a test task in the real Linear test workspace; assert the Linear comment exists and contains the enrichment output.

**SC-2 (Intelligence writes knowledge entry with all required fields):**
- Observable: After WIO Step 5 completes, a new `.md` file exists in `knowledge/<category>/` with YAML frontmatter containing all 8 required fields.
- Test: Integration test — run WIO against a test task that triggers a knowledge-worthy QA finding; assert the file exists and passes `KnowledgeStorageInput` validation.

**SC-3 (UAT Agent produces scenario results with pass/fail per AC):**
- Observable: `UATResult.scenarios` contains one entry per `[AC-N]` in the prompt; each entry has `status` in `["pass", "fail", "blocked"]` and non-empty `evidence`.
- Test: Code test — assert `{s.criterion_id for s in result.scenarios} == {f"AC-{i+1}" for i in range(len(acceptance_criteria))}`.

**SC-4 (Risk Agent produces quality score and prioritized queue consumed by Global Orchestrator):**
- Observable: `GlobalOrchestratorOutput.ready_tasks` is sorted by `RiskAgent.get_priority_queue()` output; each score has a `score_breakdown` dict.
- Test: Unit test — assert `100 - sum(score.score_breakdown.values()) == score.score`; integration test — assert Global Orchestrator output order matches risk-sorted order for a known input.

**SC-5 (Risk Agent detects QA failure patterns and surfaces suggestions without creating Linear items):**
- Observable: `AutoImprovementTrigger.linear_state == "suggested"` for all emitted triggers; `mcp__linear__list_issues` does NOT contain any new items created by the Risk Agent.
- Test: Code test — pydantic `Literal["suggested"]` enforces this at parse time; integration test — run Risk Agent skill 14 call against a test workspace and assert no new Linear issues created.

### Integration Test Strategy (Real Services — No Mocking)

Per Phase 2 integration test strategy (established in `02-CONTEXT.md`), all integration tests run against real external services:
- **Linear test workspace** — same workspace used in Phases 1–4 integration tests.
- **`hsb-test-fixture` GitHub repo** — existing fixture used for PR-related tests.
- **`knowledge/` directory** — real file writes; test teardown cleans up files with a `_test_` prefix in the slug.

**Test scenarios that exercise the full loops:**

1. **Intelligence enrichment loop (INTL-01, INTL-02):**
   - Pre-condition: `knowledge/qa/` contains one relevant entry for the test task domain.
   - Action: Trigger WIO on a test task.
   - Assert: (a) Step 1 retrieves the relevant entry (present in `knowledge_context`). (b) Step 5 writes at least one new entry after QA with a finding.

2. **UAT validation loop (UATA-01, UATA-02, UATA-03):**
   - Pre-condition: Test User Story in Linear with all child tasks `qa_status=approved`; acceptance criteria specified; related PR in `hsb-test-fixture`.
   - Action: Global Orchestrator cycle runs UAT detection.
   - Assert: (a) UAT Agent dispatched. (b) `UATResult` returned with scenario coverage = 100%. (c) If `changes_required`, Linear subtasks created.

3. **UAT re-trigger loop (UATA-01, D-02):**
   - Pre-condition: User Story with `uat_status=changes_required`; fix subtasks created; fix tasks now `qa_status=approved`.
   - Action: Global Orchestrator cycle.
   - Assert: UAT Agent re-dispatched on the parent User Story (stateless detection picks it up again as UAT-ready since fix tasks are now QA-approved).

4. **Risk priority queue (RISK-01, RISK-02):**
   - Pre-condition: Three test tasks in Linear with different QA histories (task A: 0 failures, task B: 1 failure, task C: 2 failures).
   - Action: `risk_agent.get_priority_queue([A, B, C], linear_state)`.
   - Assert: Output order is C → B → A (highest-risk first); score breakdown reconciles arithmetically.

5. **Auto-Improvement Trigger (RISK-03, RISK-04):**
   - Pre-condition: `qa_history` contains the same failure category appearing 3 times in the same module.
   - Action: `await risk_agent.detect_improvement_triggers(qa_history, scores)`.
   - Assert: (a) Returns at least one `AutoImprovementTrigger` with `pattern_evidence` length ≥ 2. (b) `linear_state == "suggested"`. (c) No new Linear issues exist after the call.

### Sampling Rate

- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q --ignore=tests/evals/llm_judge/`
- **Phase gate:** Full suite including code-based evals (`pytest tests/ && poetry run promptfoo eval -c tests/evals/promptfoo.code.yaml`) green before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/integration/test_global_orchestrator_uat.py` — covers UATA-01, UATA-03
- [ ] `tests/integration/test_wio_intelligence_enrichment.py` — covers INTL-01
- [ ] `tests/integration/test_wio_intelligence_storage.py` — covers INTL-02
- [ ] `tests/evals/code_based/test_uat_coverage.py` — covers UATA-02 coverage completeness
- [ ] `tests/evals/code_based/test_uat_scope.py` — covers UATA-04 scope boundary
- [ ] `tests/unit/test_knowledge_storage_schema.py` — covers INTL-03
- [ ] `tests/unit/test_wio_allowed_tools.py` — covers INTL-04
- [ ] `tests/unit/test_risk_agent_quality_score.py` — covers RISK-01 (Hypothesis)
- [ ] `tests/unit/test_risk_agent_priority_queue.py` — covers RISK-02
- [ ] `tests/unit/test_risk_agent_triggers.py` — covers RISK-03
- [ ] `tests/unit/test_risk_agent_skill14_config.py` — covers RISK-04
- [ ] `tests/integration/test_uat_fix_subtasks.py` — covers UATA-03
- [ ] `src/hsb/observability/tracing.py` — OTel bootstrap (Arize Phoenix)
- [ ] `tests/evals/promptfoo.code.yaml` — code-based promptfoo config
- [ ] `tests/evals/reference/` — reference dataset directory (30–60 examples per AI-SPEC §5)

---

## Open Implementation Choices Resolved

### 1. SKILL.md migration scope: per-skill vs. agent-level

**Decision: Per-skill pattern (one SKILL.md per skill file).**

Rationale: The established pattern from Phases 1–4 is one `.claude/skills/<name>/SKILL.md` per behavioral skill. All 6 Phase 5 skills are distinct behavioral units with different `allowed-tools` requirements (notably: skill 14 needs `allowed-tools:` empty, skills 10 and 11 need different tool sets). Combining them into agent-level files would make tool-set configuration ambiguous and would break the progressive-disclosure loading benefit of per-skill files.

Result: 6 new SKILL.md files, each with its own YAML frontmatter.

### 2. EPIC quality score aggregation: weighted vs. simple average; default neutral score

**Decision: Weighted average where weight = number of QA findings per task; default neutral score = 85.**

Rationale: The `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` specifies "EPIC score = weighted average of its Tasks" and explicitly sets "Tasks without QA/UAT → default neutral score (e.g., 85)." The skill spec resolves both choices. The weight mechanism: tasks with more QA history (more findings, more data) carry more weight in the EPIC score than tasks with zero history (which use the 85 default). Implementation:

```python
def calculate_epic_score(task_scores: list[QualityScore]) -> float:
    total_weight = sum(max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores)
    weighted_sum = sum(
        s.score * max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores
    )
    return weighted_sum / total_weight if total_weight > 0 else 85.0
```

Tasks with zero failures and zero subtasks get weight=1 (not 0) to prevent division-by-zero and to still count clean tasks in the average.

### 3. Knowledge Store deduplication: grep before write?

**Decision: Yes — perform a deduplication check before writing. Implemented via Glob+Grep in the skill 11 prompt instructions (not in application code).**

Rationale: The AI-SPEC eval dimension A4 defines a `title + insight` Jaccard overlap threshold of ≥ 0.85 as the duplicate detection criterion. The simplest implementation at MVP scale is to instruct the WIO (via skill 11 prompt) to grep existing entry titles in the target category before writing. If a match exists, the WIO reports the duplicate and sets `was_duplicate: True` in the `KnowledgeStorageOutput` without writing. This avoids the complexity of a separate Jaccard computation in Python code — the LLM can perform approximate title matching effectively.

Instruction added to skill 11: "Before writing a new entry, use `Grep` to search the target category for entries with titles similar to the new entry. If a near-duplicate exists, do not write a new entry. Report `was_duplicate: true` and reference the existing entry."

The post-write code-based check (Jaccard computation per AI-SPEC dimension A4) is for the eval suite, not for the runtime path.

### 4. UAT Agent dispatch mechanism: subprocess vs. inline

**Decision: Inline `await` from within the Global Orchestrator's async method — NOT a subprocess.**

Rationale:
1. **Architecture consistency:** WIO subprocesses are dispatched from the Main Orchestrator (Phase 4), not the Global Orchestrator. The Global Orchestrator is a pure Python class that makes `await` calls to async functions. UAT Agent dispatch follows the same pattern as any other `await` call from within the Global Orchestrator.
2. **No worktree needed:** WIO subprocesses require git worktree isolation (Phase 4 D-07) because they write code to the repo. The UAT Agent is read-only (no code writes, no git operations) — worktree isolation provides no benefit.
3. **Simpler error handling:** An inline `await` surfaces `RuntimeError` from the UAT Agent retry wrapper directly to the Global Orchestrator, which can mark the UAT cycle as blocked. A subprocess would require a separate error-propagation mechanism.
4. **Event loop safety:** The Global Orchestrator's `get_ready_tasks()` is already `async def`. Calling `await run_uat_and_validate(...)` from within it is correct Python async pattern. The only place `asyncio.run()` is used is the CLI entry point (`run_loop.py`) — unchanged.

**Implication:** If multiple User Stories are UAT-ready in the same cycle, they are dispatched sequentially (one `await` after another). This is acceptable at MVP scale (User Stories rarely all become UAT-ready simultaneously). Parallel UAT dispatch is a future optimization if needed.

---

## Plan Decomposition Recommendation

### Suggested Plan Split

**4 plans, reflecting the 3 sub-system surfaces plus the Global Orchestrator integration.**

```
Plan 05-A: Intelligence Agent — WIO Extension
Plan 05-B: Risk Agent — Pure Python Class + Skill 14
Plan 05-C: UAT Agent — Standalone Session + SKILL.md
Plan 05-D: Global Orchestrator — Risk Integration + UAT Dispatch
```

### Dependency Graph

```
Plan 05-A (Intelligence inline)
    ↓ produces: validated WIO with skill 10+11 injection + knowledge/ write capability
    
Plan 05-B (Risk Agent)
    ↓ produces: RiskAgent class with get_priority_queue() and detect_improvement_triggers()
    (independent of 05-A — no shared code)
    
Plan 05-C (UAT Agent)
    ↓ produces: run_uat_and_validate() function + UATResult pydantic contract + SKILL.md
    (independent of 05-A and 05-B)
    
Plan 05-D (Global Orchestrator extension)
    ↑ depends on: 05-B (needs RiskAgent.get_priority_queue), 05-C (needs run_uat_and_validate)
    ↑ optional dependency on 05-A: can be built before 05-A since Global Orchestrator calls WIO as a subprocess and doesn't care about WIO internals
    ↓ produces: fully integrated Phase 5 Global Orchestrator
```

### Rationale

- **05-A and 05-B are independent** — they touch different files (`work_item_orchestrator.py` vs. new `risk_agent.py`). They can be planned and executed in parallel.
- **05-C is independent of 05-A and 05-B** — `uat_agent.py` is a new standalone file; its only dependency is the existing `linear_agent.py` from Phase 1.
- **05-D is the integration plan** — it cannot be completed until both 05-B (for `risk_agent.get_priority_queue()`) and 05-C (for `run_uat_and_validate()`) are done. Plan 05-A's changes (WIO internals) are invisible to the Global Orchestrator — 05-D does not need to wait for 05-A.
- **Plan size:** Each plan is approximately 3–7 implementation tasks, fitting within the standard granularity. Plan 05-D is the smallest (2–3 tasks — mostly wiring the imports and adding the two new methods to `global_orchestrator.py`).

### Execution Order Recommendation

If running sequentially (cascade mode), execute in order: 05-A → 05-B → 05-C → 05-D. Plans 05-A through 05-C are individually verifiable before 05-D wires them together. This gives the operator three isolated checkpoints before the full integration.

---

## Risks & Mitigations Specific to Phase 5

### Risk 1: WIO Context Pressure from Skill 10+11 Injection

**Probability:** Low (3% system prompt budget is safe per AI-SPEC §4b.4, but risk increases on tasks with many large files and multiple QA cycles).
**Impact:** Medium — if the WIO hits context pressure, the skill 11 Knowledge Storage step may be cut off, causing knowledge entries to be missed.
**Mitigation:** Monitor `ResultMessage.usage["input_tokens"]` and emit a warning when > 120K tokens (60% of 200K). Implement the skill index fallback (AI-SPEC §4b.4 Option 1) as a ready-to-activate path: replace full skill 10+11 content with one-line `Read`-on-demand pointers.
**Detection:** WIO `stop_reason == "error_max_turns"` or warning log > 120K tokens.

### Risk 2: UAT False-Pass (Most Critical Failure Mode)

**Probability:** Low-Medium — acceptance criteria ambiguity is the primary trigger.
**Impact:** High — a false-pass closes a User Story with unmet criteria, polluting the "done" state.
**Mitigation:** 
- `UATResult.scenarios` coverage check (code-based eval B1): `{s.criterion_id for s in result.scenarios} == expected_criterion_ids`. Any coverage gap blocks approval.
- 3-retry Pydantic validation loop with validation error fed back into prompt.
- Scope boundary literal in every UAT prompt (not only in skill 08).
- UAT cycle cap: max 3 cycles before human escalation (mirrors `max_qa_cycles=3`).
**Detection:** B1 code eval fails in CI; or operator observes User Story closed with an unmet criterion surfacing as a production issue.

### Risk 3: Knowledge Store Contamination (Compounding Noise)

**Probability:** Medium — LLM judgment for ingestion criteria is inherently probabilistic; early Knowledge Store has few entries to establish quality norms.
**Impact:** Medium (compounding) — low-signal entries degrade future Builder enrichment quality over time; hard to detect until the store grows large.
**Mitigation:**
- A2 code eval (schema completeness): pydantic + regex post-write hook validates all 8 required fields on every write. Rejects entries with empty `applicability` or `evidence`.
- Deduplication grep (Claude's Discretion resolution): prevents obvious duplicates.
- Skill 11 prompt includes explicit ingestion criteria with concrete examples of what does and does not qualify (patterns vs. one-off bugs).
**Detection:** Post-write schema validation failures in integration tests; periodic human review of `knowledge/` entries flagged by A1 LLM-judge eval (quarterly).

### Risk 4: Risk Agent Linear Write via Skill 14 (RISK-04 Violation)

**Probability:** Very Low — structural guarantee enforced by SDK configuration.
**Impact:** Critical — unauthorized Linear pollution erodes operator trust.
**Mitigation:**
- Skill 14 SDK call: `allowed_tools=[]`, no `mcp_servers`. The SDK cannot call any tool or MCP method; the LLM physically cannot write to Linear regardless of its reasoning.
- C6 code eval: `AutoImprovementTrigger.linear_state == "suggested"` enforced by pydantic `Literal["suggested"]` — rejects any other value at parse time.
- INTL-04 unit test: asserts no Linear MCP write tools appear in the WIO's or Risk Agent's `allowed_tools`.
**Detection:** C6 code eval fails (impossible given pydantic Literal constraint); G2 guardrail from AI-SPEC §6 (`"Agent" not in options.allowed_tools`).

### Risk 5: UAT Cycle Runaway (Pitfall 2 Extension)

**Probability:** Low — deterministic guard in place.
**Impact:** Medium — UAT generates fix tasks, fix tasks complete, UAT re-triggers, repeats indefinitely.
**Mitigation:**
- Pre-dispatch guard in Global Orchestrator: `if uat_cycle_count >= 3: escalate_to_human()` instead of dispatching UAT Agent.
- B5 code eval: asserts `uat_cycle <= 3` and increments correctly.
- Same `max_qa_cycles=3` invariant applied to UAT cycles (per CONTEXT.md D-02 and Pitfall 2 in PITFALLS.md).
**Detection:** Linear `uat_cycle_count` field reaches 3 without `uat_status=approved`; B5 eval catches this in integration tests.

### Risk 6: SDK Import Path Regression (All Phase 5 Code)

**Probability:** Low — but risk exists because Phases 1–4 code may still have old `claude_code_sdk` imports.
**Impact:** Medium — causes `ModuleNotFoundError` at runtime; all Phase 5 SDK code fails.
**Mitigation:** AI-SPEC §3 Common Pitfall 1 documents this explicitly. Wave 0 task: audit all existing imports in `src/hsb/agents/` before writing Phase 5 code. Correct import root is `claude_agent_sdk`.
**Detection:** `grep -r "claude_code_sdk" src/` returns any matches.

### Risk 7: UAT Agent Scope Creep into Code Review (Pitfall 8)

**Probability:** Medium — LLM agents with broad read access tend to comment on implementation quality.
**Impact:** Medium — UAT findings reference code quality, creating spurious fix subtasks and eroding operator trust.
**Mitigation:**
- Banned-token regex in B3 code eval (`refactor`, `code quality`, `naming`, `style`, `linter`, `inefficient`, `should also handle`, `future edge case`).
- `UATResult.scope_violations: list[str]` field — any non-empty list fails the B3 check.
- UAT allowed_tools deliberately excludes `Edit` and `Write` — the agent can read code but cannot modify it, which reduces the temptation to engage with implementation quality.
**Detection:** B3 code eval fails in CI.

---

## Sources

### Primary (HIGH confidence)

- `05-AI-SPEC.md` §3 Framework Quick Reference — all SDK patterns, `ClaudeAgentOptions` fields, `query()` vs. `ClaudeSDKClient` usage, pitfalls, recommended project structure. Documented as fetched from official Anthropic docs on 2026-05-06.
- `05-AI-SPEC.md` §4, §4b — Implementation Guidance, AI Systems Best Practices; pydantic contracts, async design, prompt engineering discipline, context window strategy, cost/latency budgets.
- `05-AI-SPEC.md` §5 — Evaluation Strategy; dimension rubrics (A1–A4, B1–B6, C1–C6), eval tooling (Arize Phoenix, Promptfoo, Hypothesis), reference dataset composition, CI failure policy.
- `05-AI-SPEC.md` §6 — Online Guardrails (G1 OAuth assertion, G2 allowed_tools check).
- `agents/AGENT-CONTRACTS.md` — all agent contracts referenced; §4 confirms `knowledge_context: {}` field already exists; §7 UAT contract input/output schemas; §9–§13 Phase 5 contracts.
- `skills/08-UAT-VALIDATION.md`, `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md`, `skills/11-KNOWLEDGE-STORAGE.md`, `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md`, `skills/13-ADAPTIVE-PRIORITIZATION.md`, `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md` — behavioral specs, ingestion criteria, formula details.
- `05-CONTEXT.md` — all locked decisions D-01 through D-10; discretion areas; integration points (code_context section).
- `04-CONTEXT.md` — Phase 4 Global Orchestrator architecture; D-01 (pure Python class), D-03 (output contract), D-05 (sequential claiming), D-08 (subprocess dispatch).
- `03-CONTEXT.md` — WIO inline skill injection architecture (D-01); lifecycle sequence (D-03, Intelligence deferred to Phase 5); context budget note.
- `.planning/research/STACK.md` — verified library versions, Knowledge Store format, SKILL.md frontmatter fields.
- `.planning/research/PITFALLS.md` — Pitfall 2 (QA runaway, applies to UAT cycle), Pitfall 5 (context exhaustion), Pitfall 8 (UAT scope creep), Pitfall 12 (Knowledge Store pollution).

### Secondary (MEDIUM confidence)

- `runtime/RUNTIME-EXECUTION.md` — action type definitions (UAT_VALIDATE, KNOWLEDGE_ENRICH, KNOWLEDGE_STORE, IMPROVEMENT_TRIGGER); state transition diagrams for UAT flow.
- `agents/AGENTS.md` — Agent Mapping table confirms Intelligence Agent = skills 10+11; Risk Agent = skills 12+13+14.
- `04-RESEARCH.md` — Phase 4 research patterns (Global Orchestrator filter/sort, EPIC completion detection) reused as templates for Phase 5 UAT-readiness detection.

### Tertiary (N/A — no LOW confidence claims in this research)

All claims are derived from verified project documentation (CONTEXT.md, AI-SPEC, skill files, agent contracts). No web searches or training-data assumptions were needed — the Phase 5 technical decisions were locked before this research session.

---

## Assumptions Log

> Claims tagged `[ASSUMED]` in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `work_item_orchestrator.py` from Phase 3 uses `ClaudeSDKClient` (not `query()` one-shot) and exists at `src/hsb/agents/work_item_orchestrator.py` | Phase Boundary & Code Attachment Points | If WIO uses `query()` one-shot, the multi-step `client.query()` injection pattern for Intelligence steps would need to be redesigned; however AI-SPEC §3 Pattern A explicitly describes the `ClaudeSDKClient` pattern for WIO. Confidence: HIGH. |
| A2 | `knowledge/` directory already exists with category subdirs as specified by FOUND-04 | Integration Touchpoints §4 | If not created by Phase 1, a Wave 0 task must create it. Risk: low (FOUND-04 is a Phase 1 requirement). |
| A3 | Phase 4 `global_orchestrator.py` is a pure Python class (confirmed D-01 in 04-CONTEXT.md) with an async method that can host `await run_uat_and_validate(...)` calls | Open Implementation Choices §4 (UAT dispatch) | If Global Orchestrator is not async, UAT dispatch would need refactoring. Confidence: HIGH — D-01 and 04-CONTEXT.md are unambiguous. |
| A4 | `src/hsb/contracts/` directory exists with Phase 1–4 pydantic models and `__init__.py` | Data Contracts §New Pydantic Models | If directory layout differs, file paths in the plan need updating. Low risk — this is the established pattern documented in 01-CONTEXT.md and 04-RESEARCH.md. |

**If this table is nearly empty:** All primary claims were derived from verified project documentation. The four assumptions above are all HIGH confidence based on prior-phase decision records.

---

## Open Questions

1. **WIO skill injection order** — AI-SPEC §3 Pattern A shows skills 02–06 then 10+11. Does the planner need to confirm the exact ordering within the existing 02–06 set, or is any order acceptable?
   - What we know: AI-SPEC §4b.3 recommends `system_prompt` carry behavioral instructions (skill content) and `prompt` carry dynamic data. The exact ordering of 7 skills in the system prompt is not prescribed beyond "task-orchestration first as the meta-skill."
   - Recommendation: Keep Phase 3's established ordering for skills 02–06; append skills 10+11 at the end (after all existing skills) to minimize disruption to the validated context budget.

2. **`linear_agent.py` method names** — The Phase 1 Linear Agent service interface has specific method names (`create_subtask`, `update_issue_status`, etc.). Phase 5 callers (Global Orchestrator for UAT writes, Risk Agent for trigger delegation) need to know the exact existing method signatures.
   - What we know: Phase 1 provided `linear_agent.py` but its source tree is not present in the current repo (only skills and planning docs exist). The AGENT-CONTRACTS.md §2 defines the Linear Agent operation contract (`operation: "create | update | read | link | comment | create_subtasks"`).
   - Recommendation: Plan 05-C and 05-D should include a Wave 0 task to inspect the existing `linear_agent.py` method signatures before writing callers.

3. **UAT `uat_cycle_count` Linear field** — CONTEXT.md D-02 mentions "after fix tasks reach QA-approved, Global Orchestrator re-triggers UAT on the parent User Story." What field name tracks UAT cycles in Linear?
   - What we know: The state model in AGENT-CONTRACTS.md has `uat_status` but does not explicitly define a `uat_cycle_count` field (unlike `qa_cycle_count` which is defined in REQUIREMENTS.md QAAG-04). This field may need to be defined as a metadata field or derived from comment history.
   - Recommendation: Define `uat_cycle_count` as a `metadata` key in the work item's `metadata: {}` field (already in the Global State Model), updated by the Linear Agent when UAT is dispatched. Plan 05-D should include explicit definition of this field.

---

## Environment Availability

> Checked against the project context (no external services beyond those established in Phases 1–4).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `claude-agent-sdk` | UAT Agent, Risk skill 14 | Confirmed (Phases 1–4) | 0.1.73+ | — |
| Linear MCP (`mcp-remote`) | Global Orchestrator, Linear Agent | Confirmed (Phase 1) | Current | — |
| `gh` CLI | UAT Agent (`gh pr diff`, `gh pr view`) | Assumed available (Phase 2) | 2.x+ | Manual PR diff injection in prompt |
| `knowledge/` directory | Intelligence Agent writes | FOUND-04 (Phase 1 requirement) | — | Wave 0 creation task |
| `pytest` + `hypothesis` | Risk Agent unit tests | pytest confirmed (existing); hypothesis new | 6.100+ | Standard install |
| `arize-phoenix` | Eval observability (optional) | Not yet installed | 4.x | Skip tracing; use logs |
| `promptfoo` | Structural evals in CI | Not yet installed | 0.85+ | pytest-only eval suite |

**Missing dependencies with no fallback:**
- None that block core Phase 5 implementation.

**Missing dependencies with fallback:**
- `arize-phoenix` / `promptfoo` — eval infrastructure, not on the critical path for UATA/INTL/RISK requirements. Can be deferred to a Wave 1 "eval setup" task without blocking the agent implementation tasks.

---

## Security Domain

> `security_enforcement` not explicitly set to `false` in `config.json`; treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | OAuth2 via `CLAUDE_CODE_OAUTH_TOKEN`; startup assertion `"ANTHROPIC_API_KEY" not in os.environ` (Guardrail G1) |
| V3 Session Management | Yes | WIO `ClaudeSDKClient` session IDs persisted to `.claude/session_cache.json`; resume uses `cwd` consistency check (AI-SPEC §3 Pitfall 3) |
| V4 Access Control | Yes | `allowed_tools` whitelist enforced per agent; Risk skill 14 has `allowed_tools=[]`, no MCP — structural access control (Guardrail G2) |
| V5 Input Validation | Yes | All SDK outputs validated via pydantic with 3-retry loop before any downstream action |
| V6 Cryptography | No | No cryptographic operations in Phase 5; OAuth token handling delegated to `mcp-remote` |

### Known Threat Patterns for Phase 5 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in environment overrides OAuth token | Spoofing | Startup assertion `assert "ANTHROPIC_API_KEY" not in os.environ` (Guardrail G1, AI-SPEC §3 Pitfall 6) |
| Sub-subagent dispatch creates uncontrolled SDK sessions | Elevation of Privilege | `"Agent" not in options.allowed_tools` validated by `make_options()` factory (Guardrail G2); structural enforcement, not behavioral |
| Risk Agent skill 14 writes to Linear via MCP | Tampering | `allowed_tools=[]` + no `mcp_servers` in skill 14 SDK call — physically cannot write to Linear (RISK-04 guarantee) |
| Knowledge Store contamination via prompt injection in Linear issues | Tampering | Pydantic schema validation on every `KnowledgeStorageInput`; `evidence.linear_issue` regex check; applicability non-empty check |
| UAT Agent scope creep reading arbitrary codebase files | Information Disclosure | `allowed_tools` limited to `["Read","Glob","Grep","Bash"]`; no `Write`/`Edit`; `permission_mode="dontAsk"` blocks any tool not in list |

---

## ## RESEARCH COMPLETE
