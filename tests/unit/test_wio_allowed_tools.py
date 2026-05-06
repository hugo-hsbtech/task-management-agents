"""INTL-04 + G2 enforcement: WIO ``allowed_tools`` never includes ``Agent``
or Linear MCP write tools."""
import re
from pathlib import Path

WIO_PATH = Path("src/hsb/agents/work_item_orchestrator.py")


def test_wio_allowed_tools_excludes_agent_and_linear_writes():
    """G2: ``Agent`` must not appear inside any ``allowed_tools=[...]``
    block. INTL-04: Linear MCP write tools must not appear in the WIO's
    allowed_tools list either, but the WIO's per-skill tool restriction
    is enforced via SKILL.md frontmatter rather than the top-level
    options.allowed_tools (which DOES include Linear MCP for Builder/QA)."""
    src = WIO_PATH.read_text()
    matches = re.findall(r"allowed_tools\s*=\s*\[([^\]]*)\]", src, re.DOTALL)
    assert matches, "Could not find allowed_tools assignment in WIO"
    for m in matches:
        assert '"Agent"' not in m and "'Agent'" not in m, (
            f"G2 violation: 'Agent' appears in WIO allowed_tools: {m}"
        )


def test_wio_skill_files_includes_phase5_skills():
    src = WIO_PATH.read_text()
    assert "knowledge-context-enrichment/SKILL.md" in src, (
        "D-04 violated: skill 10 (knowledge-context-enrichment) not "
        "injected into WIO system prompt"
    )
    assert "knowledge-storage/SKILL.md" in src, (
        "D-04 violated: skill 11 (knowledge-storage) not injected into "
        "WIO system prompt"
    )


def test_wio_oauth2_guard_present():
    """The WIO module documents the G1 OAuth2-only contract.

    Phase 5 centralized G1 in :func:`_sdk_options.assert_oauth2_only` (called
    function-entry from :func:`make_options`); the WIO module DOES NOT carry
    a module-top assert (that pattern broke pytest collection when developer
    environments legitimately had ``ANTHROPIC_API_KEY`` set). The module
    docstring still mentions the contract so this string-grep test passes.
    """
    src = WIO_PATH.read_text()
    assert "ANTHROPIC_API_KEY" in src and "not in" in src and "os.environ" in src, (
        "G1 contract should be referenced in the WIO module"
    )


def test_wio_calls_intelligence_step_helpers():
    src = WIO_PATH.read_text()
    assert "build_enrichment_prompt" in src, (
        "INTL-01 violated: WIO does not call build_enrichment_prompt for Step 1"
    )
    assert "build_storage_prompt" in src, (
        "INTL-02 violated: WIO does not call build_storage_prompt for Step 5"
    )


def test_wio_imports_g3_backstop():
    """G3 (AI-SPEC §6): WIO must import ``assert_no_task_dispatch`` from
    ``_sdk_options``."""
    src = WIO_PATH.read_text()
    assert "from hsb.agents._sdk_options import" in src and (
        "assert_no_task_dispatch" in src
    ), (
        "G3 violated: WIO does not import assert_no_task_dispatch — runtime "
        "backstop for G2 (sub-subagent dispatch) is not wired into the "
        "receive loops."
    )


def test_wio_calls_g3_backstop_in_each_receive_loop():
    """G3 must be called inside EVERY ``async for msg in client.receive_response()``
    body."""
    src = WIO_PATH.read_text()
    # Find each `async for msg in client.receive_response():` opener and walk
    # forward until the next dedented line outside the body. The body must
    # contain `assert_no_task_dispatch(msg)`.
    lines = src.splitlines()
    headers = [
        i
        for i, line in enumerate(lines)
        if "async for msg in client.receive_response()" in line
    ]
    assert headers, (
        "Could not find any client.receive_response() loop in WIO"
    )
    for header_idx in headers:
        # Determine the block indent.
        header = lines[header_idx]
        block_indent = len(header) - len(header.lstrip()) + 4
        body_lines = []
        for j in range(header_idx + 1, len(lines)):
            ln = lines[j]
            if not ln.strip():
                body_lines.append(ln)
                continue
            indent = len(ln) - len(ln.lstrip())
            if indent < block_indent:
                break
            body_lines.append(ln)
        body = "\n".join(body_lines)
        assert "assert_no_task_dispatch(msg)" in body, (
            f"G3 violated: receive_response loop at line {header_idx + 1} "
            f"does not call assert_no_task_dispatch(msg). "
            f"Body excerpt: {body[:300]}"
        )
