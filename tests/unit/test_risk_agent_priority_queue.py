"""RISK-02: Priority queue sort order and tiebreaker."""

from hsb.agents.risk_agent import RiskAgent


def test_priority_queue_sorts_score_descending_then_updatedAt_ascending():
    agent = RiskAgent()
    linear_state = {
        "T-1": {
            "id": "T-1",
            "fix_subtask_count": 0,
            "qa_cycle_count": 0,
            "qa_history": [],
            "uat_results": [],
            "updatedAt": "2026-05-02",
        },
        "T-2": {
            "id": "T-2",
            "fix_subtask_count": 0,
            "qa_cycle_count": 0,
            "qa_history": [{"status": "changes_required"}],
            "uat_results": [],
            "updatedAt": "2026-05-01",
        },
        "T-3": {
            "id": "T-3",
            "fix_subtask_count": 0,
            "qa_cycle_count": 0,
            "qa_history": [{"status": "changes_required"}] * 5,
            "uat_results": [],
            "updatedAt": "2026-05-03",
        },
    }
    result = agent.get_priority_queue(["T-1", "T-2", "T-3"], linear_state)
    assert result.items == ["T-1", "T-2", "T-3"]
    assert result.scores["T-1"] == 100.0
    assert result.scores["T-2"] == 90.0
    assert result.scores["T-3"] == 50.0


def test_priority_queue_tiebreaker_by_updatedAt_ascending():
    agent = RiskAgent()
    linear_state = {
        "T-A": {
            "id": "T-A",
            "fix_subtask_count": 0,
            "qa_cycle_count": 0,
            "qa_history": [{"status": "changes_required"}],
            "uat_results": [],
            "updatedAt": "2026-05-02",
        },
        "T-B": {
            "id": "T-B",
            "fix_subtask_count": 0,
            "qa_cycle_count": 0,
            "qa_history": [{"status": "changes_required"}],
            "uat_results": [],
            "updatedAt": "2026-05-01",
        },
    }
    result = agent.get_priority_queue(["T-A", "T-B"], linear_state)
    assert result.items == ["T-B", "T-A"]
