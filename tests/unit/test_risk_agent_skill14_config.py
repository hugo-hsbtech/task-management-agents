"""RISK-04 + G3 + G4 structural tests for the skill 14 SDK call site."""
import pytest


def _make_result(text: str = "[]", stop_reason: str = "end_turn"):
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
async def test_skill14_options_has_empty_tools_and_no_mcp(monkeypatch):
    from hsb.agents import risk_agent as ra

    captured: dict = {}
    original_make = ra.make_options

    def capture_make(**kw):
        captured.update(kw)
        return original_make(**kw)

    async def fake_query(prompt, options):
        captured["options"] = options
        yield _make_result("[]")

    monkeypatch.setattr(ra, "make_options", capture_make)
    monkeypatch.setattr(ra, "query", fake_query)

    agent = ra.RiskAgent()
    await agent.detect_improvement_triggers(qa_history=[], scores=[])

    assert captured["allowed_tools"] == [], (
        f"RISK-04 violated: skill 14 allowed_tools must be []; got {captured['allowed_tools']}"
    )
    assert captured.get("mcp_servers") is None, (
        f"RISK-04 violated: skill 14 mcp_servers must be None; got {captured.get('mcp_servers')}"
    )
    assert captured["model"] == "claude-haiku-4-5", (
        f"AI-SPEC §3 Pattern C: model must be claude-haiku-4-5; got {captured['model']}"
    )
    assert captured["max_turns"] == 3
    assert captured["max_budget_usd"] == 0.05


def test_risk_agent_module_has_no_import_time_oauth_assert():
    """G1 is enforced via :func:`_sdk_options.assert_oauth2_only` called from
    :func:`make_options`, NOT via a module-top assertion in ``risk_agent.py``."""
    src = open("src/hsb/agents/risk_agent.py").read()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("assert") and "ANTHROPIC_API_KEY" in stripped:
            raise AssertionError(
                "G1 must NOT be a module-top assert in risk_agent.py — it is "
                "enforced via _sdk_options.assert_oauth2_only(). Found: " + line
            )


def test_risk_agent_does_not_import_linear_agent():
    """RISK-04 structural: ``RiskAgent`` never imports ``linear_agent``."""
    src = open("src/hsb/agents/risk_agent.py").read()
    assert "from hsb.agents.linear_agent" not in src, (
        "RISK-04 violated: risk_agent.py imports linear_agent"
    )


def test_risk_agent_imports_assert_no_task_dispatch():
    """G3 backstop must be wired in ``risk_agent.py``."""
    src = open("src/hsb/agents/risk_agent.py").read()
    assert "assert_no_task_dispatch" in src, (
        "G3 violated: risk_agent.py does not import or call assert_no_task_dispatch — "
        "the runtime backstop for G2 (Task-tool dispatch) is not wired into the receive loop."
    )


def test_risk_agent_calls_assert_no_task_dispatch_in_receive_loop():
    """G3 backstop is called per-message, not just imported."""
    import re

    src = open("src/hsb/agents/risk_agent.py").read()
    # The receive loop spans multiple lines because the query(...) call is
    # multi-line. Locate the `async for msg in query(` opener, then scan
    # forward until the colon that closes the comprehension header, then
    # capture the indented body.
    opener = re.search(r"async for msg in query\(", src)
    assert opener, "Could not locate the SDK receive loop in risk_agent.py"
    # Find the matching closing paren + colon by scanning depth.
    i = opener.end()
    depth = 1
    while i < len(src) and depth > 0:
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    # Skip any whitespace/colon after the closing paren.
    while i < len(src) and src[i] in ":\n":
        i += 1
    # Capture until the next dedent (line starting with non-whitespace
    # or a new method/class).
    rest = src[i:]
    body_match = re.match(r"((?:[ \t]+\S[^\n]*\n|\s*\n)+)", rest)
    assert body_match, "Could not extract receive-loop body from risk_agent.py"
    loop_body = body_match.group(1)
    assert "assert_no_task_dispatch(msg)" in loop_body, (
        "G3 violated: assert_no_task_dispatch(msg) must be called inside the "
        "`async for msg in query(...)` loop in detect_improvement_triggers."
    )
