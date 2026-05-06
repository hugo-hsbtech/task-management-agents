"""UATA-01..04 integration test — real Linear test workspace + hsb-test-fixture PR.

NOTE: The two async fixture-driven tests run against the REAL Linear test
workspace per Phase 2 CONTEXT.md integration test strategy. Do NOT mock the
SDK or Linear MCP. The remaining 8 tests are structural source-grep tests
that pass without fixtures.
"""
import pytest

from hsb.agents.uat_agent import run_uat_and_validate
from hsb.contracts.uat import UATResult

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_uat_validates_user_story_with_all_tasks_approved(
    linear_test_workspace,  # conftest.py fixture (Phase 2)
    uat_ready_user_story,  # conftest.py fixture (Phase 5 — to be added)
):
    """UATA-01 + UATA-02: UAT Agent validates User Story; scenarios cover every AC."""
    criteria = uat_ready_user_story["acceptance_criteria"]
    result = await run_uat_and_validate(
        user_story_id=uat_ready_user_story["id"],
        acceptance_criteria=criteria,
        uat_cycle=1,
    )
    assert isinstance(result, UATResult)
    expected = {f"AC-{i + 1}" for i in range(len(criteria))}
    actual = {s.criterion_id for s in result.scenarios}
    assert actual == expected, (
        f"UATA-02 coverage gap: expected {expected}, got {actual}"
    )


@pytest.mark.asyncio
async def test_uat_agent_produces_no_scope_violations(
    linear_test_workspace,
    uat_ready_user_story,
):
    """UATA-04: UAT Agent must not produce scope violations on a clean PR."""
    result = await run_uat_and_validate(
        user_story_id=uat_ready_user_story["id"],
        acceptance_criteria=uat_ready_user_story["acceptance_criteria"],
        uat_cycle=1,
    )
    assert result.scope_violations == [], (
        f"UATA-04 violated: scope violations found: {result.scope_violations}"
    )


def test_uat_agent_module_has_no_import_time_oauth_assert():
    """G1 is enforced via :func:`_sdk_options.assert_oauth2_only` called from
    :func:`make_options`, NOT via a module-top assertion in
    ``uat_agent.py``."""
    src = open("src/hsb/agents/uat_agent.py").read()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert") and "ANTHROPIC_API_KEY" in stripped:
            raise AssertionError(
                "G1 must NOT be a module-top assert in uat_agent.py — it is "
                "enforced via _sdk_options.assert_oauth2_only(). Found: " + line
            )


def test_uat_agent_does_not_import_linear_agent():
    """UATA-04 structural: UAT Agent never imports ``linear_agent``."""
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "from hsb.agents.linear_agent" not in src, (
        "UATA-04 violated: uat_agent.py imports linear_agent; "
        "Linear writes must go through Global Orchestrator (Plan 05-04)."
    )


def test_uat_agent_allowed_tools_excludes_write_edit_agent():
    """UATA-04 + G2 structural: ``allowed_tools`` is exactly Read/Glob/Grep/Bash."""
    import re

    src = open("src/hsb/agents/uat_agent.py").read()
    m = re.search(r"allowed_tools\s*=\s*\[([^\]]*)\]", src)
    assert m, "Could not find allowed_tools assignment in uat_agent.py"
    listing = m.group(1)
    assert '"Write"' not in listing and "'Write'" not in listing, (
        "UATA-04: Write must not appear"
    )
    assert '"Edit"' not in listing and "'Edit'" not in listing, (
        "UATA-04: Edit must not appear"
    )
    assert '"Agent"' not in listing and "'Agent'" not in listing, (
        "G2: Agent must not appear"
    )
    for required in ("Read", "Glob", "Grep", "Bash"):
        assert required in listing, (
            f"UATA-04: {required} must appear in allowed_tools"
        )


def test_uat_agent_uses_make_options_factory():
    """G2 chokepoint: UAT Agent constructs options via the factory."""
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "from hsb.agents._sdk_options import" in src
    assert "make_options" in src
    assert "make_options(" in src


def test_uat_agent_prompt_contains_scope_boundary_literal():
    """AI-SPEC §4b.3: SCOPE BOUNDARY literal must appear in the prompt."""
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "SCOPE BOUNDARY: Only validate the acceptance criteria listed below" in src, (
        "AI-SPEC §4b.3 violated: SCOPE BOUNDARY literal must appear in base_prompt"
    )


def test_uat_agent_max_retries_is_three():
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "MAX_RETRIES = 3" in src, "AI-SPEC §4b.1: MAX_RETRIES must be 3"


def test_uat_agent_max_turns_is_twenty():
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "max_turns=20" in src, "AI-SPEC §3 Pattern B: max_turns must be 20"


def test_uat_agent_model_is_sonnet():
    src = open("src/hsb/agents/uat_agent.py").read()
    assert 'model="claude-sonnet-4-6"' in src, (
        "AI-SPEC §4 Model Config: UAT requires claude-sonnet-4-6 for AC reasoning"
    )


def test_uat_agent_imports_g3_backstop():
    """G3 (AI-SPEC §6): UAT Agent must import ``assert_no_task_dispatch``
    from ``_sdk_options``."""
    src = open("src/hsb/agents/uat_agent.py").read()
    assert "from hsb.agents._sdk_options import" in src and (
        "assert_no_task_dispatch" in src
    ), (
        "G3 violated: uat_agent.py does not import assert_no_task_dispatch — "
        "runtime backstop for G2 (sub-subagent dispatch) is not wired into "
        "the receive loop."
    )


def test_uat_agent_calls_g3_backstop_in_receive_loop():
    """G3 must be called inside the SDK receive loop (per-message)."""
    import re

    src = open("src/hsb/agents/uat_agent.py").read()
    # Locate the multi-line `async for msg in query(...)` opener and walk the
    # parenthesis depth to find the colon, then capture the indented body.
    # The docstring also mentions ``query(`` so we anchor on the actual
    # statement (preceded by whitespace at line start).
    opener = re.search(r"\n[ \t]+async for msg in query\(", src)
    assert opener, "Could not locate the SDK receive loop in uat_agent.py"
    i = opener.end()
    depth = 1
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    while i < len(src) and src[i] in ":\n":
        i += 1
    rest = src[i:]
    body_match = re.match(r"((?:[ \t]+\S[^\n]*\n|\s*\n)+)", rest)
    assert body_match, "Could not extract receive-loop body from uat_agent.py"
    loop_body = body_match.group(1)
    assert "assert_no_task_dispatch(msg)" in loop_body, (
        "G3 violated: assert_no_task_dispatch(msg) must be called inside the "
        "`async for msg in query(...)` loop in run_uat_and_validate."
    )
