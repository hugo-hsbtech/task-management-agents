# Phase 5: Enhancement Agents - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 18 new/modified files
**Analogs found:** 18 / 18 (all spec-derived from Phase 1–4 PATTERNS.md and specification documents; no Python source exists yet)

> **Greenfield note (same as Phases 1–4):** The repository still contains only markdown documentation — no Python source code has been created yet. Every pattern below is derived from (1) Phase 1 PATTERNS.md (canonical foundation: `asyncio.run()`, `load_dotenv()`, Pydantic `extra="forbid"`, OAuth2 guard), (2) Phase 2 PATTERNS.md (agent/contract/test extensions, `MAX_VALIDATION_RETRIES` retry loop, `model_config = {"extra": "forbid"}`), (3) Phase 3 PATTERNS.md (WIO SDK session, `load_skill()`, inline skill injection assembly, `@tool` wrappers), (4) Phase 4 PATTERNS.md (GlobalOrchestrator pure Python class pattern, async coroutine structure, `_filter_ready_items`, `_check_epic_complete`), and (5) `05-AI-SPEC.md` §3–4b (Pattern A/B/C, Pydantic contracts, retry wrapper). Phase 5 adds no new architectural primitives — it extends all four prior patterns. All code excerpts below are canonical — copy verbatim, do not paraphrase.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/hsb/agents/uat_agent.py` | service | request-response (standalone `query()` session, Pattern B) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — `query()` loop, `AssistantMessage`/`ResultMessage` handling) + AI-SPEC §3 Pattern B | role-match + SDK-pattern-match |
| `src/hsb/agents/risk_agent.py` | service | CRUD (pure Python class for skills 12+13) + request-response (isolated `query()` for skill 14) | `src/hsb/agents/global_orchestrator.py` (Phase 4 PATTERNS.md — pure Python class, no SDK session, deterministic filter/sort) + AI-SPEC §3 Pattern C | exact-role (skills 12+13) + SDK-pattern-match (skill 14) |
| `src/hsb/agents/work_item_orchestrator.py` (extend) | service | event-driven (multi-step `ClaudeSDKClient` session, Pattern A) | `src/hsb/agents/work_item_orchestrator.py` (Phase 3 PATTERNS.md — `assemble_system_prompt()`, `ClaudeAgentOptions`, `client.query()` loop) | exact-role (delta only) |
| `src/hsb/agents/global_orchestrator.py` (extend) | service | CRUD (pure Python class + new `await run_uat_and_validate()` calls) | `src/hsb/agents/global_orchestrator.py` (Phase 4 PATTERNS.md — `GlobalOrchestrator` class, `_check_epic_complete` pattern) | exact-role (delta only) |
| `src/hsb/contracts/uat.py` | model | CRUD (pydantic validate + `Literal` + `Field` constraints) | `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md — `model_validator`, `Literal` status enum, `extra="forbid"`) | exact-role |
| `src/hsb/contracts/risk.py` | model | CRUD (pydantic validate + `Literal` + arithmetic invariant) | `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md — `Literal` enforcement, field constraints) | exact-role |
| `src/hsb/contracts/knowledge.py` | model | CRUD (pydantic validate + 8 required fields + applicability constraint) | `src/hsb/contracts/builder.py` (Phase 2 PATTERNS.md — `extra="forbid"`, `Literal` type, nested model structure) | exact-role |
| `src/hsb/agents/_sdk_options.py` | utility | — (factory function, no data flow) | AI-SPEC §3 Pattern A/B/C `ClaudeAgentOptions` blocks | spec-derived |
| `.claude/skills/uat-validation/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter structure, `disable-model-invocation: true`) | exact-role |
| `.claude/skills/knowledge-context-enrichment/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter) | exact-role |
| `.claude/skills/knowledge-storage/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter) | exact-role |
| `.claude/skills/quality-scoring-risk-analysis/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter) | exact-role |
| `.claude/skills/adaptive-prioritization/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter) | exact-role |
| `.claude/skills/auto-improvement-triggers/SKILL.md` | config | — | `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md — SKILL.md frontmatter, `allowed-tools:` empty) | exact-role |
| `tests/integration/test_uat_agent.py` | test | request-response (integration, real Linear workspace) | `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — `pytestmark = [pytest.mark.integration]`, real Linear workspace, `@pytest.mark.asyncio`) | exact-role |
| `tests/integration/test_intelligence_enrichment.py` | test | file-I/O + request-response (integration, real `knowledge/` writes) | `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — integration marker, real service, side-effect assertions) | role-match |
| `tests/integration/test_risk_priority_queue.py` | test | CRUD (unit/integration, Hypothesis property-based for deterministic math) | `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md — `pytest.raises(ValidationError)`, `pytest.mark.asyncio`) | role-match (adds Hypothesis) |
| `tests/integration/test_global_orchestrator_phase5.py` (extend) | test | CRUD + request-response (integration, adds UAT-readiness + Risk scenarios) | `tests/integration/test_global_orchestrator_e2e.py` (Phase 4 PATTERNS.md — real Linear workspace, two-task gate) | exact-role (delta only) |

---

## Pattern Assignments

### `src/hsb/agents/uat_agent.py` (service, request-response, SDK Pattern B)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — `query()` loop, `load_dotenv()`, `AssistantMessage`/`ResultMessage` message handling) extended with AI-SPEC §3 Pattern B and §4b.1 Pydantic retry wrapper.

**Source specs:** `05-AI-SPEC.md` §3 Pattern B, §4b.1 `run_uat_and_validate` with retry, §4b.3 scope boundary injection; `05-RESEARCH.md` §Files Created `uat_agent.py` block; `skills/08-UAT-VALIDATION.md` (system prompt body).

**Imports pattern** (Phase 1 PATTERNS.md `linear_agent.py` import block + Phase 3 WIO additions):

```python
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from dotenv import load_dotenv
from pydantic import ValidationError

from hsb.contracts.uat import UATResult, UATScenario

load_dotenv()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def load_skill(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
```

**Core Pattern B session** (AI-SPEC §3 Pattern B — standalone bounded `query()` per User Story, not resumed, `dontAsk`):

```python
async def run_uat_and_validate(
    user_story_id: str,
    acceptance_criteria: list[str],
    uat_cycle: int,
) -> UATResult:
    """
    Standalone Claude Agent SDK session. Skill 08 inline (Pattern B, AI-SPEC §3).
    Returns validated UATResult. Raises RuntimeError after MAX_RETRIES failed validation
    attempts — never returns an unvalidated result.
    WORC-02: "Agent" is absent from allowed_tools — no sub-subagent dispatch.
    """
    skill_08 = load_skill(".claude/skills/uat-validation/SKILL.md")
    schema_json = json.dumps(UATResult.model_json_schema(), indent=2)
    scope_block = "\n".join(f"[AC-{i+1}] {c}" for i, c in enumerate(acceptance_criteria))

    base_prompt = (
        f"Validate User Story {user_story_id} (UAT cycle {uat_cycle}).\n\n"
        "SCOPE BOUNDARY: Only validate the acceptance criteria listed below. "
        "Do not evaluate any feature, behavior, or quality dimension not explicitly listed. "
        "Any finding that lacks a direct reference to a listed [AC-N] criterion is out of scope "
        "and must not appear in your response.\n\n"
        f"Acceptance criteria:\n{scope_block}\n\n"
        f"Return a single JSON object matching this schema:\n{schema_json}\n"
        "Do not include any prose before or after the JSON."
    )

    options = ClaudeAgentOptions(
        system_prompt=skill_08,
        allowed_tools=["Read", "Glob", "Grep", "Bash"],  # No "Agent" — WORC-02
        permission_mode="dontAsk",   # Deny anything not in allowed_tools — headless safe
        max_turns=20,                # Hard ceiling (AI-SPEC §3 Pattern B)
        model="claude-sonnet-4-6",   # Acceptance-criteria interpretation (AI-SPEC §4 Model Config)
    )
```

**Pydantic retry wrapper** (AI-SPEC §4b.1 — copy verbatim; 3 retries, error fed back into prompt):

```python
    last_error: str | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        prompt = base_prompt
        if last_error:
            prompt += f"\n\nPrevious attempt failed validation: {last_error}. Fix and retry."

        result_text = ""
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_text = msg.result or ""
                if msg.stop_reason == "error_max_turns":
                    raise RuntimeError(f"UAT Agent hit max_turns for {user_story_id}")

        try:
            clean = result_text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(clean)
            data.setdefault("user_story_id", user_story_id)
            data.setdefault("uat_cycle", uat_cycle)
            return UATResult(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning(
                "UATResult validation failed (attempt %d/%d) for %s: %s",
                attempt, MAX_RETRIES, user_story_id, last_error,
            )

    raise RuntimeError(
        f"UAT Agent failed to produce valid UATResult after {MAX_RETRIES} attempts "
        f"for {user_story_id}. Last error: {last_error}"
    )
```

**Critical rules:**
- `"Agent"` MUST NOT appear in `allowed_tools` — this is the sole WORC-02 enforcement mechanism (AI-SPEC §3 Key Abstractions).
- `permission_mode="dontAsk"` is mandatory for headless execution — `"default"` causes a process hang (AI-SPEC Common Pitfall 4).
- `max_turns` must always be set explicitly — the SDK default is unlimited, enabling infinite loops on tool error (AI-SPEC Common Pitfall 5).
- No `mcp_servers` for UAT Agent — User Story JSON is passed in the prompt string directly, eliminating MCP write risk (05-RESEARCH.md §Files Created `uat_agent.py` key implementation notes).
- All Linear writes happen AFTER the UAT Agent returns — through Global Orchestrator → Linear Agent path.
- UAT Agent DEVIATIONS from prior phase patterns: uses `query()` one-shot (not `ClaudeSDKClient`); no `mcp_servers` block; `max_turns=20` (lower than WIO's 40).

---

### `src/hsb/agents/risk_agent.py` (service, CRUD + request-response for skill 14)

**Analog for skills 12+13:** `src/hsb/agents/global_orchestrator.py` (Phase 4 PATTERNS.md — `GlobalOrchestrator` pure Python class pattern, deterministic filter/sort, no LLM, no SDK session, `load_dotenv()`).

**Analog for skill 14:** AI-SPEC §3 Pattern C — isolated one-shot `query()` with `allowed_tools=[]` and no `mcp_servers`.

**Source specs:** `05-AI-SPEC.md` §3 Pattern C, §4b.1 `QualityScore`/`PriorityQueue`/`AutoImprovementTrigger` models; `05-RESEARCH.md` §Sub-System 3 quality score formula and priority score formula, EPIC aggregation pattern; `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md`; `skills/13-ADAPTIVE-PRIORITIZATION.md`; `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md`.

**Imports pattern** (Phase 4 PATTERNS.md `global_orchestrator.py` imports + AI-SPEC §3 Pattern C SDK imports):

```python
from __future__ import annotations
import logging
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from dotenv import load_dotenv

from hsb.contracts.risk import QualityScore, PriorityQueue, AutoImprovementTrigger

load_dotenv()
logger = logging.getLogger(__name__)


def load_skill(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
```

**Pure Python class pattern for skills 12+13** (Phase 4 PATTERNS.md `GlobalOrchestrator` class structure — pure Python, no SDK):

```python
class RiskAgent:
    """
    Pure Python for skills 12+13. One isolated SDK call for skill 14.
    Skills 12+13 are deterministic math — no LLM, no MCP, no SDK.
    RISK-04: No Linear writes without explicit delegation through Linear Agent.
    """

    def calculate_quality_score(
        self,
        work_item: dict,
        qa_history: list[dict],
        uat_results: list[dict],
    ) -> QualityScore:
        """Deterministic formula (skill 12). Pure Python. No LLM."""
        qa_failures = sum(1 for qa in qa_history if qa.get("status") == "changes_required")
        fix_subtask_count = work_item.get("fix_subtask_count", 0)
        uat_failed = any(r.get("overall_status") == "changes_required" for r in uat_results)
        rework_cycles = work_item.get("qa_cycle_count", 0)

        score = 100.0
        score -= 10 * qa_failures
        score -= 5 * fix_subtask_count
        score -= 15 if uat_failed else 0
        score -= 5 * rework_cycles
        score = max(0.0, score)

        breakdown = {
            "qa_failures_penalty": 10 * qa_failures,
            "fix_subtask_penalty": 5 * fix_subtask_count,
            "uat_failure_penalty": 15 if uat_failed else 0,
            "rework_penalty": 5 * rework_cycles,
        }
        return QualityScore(
            work_item_id=work_item["id"],
            score=score,
            qa_failures=qa_failures,
            fix_subtask_count=fix_subtask_count,
            uat_failed=uat_failed,
            rework_cycles=rework_cycles,
            score_breakdown=breakdown,
        )

    def get_priority_queue(
        self,
        ready_tasks: list[str],
        linear_state: dict,
    ) -> PriorityQueue:
        """Sort by quality score descending. Tiebreaker: updatedAt ascending. Pure Python."""
        scores: dict[str, float] = {}
        for task_id in ready_tasks:
            item = linear_state.get(task_id, {})
            qs = self.calculate_quality_score(
                item,
                item.get("qa_history", []),
                item.get("uat_results", []),
            )
            scores[task_id] = qs.score

        sorted_ids = sorted(
            ready_tasks,
            key=lambda tid: (-scores[tid], linear_state.get(tid, {}).get("updatedAt", "")),
        )
        return PriorityQueue(items=sorted_ids, scores=scores)
```

**EPIC score aggregation** (05-RESEARCH.md §Open Implementation Choices §2 — weighted average by QA history depth):

```python
    def calculate_epic_score(self, task_scores: list[QualityScore]) -> float:
        """Weighted average: tasks with more QA history carry more weight. Default neutral = 85."""
        total_weight = sum(max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores)
        weighted_sum = sum(
            s.score * max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores
        )
        return weighted_sum / total_weight if total_weight > 0 else 85.0
```

**Skill 14 — isolated Pattern C SDK call** (AI-SPEC §3 Pattern C — no tools, no MCP, structural RISK-04 guarantee):

```python
    async def detect_improvement_triggers(
        self,
        qa_history: list[dict],
        scores: list[QualityScore],
    ) -> list[AutoImprovementTrigger]:
        """
        Isolated Haiku SDK call (Pattern C, AI-SPEC §3). No MCP. No tools.
        RISK-04 structural guarantee: allowed_tools=[] means the LLM literally
        cannot write to Linear regardless of what it attempts.
        """
        risk_summary = self._build_risk_summary(qa_history, scores)

        options = ClaudeAgentOptions(
            system_prompt=load_skill(".claude/skills/auto-improvement-triggers/SKILL.md"),
            allowed_tools=[],           # No tools — RISK-04 structural guarantee
            permission_mode="dontAsk",
            max_turns=3,                # Think + respond + done (AI-SPEC §4 Model Config)
            model="claude-haiku-4-5",   # Cheapest capable model for classification
            max_budget_usd=0.05,        # Hard cost ceiling per invocation
        )

        result_text = ""
        async for msg in query(
            prompt=(
                f"Analyze this risk summary and identify patterns warranting an "
                f"Auto-Improvement work item. Return suggestions as JSON array of "
                f"AutoImprovementTrigger objects. Do not create any Linear items yourself.\n\n"
                f"{risk_summary}"
            ),
            options=options,
        ):
            if isinstance(msg, ResultMessage):
                result_text = msg.result or ""

        # Parse and validate each trigger — filter out any with < 2 pattern_evidence refs
        import json
        triggers = []
        try:
            data = json.loads(result_text.strip().removeprefix("```json").removesuffix("```").strip())
            for item in data:
                t = AutoImprovementTrigger(**item)
                if len(t.pattern_evidence) >= 2:
                    triggers.append(t)
        except Exception as exc:
            logger.warning("AutoImprovementTrigger parse failed: %s", exc)
        return triggers
```

**Critical rules:**
- `allowed_tools=[]` and no `mcp_servers` in the skill 14 call — this is the structural RISK-04 guarantee (AI-SPEC §3 Pattern C).
- `calculate_quality_score()` and `get_priority_queue()` are synchronous `def` — NOT `async def`. Only `detect_improvement_triggers()` is `async def` (05-RESEARCH.md §Sub-System 3 "Global Orchestrator integration").
- `model="claude-haiku-4-5"` for skill 14 only (cheapest capable model); never Sonnet for this call.
- RISK-04 must appear in docstrings at class and method level — enforcement is documentation-visible, not just structural.

---

### `src/hsb/agents/work_item_orchestrator.py` (extend — delta only)

**Analog:** `src/hsb/agents/work_item_orchestrator.py` (Phase 3 PATTERNS.md — exact file; delta is: extend `assemble_system_prompt()` with skills 10+11, add Step 1 Enrich and Step 5 Store `client.query()` calls).

**Source specs:** `05-AI-SPEC.md` §3 Pattern A (full WIO session with skills 10+11); `05-RESEARCH.md` §Files Modified `work_item_orchestrator.py`; Phase 3 PATTERNS.md §`work_item_orchestrator.py` core pattern.

**Skill injection extension delta** (05-AI-SPEC.md §3 Pattern A `system_prompt` assembly — add two lines to existing `SKILL_FILES` list):

```python
# Phase 5 additions to the existing SKILL_FILES list in assemble_system_prompt()
SKILL_FILES = [
    ".claude/skills/task-orchestration/SKILL.md",             # skill 06 (existing)
    ".claude/skills/implementation/SKILL.md",                 # skill 02 (existing)
    ".claude/skills/qa-review/SKILL.md",                      # skill 03 (existing)
    ".claude/skills/git-pr-management/SKILL.md",              # skill 04 (existing)
    ".claude/skills/linear-system-of-record/SKILL.md",        # skill 05 (existing)
    ".claude/skills/knowledge-context-enrichment/SKILL.md",   # skill 10 [NEW Phase 5]
    ".claude/skills/knowledge-storage/SKILL.md",              # skill 11 [NEW Phase 5]
]
```

**Lifecycle step delta** (05-AI-SPEC.md §3 Pattern A — two new `client.query()` calls within the existing `async with ClaudeSDKClient(options=options) as client:` block):

```python
async with ClaudeSDKClient(options=options) as client:
    # [NEW] Step 1: Intelligence enrichment (skill 10) — before Builder
    await client.query(
        f"Enrich work item {work_item_id} from the Knowledge Store before implementation. "
        f"Work item context: {work_item_json}"
    )
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)

    # [EXISTING] Steps 2–4: Builder → Git → QA lifecycle (unchanged)
    await client.query(
        f"Execute the full build-git-qa cycle for {work_item_id}. "
        "Apply max_qa_cycles=3. Report final qa_status."
    )
    async for msg in client.receive_response():
        if isinstance(msg, ResultMessage):
            session_id = msg.session_id
            result_text = msg.result or ""
            if msg.stop_reason == "error_max_turns":
                raise RuntimeError(f"WIO hit max_turns for {work_item_id}")

    # [NEW] Step 5: Intelligence storage (skill 11) — after QA result
    await client.query(
        "Evaluate QA findings and implementation notes from this cycle. "
        "Apply skill 11 ingestion criteria. Write Knowledge Store entries only for "
        "insights that meet the signal threshold."
    )
    async for msg in client.receive_response():
        pass  # Side-effectful writes to knowledge/ — no return value needed
```

**Context monitoring delta** (AI-SPEC §4b.4 — add after each `receive_response()` drain):

```python
    if isinstance(msg, ResultMessage) and msg.usage:
        input_tokens = msg.usage.get("input_tokens", 0)
        if input_tokens > 120_000:  # 60% of 200K window
            logger.warning(
                "WIO context at %d tokens (%.0f%% of 200K) for %s",
                input_tokens, input_tokens / 2_000, work_item_id,
            )
```

**Critical rules:**
- `allowed_tools` remains `["Read", "Write", "Edit", "Bash", "Glob", "Grep"]` — no `"Agent"` (WORC-02).
- `knowledge_context` field in the Builder prompt is already defined in `AGENT-CONTRACTS.md §4` — no schema change needed (05-CONTEXT.md D-05).
- System prompt budget post Phase 5: ~6,250 tokens (~3% of 200K window) — safe per AI-SPEC §4b.4.
- If context pressure detected (>120K input_tokens), apply skill index fallback: replace full skill 10+11 content with one-line `Read` pointers (AI-SPEC §4b.4 Option 1).
- `max_turns=40` remains unchanged — do not lower for WIO.

---

### `src/hsb/agents/global_orchestrator.py` (extend — delta only)

**Analog:** `src/hsb/agents/global_orchestrator.py` (Phase 4 PATTERNS.md — `GlobalOrchestrator` class, `_check_epic_complete()` pattern for GORD-04, `get_ready_tasks()` method structure).

**Source specs:** `05-AI-SPEC.md` §Integration Touchpoints §1; `05-RESEARCH.md` §Files Modified `global_orchestrator.py`; Phase 4 PATTERNS.md §`global_orchestrator.py` core class and EPIC completion check patterns.

**New import delta** (05-AI-SPEC.md §Integration Touchpoints §1 — add at module top):

```python
from hsb.agents.risk_agent import RiskAgent
from hsb.agents.uat_agent import run_uat_and_validate
from hsb.contracts.risk import AutoImprovementTrigger
```

**New method: UAT-readiness detection** (mirrors `_check_epic_complete()` GORD-04 pattern from Phase 4 PATTERNS.md):

```python
async def _detect_uat_ready_user_stories(
    self, linear_state: dict
) -> list[dict]:
    """
    Detect User Stories where all child tasks are QA-approved and UAT is pending.
    Mirrors the GORD-04 EPIC-readiness check pattern (Phase 4 PATTERNS.md).
    Stateless — re-runs on every Global Orchestrator cycle.
    """
    uat_ready = []
    user_stories = [
        item for item in linear_state.values()
        if item.get("type") == "user_story"
    ]
    for us in user_stories:
        if us.get("uat_status") == "approved":
            continue  # Already approved — skip
        uat_cycle_count = us.get("uat_cycle_count", 0)
        if uat_cycle_count >= 3:
            logger.warning(
                "User Story %s has reached max UAT cycles (3) — escalating to human",
                us["id"],
            )
            continue
        children = await self._fetch_children(us["id"])
        if children and all(
            c.get("qa_status") == "approved" for c in children
        ):
            uat_ready.append(us)
    return uat_ready
```

**Modified method: `get_ready_tasks()` insertion sequence** (05-AI-SPEC.md §Integration Touchpoints §1 §Modified method block):

```python
async def get_ready_tasks(self) -> GlobalOrchestratorOutput:
    all_items = await self._fetch_all_items()

    if not all_items:
        return GlobalOrchestratorOutput(
            ready_tasks=[], is_backlog_empty=True, is_epic_ready=False,
            uat_dispatched=[], improvement_triggers=[],
        )

    # [EXISTING] Step 1: Dependency filter → raw_ready_tasks
    raw_ready = self._filter_ready_items(all_items)

    # [NEW] Step 2: Risk Agent priority queue — replaces raw_ready ordering
    risk_agent = RiskAgent()
    linear_state = {item["id"]: item for item in all_items}
    raw_task_ids = [t["id"] for t in raw_ready]
    priority_queue = risk_agent.get_priority_queue(raw_task_ids, linear_state)
    ready_tasks = priority_queue.items  # Risk-sorted; replaces unsorted list

    # [EXISTING] Step 3: EPIC readiness check (GORD-04)
    is_epic_ready = self._check_epic_complete(all_items)

    # [NEW] Step 4–7: UAT readiness detection and dispatch
    uat_dispatched: list[str] = []
    uat_ready = await self._detect_uat_ready_user_stories(linear_state)
    for us in uat_ready:
        uat_cycle = us.get("uat_cycle_count", 0) + 1
        uat_result = await run_uat_and_validate(
            user_story_id=us["id"],
            acceptance_criteria=us.get("acceptance_criteria", []),
            uat_cycle=uat_cycle,
        )
        uat_dispatched.append(us["id"])
        if uat_result.overall_status == "changes_required":
            await run_validated_linear_agent(
                operation="create_subtasks",
                payload={"parent_id": us["id"], "findings": [
                    s.finding for s in uat_result.scenarios if s.status == "fail"
                ]},
            )
        else:
            await run_validated_linear_agent(
                operation="update",
                payload={"id": us["id"], "uat_status": "approved",
                         "uat_cycle_count": uat_cycle},
            )

    # [NEW] Step 8: (Periodic) Auto-improvement trigger detection
    improvement_triggers: list[AutoImprovementTrigger] = []
    # Trigger detection called only when explicitly requested — see D-09 + RISK-04

    return GlobalOrchestratorOutput(
        ready_tasks=ready_tasks,
        is_backlog_empty=False,
        is_epic_ready=is_epic_ready,
        uat_dispatched=uat_dispatched,
        improvement_triggers=improvement_triggers,
    )
```

**Critical rules:**
- `GlobalOrchestrator` remains a pure Python class — no SDK session, no LLM (Phase 4 D-01 unchanged).
- UAT Agent dispatch is inline `await` — NOT a subprocess (05-RESEARCH.md §Open Implementation Choices §4).
- If multiple User Stories are UAT-ready, they are dispatched sequentially (one `await` after another) — acceptable at MVP scale.
- `GlobalOrchestratorOutput` gains two new optional fields: `uat_dispatched: list[str]` and `improvement_triggers: list[AutoImprovementTrigger]` (05-RESEARCH.md §Files Modified `global_orchestrator.py`).
- `asyncio.run()` is NEVER called inside this method — `get_ready_tasks()` is already `async def` and called with `await` from the CLI layer (AI-SPEC §4b.2 Pitfall).

---

### `src/hsb/contracts/uat.py` (model, CRUD)

**Analog:** `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md — `Literal` status enum, `extra="forbid"`, `model_config`, field-level validation).

**Source spec:** `05-AI-SPEC.md` §4b.1 `UATScenario` and `UATResult` Pydantic code (copy verbatim).

**Full contract models** (AI-SPEC §4b.1 — copy verbatim; do not add or remove fields):

```python
# src/hsb/contracts/uat.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class UATScenario(BaseModel):
    criterion_id: str = Field(..., description="Identifier matching the [AC-N] label in the prompt")
    criterion_text: str
    status: Literal["pass", "fail", "blocked"]
    evidence: str = Field(
        ...,
        description="Specific observable evidence from the PR or runtime — not a paraphrase",
        min_length=10,
    )
    finding: str | None = Field(
        None,
        description="Required when status=fail. Describes the gap vs. the criterion.",
    )

    model_config = {"extra": "forbid"}


class UATResult(BaseModel):
    user_story_id: str
    overall_status: Literal["approved", "changes_required", "blocked"]
    scenarios: list[UATScenario]
    scope_violations: list[str] = Field(
        default_factory=list,
        description="Findings outside explicit acceptance criteria — should be empty",
    )
    uat_cycle: int = Field(..., ge=1)

    model_config = {"extra": "forbid"}
```

**Critical rules:**
- `extra="forbid"` is mandatory on every model (Phase 2 PATTERNS.md rule — absent causes silent schema drift).
- `evidence` has `min_length=10` — enforces the "not a paraphrase" domain requirement (AI-SPEC §5 dimension B2).
- `uat_cycle` has `ge=1` — enforces the "cycle count is 1-indexed" invariant.
- `scope_violations` uses `default_factory=list` — must be empty in the happy path (UATA-04).
- Do NOT add fields not in `agents/AGENT-CONTRACTS.md §7` — downstream Global Orchestrator depends on exact mirror.

---

### `src/hsb/contracts/risk.py` (model, CRUD + arithmetic invariant)

**Analog:** `src/hsb/contracts/qa.py` (Phase 2 PATTERNS.md — `Literal` enforcement, `Field` constraints, `extra="forbid"`).

**Source spec:** `05-AI-SPEC.md` §4b.1 `QualityScore`, `PriorityQueue`, `AutoImprovementTrigger` code (copy verbatim).

**Full contract models** (AI-SPEC §4b.1 — copy verbatim):

```python
# src/hsb/contracts/risk.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class QualityScore(BaseModel):
    """Deterministic skill 12 output — no LLM involved."""
    work_item_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    qa_failures: int = 0
    fix_subtask_count: int = 0
    uat_failed: bool = False
    rework_cycles: int = 0
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class PriorityQueue(BaseModel):
    """Deterministic skill 13 output — sorted list of work item IDs."""
    items: list[str]
    scores: dict[str, float]

    model_config = {"extra": "forbid"}


class AutoImprovementTrigger(BaseModel):
    """Skill 14 LLM output. linear_state is always 'suggested' — never auto-created in Linear."""
    title: str
    description: str
    pattern_evidence: list[str] = Field(
        ..., description="Work item IDs or QA finding refs forming the pattern"
    )
    suggested_type: str
    linear_state: Literal["suggested"] = "suggested"

    model_config = {"extra": "forbid"}
```

**Arithmetic invariant test** (referenced in AI-SPEC §5 SC-4 — implement in test, not in Pydantic model itself):

```python
# In tests/unit/test_risk_agent_quality_score.py:
assert 100.0 - sum(score.score_breakdown.values()) == pytest.approx(score.score, abs=0.01)
```

**Critical rules:**
- `linear_state: Literal["suggested"] = "suggested"` — the `Literal` type enforces RISK-04 at parse time. Any attempt to set `linear_state = "created"` raises a `ValidationError`.
- `pattern_evidence` minimum length ≥ 2 is NOT enforced in the Pydantic model (no `min_length=2`) — it is enforced in `detect_improvement_triggers()` application code after parsing. Reason: Pydantic `min_length` on `list[str]` raises at parse time before the filter loop runs.
- `score` has `ge=0.0, le=100.0` — formula `max(0, score)` in `RiskAgent.calculate_quality_score()` prevents underflow; Pydantic catches any coding error.

---

### `src/hsb/contracts/knowledge.py` (model, CRUD + 8-field completeness + applicability constraint)

**Analog:** `src/hsb/contracts/builder.py` (Phase 2 PATTERNS.md — `extra="forbid"`, `Literal` type field, nested model with multiple optional and required fields).

**Source spec:** `05-RESEARCH.md` §Files Created `src/hsb/contracts/knowledge.py` block (copy verbatim).

**Full contract models** (05-RESEARCH.md §Files Created — copy verbatim; INTL-03 requires all 8 fields):

```python
# src/hsb/contracts/knowledge.py
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class KnowledgeEnrichmentOutput(BaseModel):
    work_item_id: str
    enrichment_report: dict  # matches AGENT-CONTRACTS.md §9 output structure
    retrieved_entries: list[str]  # file paths of Knowledge Store entries retrieved

    model_config = {"extra": "forbid"}


class KnowledgeStorageInput(BaseModel):
    """8 required fields per INTL-03. applicability must not be empty or 'all tasks'."""
    title: str
    type: Literal[
        "architecture", "qa", "implementation", "backlog",
        "risk", "pattern", "anti_pattern"
    ]
    context: str
    evidence: dict  # linear_issue, pr, files, qa_finding
    insight: str
    recommendation: str
    applicability: str = Field(
        ..., description="Non-empty, not 'all tasks' — must identify the scope condition"
    )
    date: str  # YYYY-MM-DD

    @field_validator("applicability")
    @classmethod
    def applicability_not_all_tasks(cls, v: str) -> str:
        if not v.strip() or v.strip().lower() in ("all tasks", "all", "n/a", "tbd"):
            raise ValueError(
                "applicability must identify specific conditions — not 'all tasks', empty, or 'n/a'"
            )
        return v

    model_config = {"extra": "forbid"}


class KnowledgeStorageOutput(BaseModel):
    stored: bool
    location: str  # knowledge/category/YYYY-MM-DD-slug.md
    entry_id: str
    was_duplicate: bool  # True if deduplication check prevented write

    model_config = {"extra": "forbid"}
```

**Critical rules:**
- All 8 `KnowledgeStorageInput` fields are required (no defaults) — INTL-03 mandates complete entries.
- The `applicability` validator enforces the domain requirement from AI-SPEC §5 dimension A2.
- `type` is a `Literal` with 7 values — must match the `CATEGORY_MAP` in `05-RESEARCH.md` §Knowledge Store Directory Structure.
- `evidence` is `dict` (not a typed sub-model) — matches AGENT-CONTRACTS.md §10; do not tighten to a typed model without updating the contract spec.

---

### `src/hsb/agents/_sdk_options.py` (utility — `make_options()` factory, G2 enforcement)

**Analog:** AI-SPEC §3 `ClaudeAgentOptions` blocks across Patterns A/B/C — extract into a shared factory with explicit G2 (`allowed_tools` never includes `"Agent"`) enforcement.

**Source spec:** `05-AI-SPEC.md` §3 Pattern A/B/C; AI-SPEC §6 G2 constraint.

**Factory pattern** (deduplicates the `ClaudeAgentOptions` construction across `uat_agent.py`, `risk_agent.py`, and `work_item_orchestrator.py`):

```python
# src/hsb/agents/_sdk_options.py
from __future__ import annotations
from claude_agent_sdk import ClaudeAgentOptions


_FORBIDDEN_TOOLS = {"Agent"}  # G2: sub-subagent dispatch forbidden (WORC-02)


def make_options(
    system_prompt: str,
    allowed_tools: list[str],
    permission_mode: str,
    max_turns: int,
    model: str,
    mcp_servers: dict | None = None,
    max_budget_usd: float | None = None,
    cwd: str | None = None,
    resume: str | None = None,
) -> ClaudeAgentOptions:
    """
    Factory for ClaudeAgentOptions. Enforces G2: 'Agent' must never appear
    in allowed_tools across any Phase 5 SDK call (WORC-02).
    """
    forbidden_in_call = _FORBIDDEN_TOOLS & set(allowed_tools)
    if forbidden_in_call:
        raise ValueError(
            f"G2 violation: {forbidden_in_call} must not appear in allowed_tools. "
            "Sub-subagent dispatch is forbidden by WORC-02."
        )

    kwargs: dict = dict(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,
        max_turns=max_turns,
        model=model,
    )
    if mcp_servers is not None:
        kwargs["mcp_servers"] = mcp_servers
    if max_budget_usd is not None:
        kwargs["max_budget_usd"] = max_budget_usd
    if cwd is not None:
        kwargs["cwd"] = cwd
    if resume is not None:
        kwargs["resume"] = resume

    return ClaudeAgentOptions(**kwargs)
```

---

### SKILL.md Files (6 new files, per-skill pattern)

**Analog:** `.claude/skills/task-orchestration/SKILL.md` (Phase 3 PATTERNS.md §`task-orchestration/SKILL.md` — SKILL.md frontmatter structure, `disable-model-invocation: true`).

**Source specs:** `05-AI-SPEC.md` §3 Recommended Project Structure SKILL.md table; `05-RESEARCH.md` §SKILL.md Files Created table; each corresponding `skills/NN-*.md` file (body content).

**SKILL.md frontmatter pattern** (copy from Phase 3 PATTERNS.md §`.claude/skills/task-orchestration/SKILL.md`, adapt per-skill):

Each SKILL.md file = YAML frontmatter block + exact body from `skills/NN-*.md` (no content changes, no paraphrasing).

```yaml
---
name: <skill-name>
description: <one-line description from skills/NN-*.md ## Objective>
disable-model-invocation: true
allowed-tools: <tool list or empty>
---
```

**Per-skill frontmatter values** (05-AI-SPEC.md §3 SKILL.md table):

| Destination | Source | `allowed-tools` value |
|-------------|--------|-----------------------|
| `.claude/skills/uat-validation/SKILL.md` | `skills/08-UAT-VALIDATION.md` | `Read Glob Grep Bash` |
| `.claude/skills/knowledge-context-enrichment/SKILL.md` | `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md` | `Read Glob Grep` |
| `.claude/skills/knowledge-storage/SKILL.md` | `skills/11-KNOWLEDGE-STORAGE.md` | `Write` |
| `.claude/skills/quality-scoring-risk-analysis/SKILL.md` | `skills/12-QUALITY-SCORING-RISK-ANALYSIS.md` | (empty — read-only risk reference) |
| `.claude/skills/adaptive-prioritization/SKILL.md` | `skills/13-ADAPTIVE-PRIORITIZATION.md` | (empty) |
| `.claude/skills/auto-improvement-triggers/SKILL.md` | `skills/14-AUTO-IMPROVEMENT-TRIGGERS.md` | (empty — skill 14 call has `allowed_tools=[]`) |

**Critical rules:**
- `disable-model-invocation: true` is mandatory on all 6 — these are skill reference files, not agent entry points.
- Body content is migrated verbatim from `skills/NN-*.md`. Never paraphrase or summarize.
- `allowed-tools:` with an empty value (not omitted) on skills 12, 13, 14 — omitting the key vs. empty value has different SDK auto-discovery semantics.

---

### `tests/integration/test_uat_agent.py` (test, request-response integration)

**Analog:** `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — `pytestmark = [pytest.mark.integration]`, real Linear workspace, `@pytest.mark.asyncio`, assertion on Linear state after agent run).

**Source spec:** `05-AI-SPEC.md` §Integration Test Strategy scenario 2 (UAT validation loop); `05-RESEARCH.md` §Validation Architecture Test Framework.

**Test structure pattern** (Phase 3 PATTERNS.md `test_orchestrator_e2e.py` structure):

```python
import pytest
from hsb.agents.uat_agent import run_uat_and_validate
from hsb.contracts.uat import UATResult

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_uat_validates_user_story_with_all_tasks_approved(
    linear_test_workspace,  # fixture from conftest.py
    uat_ready_user_story,   # fixture: User Story with all child tasks qa_status=approved
):
    """
    SC-3: UATResult.scenarios covers every AC.
    Real Linear workspace. Real hsb-test-fixture PR for evidence.
    """
    acceptance_criteria = uat_ready_user_story["acceptance_criteria"]
    result = await run_uat_and_validate(
        user_story_id=uat_ready_user_story["id"],
        acceptance_criteria=acceptance_criteria,
        uat_cycle=1,
    )
    assert isinstance(result, UATResult)
    # Coverage check: every [AC-N] has a matching scenario
    expected_ids = {f"AC-{i+1}" for i in range(len(acceptance_criteria))}
    actual_ids = {s.criterion_id for s in result.scenarios}
    assert actual_ids == expected_ids, (
        f"AC coverage gap: missing {expected_ids - actual_ids}"
    )
    assert result.scope_violations == []  # UATA-04
```

**Critical rules:**
- Use `pytestmark = [pytest.mark.integration]` — same marker as Phase 3/4 integration tests.
- Test teardown must clean up any Linear items created during the test (UAT fix subtasks created in `changes_required` scenario).
- No mocking — real Linear test workspace and real `hsb-test-fixture` GitHub repo (Phase 2 CONTEXT.md integration test strategy).

---

### `tests/integration/test_intelligence_enrichment.py` (test, file-I/O + integration)

**Analog:** `tests/integration/test_orchestrator_e2e.py` (Phase 3 PATTERNS.md — integration marker, real service, side-effect assertions on Linear state; extend with file-system side-effect assertions on `knowledge/`).

**Source spec:** `05-AI-SPEC.md` §Integration Test Strategy scenario 1 (Intelligence enrichment loop); test teardown must clean `knowledge/**/*_test_*.md` files.

**Test structure delta** (extends Phase 3 e2e pattern with `knowledge/` file assertions):

```python
@pytest.mark.asyncio
async def test_wio_step1_populates_knowledge_context(
    linear_test_workspace,
    test_task_with_knowledge_fixture,  # fixture: task in Linear + pre-seeded knowledge/qa/ entry
    tmp_knowledge_cleanup,             # fixture: removes files with _test_ slug after test
):
    """
    INTL-01: Enrichment retrieval runs before Builder; knowledge_context populated.
    Pre-condition: knowledge/qa/ contains one relevant entry for the test task domain.
    """
    from hsb.agents.work_item_orchestrator import run_work_item_orchestrator
    result = await run_work_item_orchestrator(
        work_item_id=test_task_with_knowledge_fixture["id"],
        work_item_json=json.dumps(test_task_with_knowledge_fixture),
    )
    # Assert enrichment report appears in Linear comment
    comments = await get_linear_comments(test_task_with_knowledge_fixture["id"])
    assert any("Enrichment Report" in c["body"] for c in comments)
```

---

### `tests/integration/test_risk_priority_queue.py` (test, CRUD + Hypothesis property-based)

**Analog:** `tests/unit/test_orchestrator.py` (Phase 3 PATTERNS.md — `pytest.raises(ValidationError)`, `pytest.mark.asyncio`); adds `hypothesis` property-based testing per AI-SPEC §5 RISK-01.

**Source spec:** `05-AI-SPEC.md` §Validation Architecture RISK-01/RISK-02 test entries; `05-RESEARCH.md` §Integration Test Strategy scenario 4.

**Hypothesis property-based pattern** (new to Phase 5 — not present in prior phases):

```python
from hypothesis import given, strategies as st
from hsb.agents.risk_agent import RiskAgent
from hsb.contracts.risk import QualityScore
import pytest


@given(
    qa_failures=st.integers(min_value=0, max_value=10),
    fix_subtasks=st.integers(min_value=0, max_value=10),
    uat_failed=st.booleans(),
    rework_cycles=st.integers(min_value=0, max_value=5),
)
def test_quality_score_deterministic_formula(
    qa_failures, fix_subtasks, uat_failed, rework_cycles
):
    """RISK-01: Formula produces correct penalties; score bounded [0, 100]."""
    agent = RiskAgent()
    work_item = {
        "id": "TEST-1", "fix_subtask_count": fix_subtasks,
        "qa_cycle_count": rework_cycles,
    }
    qa_history = [{"status": "changes_required"}] * qa_failures
    uat_results = [{"overall_status": "changes_required"}] if uat_failed else []

    score = agent.calculate_quality_score(work_item, qa_history, uat_results)

    assert 0.0 <= score.score <= 100.0
    expected = max(
        0.0,
        100.0 - 10 * qa_failures - 5 * fix_subtasks
        - (15 if uat_failed else 0) - 5 * rework_cycles,
    )
    assert score.score == pytest.approx(expected, abs=0.01)
    # Arithmetic invariant from AI-SPEC §5 SC-4
    assert 100.0 - sum(score.score_breakdown.values()) == pytest.approx(score.score, abs=0.01)
```

---

### `tests/integration/test_global_orchestrator_phase5.py` (extend — delta only)

**Analog:** `tests/integration/test_global_orchestrator_e2e.py` (Phase 4 PATTERNS.md — exact file; delta adds UAT-readiness detection and Risk Agent integration scenarios).

**Source spec:** `05-AI-SPEC.md` §Validation Architecture UATA-01 and SC-4; `05-RESEARCH.md` §Integration Test Strategy scenarios 2 and 4.

**Delta test functions** (add to existing Phase 4 integration test file):

```python
@pytest.mark.asyncio
async def test_uat_dispatched_when_all_child_tasks_approved(linear_test_workspace):
    """UATA-01: UAT dispatched when all child tasks QA-approved."""
    ...  # assert GlobalOrchestratorOutput.uat_dispatched contains User Story ID

@pytest.mark.asyncio
async def test_ready_tasks_sorted_by_risk_score(linear_test_workspace):
    """SC-4: GlobalOrchestratorOutput.ready_tasks is risk-sorted."""
    ...  # assert order matches risk_agent.get_priority_queue() for known input
```

---

## Shared Patterns

### OAuth2 Guard (apply to all agent entry points)

**Source:** Phase 1 PATTERNS.md `linear_agent.py` + AI-SPEC §3 OAuth2 Authentication section.
**Apply to:** `uat_agent.py` module-level startup, `risk_agent.py` module-level startup.

```python
import os
assert "ANTHROPIC_API_KEY" not in os.environ, (
    "ANTHROPIC_API_KEY is set — forbidden. Use CLAUDE_CODE_OAUTH_TOKEN only."
)
```

### `load_dotenv()` at module level (apply to all agent files)

**Source:** Phase 1 PATTERNS.md `linear_agent.py`; Phase 4 PATTERNS.md `global_orchestrator.py`.
**Apply to:** `uat_agent.py`, `risk_agent.py` (already in `work_item_orchestrator.py` and `global_orchestrator.py`).

```python
from dotenv import load_dotenv
load_dotenv()
```

### Pydantic `extra="forbid"` on every model (apply to all contracts)

**Source:** Phase 2 PATTERNS.md §Critical rules — "absent causes silent schema drift (PITFALLS.md Pitfall 4)".
**Apply to:** `UATScenario`, `UATResult`, `QualityScore`, `PriorityQueue`, `AutoImprovementTrigger`, `KnowledgeEnrichmentOutput`, `KnowledgeStorageInput`, `KnowledgeStorageOutput`.

```python
model_config = {"extra": "forbid"}
```

### `from __future__ import annotations` at top of every module

**Source:** Phase 4 PATTERNS.md (consistent across all contract and agent files).
**Apply to:** All new Python files in `src/hsb/contracts/` and `src/hsb/agents/`.

### `max_turns` always set explicitly (apply to all SDK calls)

**Source:** AI-SPEC §3 Common Pitfall 5.
**Values:** WIO=40 (unchanged), UAT=20, Risk-14=3.

```python
# Never omit max_turns — the SDK default is unlimited, enabling infinite loops on tool error.
```

### `ResultMessage.stop_reason` check on every SDK call

**Source:** AI-SPEC §3 Key Abstractions `ResultMessage` table.
**Apply to:** `uat_agent.py` `query()` loop, `risk_agent.py` skill 14 `query()` loop.

```python
if isinstance(msg, ResultMessage):
    if msg.stop_reason == "error_max_turns":
        raise RuntimeError(f"Agent hit max_turns for {work_item_id}")
```

### Integration test marker (apply to all integration tests)

**Source:** Phase 3 PATTERNS.md `test_orchestrator_e2e.py` — "real services, no mocking".
**Apply to:** All three new integration test files.

```python
pytestmark = [pytest.mark.integration]
```

---

## No Analog Found

All Phase 5 files have spec-derived analogs from prior phases. No file is truly novel:

| File | Role | Data Flow | Why Not "No Analog" |
|------|------|-----------|---------------------|
| `src/hsb/agents/_sdk_options.py` | utility | — | Extracts existing `ClaudeAgentOptions` blocks from AI-SPEC §3 into a factory; pattern is 100% spec-derived |
| Hypothesis tests in `test_risk_priority_queue.py` | test | CRUD | Hypothesis is a new test dependency but the test file structure follows Phase 3 PATTERNS.md unit test pattern |

The one genuinely new pattern in Phase 5 — the Hypothesis `@given` decorator for property-based testing — has no prior analog in Phases 1–4. The planner should use the `05-AI-SPEC.md §5` RISK-01 test entry as the canonical template.

---

## Metadata

**Analog search scope:** Phase 1–4 PATTERNS.md documents (canonical spec-derived analogs); `05-AI-SPEC.md` §3–4b (SDK patterns and Pydantic contracts); `05-RESEARCH.md` §Files Created/Modified, §Sub-System Designs, §Open Implementation Choices
**Files scanned:** 6 PATTERNS.md documents, 05-AI-SPEC.md, 05-RESEARCH.md, 05-CONTEXT.md, 03-CONTEXT.md, 04-CONTEXT.md, skills/08/10/12 (structure samples)
**Pattern extraction date:** 2026-05-06
