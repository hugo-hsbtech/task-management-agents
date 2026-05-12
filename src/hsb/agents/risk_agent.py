"""Risk Agent (Phase 5).

Pure Python class implementing skills 12 (quality scoring) and 13 (adaptive
prioritization) with deterministic math — no LLM session required for these.
Skill 14 (Auto-Improvement Trigger detection) is the only async method;
it makes one isolated Claude Agent SDK ``query()`` call (Pattern C) with
``allowed_tools=[]`` and ``mcp_servers=None`` so the LLM physically cannot
write to Linear.

Defense-in-depth for RISK-04 ("Risk Agent must not write to Linear directly"):

1. STRUCTURAL  — skill 14 SDK call has ``allowed_tools=[]`` and no MCP servers.
2. PARSE-TIME  — :class:`AutoImprovementTrigger.linear_state` is
   ``Literal["suggested"]`` (rejected by pydantic if anything else).
3. IMPORT-TIME — this module does NOT import ``hsb.agents.linear_agent``.
4. RUNTIME     — :func:`linear_write_guard` (G5) on every LinearAgent write
   method inspects the call stack and denies any frame originating from
   ``risk_agent.py`` outside the operator-delegated path through
   ``global_orchestrator.approve_improvement_trigger()``.

G1 enforcement is centralized in
:func:`hsb.agents._sdk_options.assert_oauth2_only` (called from
:func:`make_options`). There is NO module-top OAuth2 assertion in this file.

G3 backstop is wired into the receive loop of
:meth:`RiskAgent.detect_improvement_triggers`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from claude_agent_sdk import ResultMessage, query
from dotenv import load_dotenv

from hsb.agents._sdk_options import assert_no_task_dispatch, make_options
from hsb.contracts.risk import (
    AutoImprovementTrigger,
    PriorityQueue,
    QualityScore,
)

load_dotenv()
logger = logging.getLogger(__name__)


def load_skill(path: str) -> str:
    """Load a SKILL.md file as a UTF-8 string for use as a system prompt."""
    return Path(path).read_text(encoding="utf-8")


class RiskAgent:
    """Pure Python for skills 12+13. One isolated SDK call for skill 14.

    Skills 12+13 are deterministic math — no LLM, no MCP, no SDK.
    RISK-04: No Linear writes without explicit delegation through Linear Agent.
    """

    def calculate_quality_score(
        self,
        work_item: dict[str, Any],
        qa_history: list[dict[str, Any]],
        uat_results: list[dict[str, Any]],
    ) -> QualityScore:
        """Skill 12 deterministic formula.

        score = max(0, 100 - 10*qa_failures - 5*fix_subtasks - (15 if uat_failed else 0)
                    - 5*rework_cycles)
        """
        qa_failures = sum(
            1 for qa in qa_history if qa.get("status") == "changes_required"
        )
        fix_subtask_count = work_item.get("fix_subtask_count", 0)
        uat_failed = any(
            r.get("overall_status") == "changes_required" for r in uat_results
        )
        rework_cycles = work_item.get("qa_cycle_count", 0)

        score = 100.0
        score -= 10 * qa_failures
        score -= 5 * fix_subtask_count
        score -= 15 if uat_failed else 0
        score -= 5 * rework_cycles
        score = max(0.0, score)

        breakdown = {
            "qa_failures_penalty": float(10 * qa_failures),
            "fix_subtask_penalty": float(5 * fix_subtask_count),
            "uat_failure_penalty": float(15 if uat_failed else 0),
            "rework_penalty": float(5 * rework_cycles),
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
        self, ready_tasks: list[str], linear_state: dict[str, Any]
    ) -> PriorityQueue:
        """Skill 13: sort tasks by score descending, tiebreak by ``updatedAt`` ascending."""
        scores: dict[str, float] = {}
        for tid in ready_tasks:
            item = linear_state.get(tid, {})
            qs = self.calculate_quality_score(
                item,
                item.get("qa_history", []),
                item.get("uat_results", []),
            )
            scores[tid] = qs.score
        sorted_ids = sorted(
            ready_tasks,
            key=lambda tid: (
                -scores[tid],
                linear_state.get(tid, {}).get("updatedAt", ""),
            ),
        )
        return PriorityQueue(items=sorted_ids, scores=scores)

    def calculate_epic_score(self, task_scores: list[QualityScore]) -> float:
        """Skill 12 EPIC aggregation: weighted average where weight =
        ``max(1, qa_failures + fix_subtask_count)``. Empty list → 85.0 default."""
        total_weight = sum(
            max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores
        )
        weighted_sum = sum(
            s.score * max(1, s.qa_failures + s.fix_subtask_count) for s in task_scores
        )
        return weighted_sum / total_weight if total_weight > 0 else 85.0

    @staticmethod
    def risk_level(score: float) -> Literal["low", "medium", "high"]:
        """Skill 12 risk thresholds: ≥75 low, ≥50 medium, else high."""
        if score >= 75:
            return "low"
        if score >= 50:
            return "medium"
        return "high"

    def _build_risk_summary(
        self, qa_history: list[dict[str, Any]], scores: list[QualityScore]
    ) -> str:
        """Plain-text summary the skill 14 LLM analyzes for patterns."""
        lines = ["Quality scores:"]
        for s in scores:
            lines.append(
                f"  {s.work_item_id}: score={s.score} qa_failures={s.qa_failures} "
                f"rework={s.rework_cycles}"
            )
        lines.append("\nQA history (recent findings):")
        for qa in qa_history[-20:]:
            lines.append(
                f"  {qa.get('work_item_id', '?')}: {qa.get('category', '?')} - "
                f"{qa.get('summary', '?')}"
            )
        return "\n".join(lines)

    async def detect_improvement_triggers(
        self,
        qa_history: list[dict[str, Any]],
        scores: list[QualityScore],
    ) -> list[AutoImprovementTrigger]:
        """Isolated Haiku SDK call (Pattern C, AI-SPEC §3). No MCP. No tools.

        RISK-04 structural: ``allowed_tools=[]`` means the LLM literally cannot
        write to Linear. G3 backstop: every received message is checked for
        runtime ``Task``-tool dispatch.
        """
        risk_summary = self._build_risk_summary(qa_history, scores)

        options = make_options(
            system_prompt=load_skill(
                ".claude/skills/auto-improvement-triggers/SKILL.md"
            ),
            allowed_tools=[],
            permission_mode="dontAsk",
            max_turns=3,
            model="claude-haiku-4-5",
            max_budget_usd=0.05,
        )
        assert options.allowed_tools == [], (
            "G4 violation: skill 14 allowed_tools must be empty"
        )
        assert getattr(options, "mcp_servers", None) in (None, {}), (
            "G4 violation: skill 14 mcp_servers must be None"
        )

        result_text = ""
        async for msg in query(
            prompt=(
                "Analyze this risk summary and identify patterns warranting an "
                "Auto-Improvement work item. Return suggestions as JSON array of "
                "AutoImprovementTrigger objects (fields: title, description, "
                "pattern_evidence (list of >=2 work item IDs), suggested_type). "
                "Do not create any Linear items yourself.\n\n"
                f"{risk_summary}"
            ),
            options=options,
        ):
            # G3 runtime backstop — catches an SDK regression that bypasses
            # allowed_tools at runtime. Propagates RuntimeError on violation.
            assert_no_task_dispatch(msg)
            if isinstance(msg, ResultMessage):
                if msg.stop_reason == "error_max_turns":
                    raise RuntimeError("RiskAgent skill 14 hit max_turns")
                result_text = msg.result or ""

        triggers: list[AutoImprovementTrigger] = []
        try:
            clean = (
                result_text.strip().removeprefix("```json").removesuffix("```").strip()
            )
            data = json.loads(clean) if clean else []
            for item in data if isinstance(data, list) else []:
                t = AutoImprovementTrigger(**item)
                if len(t.pattern_evidence) >= 2:
                    triggers.append(t)
        except Exception as exc:
            logger.warning("AutoImprovementTrigger parse failed: %s", exc)
        return triggers
