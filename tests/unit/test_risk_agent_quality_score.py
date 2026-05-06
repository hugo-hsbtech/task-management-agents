"""RISK-01 + arithmetic invariant tests for ``RiskAgent.calculate_quality_score``."""
import pytest
from hypothesis import given, strategies as st

from hsb.agents.risk_agent import RiskAgent
from hsb.contracts.risk import QualityScore


@given(
    qa_failures=st.integers(min_value=0, max_value=10),
    fix_subtasks=st.integers(min_value=0, max_value=10),
    uat_failed=st.booleans(),
    rework_cycles=st.integers(min_value=0, max_value=5),
)
def test_quality_score_deterministic_formula(
    qa_failures, fix_subtasks, uat_failed, rework_cycles
):
    agent = RiskAgent()
    work_item = {
        "id": "TEST-1",
        "fix_subtask_count": fix_subtasks,
        "qa_cycle_count": rework_cycles,
    }
    qa_history = [{"status": "changes_required"}] * qa_failures
    uat_results = [{"overall_status": "changes_required"}] if uat_failed else []

    score = agent.calculate_quality_score(work_item, qa_history, uat_results)

    expected = max(
        0.0,
        100.0
        - 10 * qa_failures
        - 5 * fix_subtasks
        - (15 if uat_failed else 0)
        - 5 * rework_cycles,
    )
    assert score.score == pytest.approx(expected, abs=0.01)
    assert 0.0 <= score.score <= 100.0
    # Arithmetic invariant: 100 - sum(penalties) == score, but only when score
    # is not clamped to 0. When clamped (raw < 0), the breakdown still records
    # the full unclamped penalties, which is the intended audit-trail behavior.
    raw = 100.0 - sum(score.score_breakdown.values())
    if raw >= 0.0:
        assert raw == pytest.approx(score.score, abs=0.01)
    else:
        assert score.score == 0.0
        assert raw < 0.0


def test_risk_level_thresholds():
    assert RiskAgent.risk_level(80.0) == "low"
    assert RiskAgent.risk_level(75.0) == "low"
    assert RiskAgent.risk_level(74.99) == "medium"
    assert RiskAgent.risk_level(60.0) == "medium"
    assert RiskAgent.risk_level(50.0) == "medium"
    assert RiskAgent.risk_level(49.99) == "high"
    assert RiskAgent.risk_level(0.0) == "high"


def test_calculate_epic_score_weighted_average():
    agent = RiskAgent()
    scores = [
        QualityScore(
            work_item_id="A",
            score=80.0,
            qa_failures=2,
            fix_subtask_count=0,
            uat_failed=False,
            rework_cycles=0,
            score_breakdown={},
        ),
        QualityScore(
            work_item_id="B",
            score=100.0,
            qa_failures=0,
            fix_subtask_count=0,
            uat_failed=False,
            rework_cycles=0,
            score_breakdown={},
        ),
    ]
    epic = agent.calculate_epic_score(scores)
    # weight(A) = max(1, 2) = 2; weight(B) = max(1, 0) = 1
    # weighted_sum = 80 * 2 + 100 * 1 = 260; total = 3 -> 86.6667
    assert epic == pytest.approx(86.6667, abs=0.01)


def test_calculate_epic_score_empty_returns_default_85():
    agent = RiskAgent()
    assert agent.calculate_epic_score([]) == 85.0
