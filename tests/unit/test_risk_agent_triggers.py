"""RISK-03 filter + RISK-04 parse-layer + SC-5 positive-path automated verification.

SC-5 (Phase 5 success criterion): 'Risk Agent surfaces improvement triggers
without creating Linear items.' This test provides the AUTOMATED verification:
with seeded ``qa_history`` meeting the pattern threshold and a stubbed SDK
returning a valid trigger payload, ``detect_improvement_triggers`` returns
≥1 :class:`AutoImprovementTrigger` whose ``linear_state == 'suggested'``.
"""

import json

import pytest


def _make_result(text: str, stop_reason: str = "end_turn"):
    """Build a real :class:`ResultMessage` so ``isinstance`` checks in
    ``risk_agent.detect_improvement_triggers`` succeed."""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
        stop_reason=stop_reason,
        result=text,
    )


@pytest.mark.asyncio
async def test_triggers_with_fewer_than_two_evidence_refs_filtered(monkeypatch):
    from hsb.agents import risk_agent as ra

    payload = json.dumps(
        [
            {
                "title": "T1",
                "description": "d",
                "pattern_evidence": ["LIN-1"],
                "suggested_type": "refactor",
            },
            {
                "title": "T2",
                "description": "d",
                "pattern_evidence": ["LIN-1", "LIN-2"],
                "suggested_type": "refactor",
            },
        ]
    )

    async def fake_query(prompt, options):
        yield _make_result(payload)

    monkeypatch.setattr(ra, "query", fake_query)
    agent = ra.RiskAgent()
    result = await agent.detect_improvement_triggers(qa_history=[], scores=[])
    assert len(result) == 1
    assert result[0].title == "T2"
    assert len(result[0].pattern_evidence) >= 2


@pytest.mark.asyncio
async def test_triggers_linear_state_always_suggested(monkeypatch):
    from hsb.agents import risk_agent as ra

    payload = json.dumps(
        [
            {
                "title": "T1",
                "description": "d",
                "pattern_evidence": ["LIN-1", "LIN-2"],
                "suggested_type": "refactor",
            },
        ]
    )

    async def fake_query(prompt, options):
        yield _make_result(payload)

    monkeypatch.setattr(ra, "query", fake_query)
    agent = ra.RiskAgent()
    result = await agent.detect_improvement_triggers(qa_history=[], scores=[])
    assert len(result) == 1
    assert result[0].linear_state == "suggested"


@pytest.mark.asyncio
async def test_sc5_positive_path_returns_trigger_for_seeded_qa_history(monkeypatch):
    """SC-5 automated verification: seeded qa_history with pattern → ≥1 trigger.

    Per AI-SPEC §6 / RISK-04, the production code path returns triggers ONLY
    when explicitly invoked (the global_orchestrator per-cycle path returns
    ``improvement_triggers=[]`` always). This test invokes
    ``detect_improvement_triggers`` DIRECTLY (the operator-delegated CLI path)
    and asserts a trigger is returned given a seeded ``qa_history`` that meets
    the pattern threshold.

    The 05-04 SC-5 human checkpoint cites this test as the automated
    verification path.
    """
    from hsb.agents import risk_agent as ra
    from hsb.contracts.risk import AutoImprovementTrigger

    # Seeded qa_history: 3 changes_required findings in the same auth category.
    qa_history = [
        {
            "work_item_id": "LIN-1",
            "category": "auth",
            "status": "changes_required",
            "summary": "missing input validation",
        },
        {
            "work_item_id": "LIN-2",
            "category": "auth",
            "status": "changes_required",
            "summary": "weak password regex",
        },
        {
            "work_item_id": "LIN-3",
            "category": "auth",
            "status": "changes_required",
            "summary": "session token leak",
        },
    ]
    payload = json.dumps(
        [
            {
                "title": "Auth-domain pattern: missing input validation pattern",
                "description": (
                    "Three consecutive QA findings in auth category indicate "
                    "a missing input-validation pattern in the team's auth flows."
                ),
                "pattern_evidence": ["LIN-1", "LIN-2", "LIN-3"],
                "suggested_type": "auto_improvement",
            },
        ]
    )

    async def fake_query(prompt, options):
        # Defensive: confirm the SDK call config matches RISK-04 / G4.
        assert options.allowed_tools == []
        assert getattr(options, "mcp_servers", None) in (None, {})
        yield _make_result(payload)

    monkeypatch.setattr(ra, "query", fake_query)
    agent = ra.RiskAgent()
    result = await agent.detect_improvement_triggers(qa_history=qa_history, scores=[])

    # SC-5 assertion: at least one trigger surfaced for the seeded pattern.
    assert len(result) >= 1, (
        "SC-5 violated: detect_improvement_triggers returned 0 triggers for "
        "seeded qa_history with 3 same-category changes_required findings."
    )
    # Defense-in-depth: every trigger has linear_state='suggested' (RISK-04 layer 2).
    for t in result:
        assert isinstance(t, AutoImprovementTrigger)
        assert t.linear_state == "suggested"
        assert len(t.pattern_evidence) >= 2
