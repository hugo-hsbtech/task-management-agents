"""UATA-01 + D-01 integration test: Global Orchestrator dispatches UAT
when all child tasks QA-approved.

Real Linear test workspace; no mocking. Source-grep tests run without
fixtures and verify structural properties of the source file.
"""

import re

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_uat_dispatch_on_all_tasks_approved(
    linear_test_workspace,
    uat_ready_user_story,
):
    """UATA-01: Global Orchestrator dispatches UAT for User Stories with all
    child tasks QA-approved."""
    from hsb.agents.global_orchestrator import GlobalOrchestrator

    go = GlobalOrchestrator()
    output = await go.get_ready_tasks()
    assert uat_ready_user_story["id"] in output.uat_dispatched, (
        f"UATA-01 violated: User Story {uat_ready_user_story['id']} "
        "was not dispatched for UAT"
    )


def test_global_orchestrator_imports_phase5_dependencies():
    src = open("src/hsb/agents/global_orchestrator.py").read()
    assert "from hsb.agents.risk_agent import RiskAgent" in src, (
        "D-10 violated: Global Orchestrator must import RiskAgent"
    )
    assert "from hsb.agents.uat_agent import run_uat_and_validate" in src, (
        "D-01 violated: Global Orchestrator must import run_uat_and_validate"
    )


def test_global_orchestrator_has_uat_readiness_detector():
    src = open("src/hsb/agents/global_orchestrator.py").read()
    assert "_detect_uat_ready_user_stories" in src, (
        "UATA-01 violated: missing _detect_uat_ready_user_stories method"
    )


def test_global_orchestrator_has_g6_cycle_cap():
    src = open("src/hsb/agents/global_orchestrator.py").read()
    assert "uat_cycle_count >= 3" in src or "uat_cycle_count>= 3" in src, (
        "G6 violated: UAT cycle cap not enforced in Global Orchestrator"
    )


def test_g6_escalation_payload_uses_linear_mcp_create_comment_shape():
    """Issue 5 (checker): the G6 escalation
    ``run_validated_linear_agent(operation='create_comment', payload={...})``
    call MUST use the payload shape accepted by the Phase 1 LinearAgent
    contract for create_comment.

    Linear MCP ``linear_createComment`` tool expects ``issueId`` (camelCase)
    and ``body`` per the Linear GraphQL API. The Phase 1
    ``run_validated_linear_agent`` forwards ``payload`` dict keys verbatim
    to the MCP tool. This test asserts the GO source uses ``issueId``
    (NOT ``issue_id`` or ``id``) and ``body`` for the G6 escalation
    comment.
    """
    src = open("src/hsb/agents/global_orchestrator.py").read()
    m = re.search(
        r"uat_cycle_count >= 3.*?run_validated_linear_agent\([^)]*"
        r"operation\s*=\s*[\"']create_comment[\"']\s*,\s*payload\s*=\s*\{([^}]+)\}",
        src,
        re.DOTALL,
    )
    assert m, (
        "G6 escalation comment block not found; check that "
        "_detect_uat_ready_user_stories includes the create_comment escalation."
    )
    payload_body = m.group(1)
    assert '"issueId"' in payload_body or "'issueId'" in payload_body, (
        f"G6 payload shape mismatch: create_comment payload must use 'issueId' "
        f"(camelCase, matches Linear MCP linear_createComment tool). "
        f"Found payload body: {payload_body!r}"
    )
    assert '"body"' in payload_body or "'body'" in payload_body, (
        f"G6 payload shape mismatch: create_comment payload must include 'body'. "
        f"Found payload body: {payload_body!r}"
    )


def test_g6_escalation_payload_does_not_use_snake_case_issue_id():
    """G6 payload uses ``issueId`` (camelCase). ``issue_id`` (snake_case)
    is the Python-style key and is NOT what the Linear MCP tool accepts."""
    src = open("src/hsb/agents/global_orchestrator.py").read()
    m = re.search(
        r"operation\s*=\s*[\"']create_comment[\"']\s*,\s*payload\s*=\s*\{([^}]+)\}",
        src,
        re.DOTALL,
    )
    if m:
        payload_body = m.group(1)
        assert '"issue_id"' not in payload_body and "'issue_id'" not in payload_body, (
            f"G6 payload shape error: must use 'issueId' (camelCase) NOT 'issue_id' "
            f"(snake_case). Found: {payload_body!r}"
        )


def test_global_orchestrator_has_g10_uat_validator():
    src = open("src/hsb/agents/global_orchestrator.py").read()
    assert "_uat_passes_g10" in src, (
        "G10 violated: missing _uat_passes_g10 helper for UAT pre-persist validation"
    )
    assert "BANNED_RE" in src or "_UAT_BANNED_RE" in src, (
        "G10 B3 violated: missing banned-token regex"
    )
