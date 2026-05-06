---
phase: 03-work-item-orchestrator-and-single-cycle-mvp
plan: 02
status: complete
completed: 2026-05-06
self_check: PASSED
---

# Plan 03-02 — Work Item Orchestrator Implementation

## Objective

Implement the Work Item Orchestrator: a single Claude Agent SDK session
driving one Linear task through its full lifecycle (Linear read → Builder
→ Git → QA → fix loop → done) using sequential tool use within ONE context
window. No sub-agent dispatch (CONTEXT.md D-01). All five Phase 3 skill
files are read at startup and injected into the system prompt. Phase 2
agent modules are exposed as in-process MCP tools via
``create_sdk_mcp_server`` + ``@tool``.

## Files Created

| Path | LOC | Purpose |
|------|-----|---------|
| `src/hsb/agents/work_item_orchestrator.py` | 299 | Single-session orchestrator |

## Files Modified

| Path | Notes |
|------|-------|
| `tests/unit/test_orchestrator.py` | Wave 0 stubs flipped to real assertions; 4 new behavior tests added |

## Key Files (created/modified)

- `src/hsb/agents/work_item_orchestrator.py`
- `tests/unit/test_orchestrator.py`

## Verification Results

| Check | Target | Actual | Status |
|-------|--------|--------|--------|
| File size | >= 150 lines | 299 lines | PASS |
| Unit tests pass | all | 15/15 PASSED | PASS |
| `assemble_system_prompt()` length | > 5000 chars | 14,405 chars | PASS |
| @tool wrappers (count of canonical envelope returns) | >= 4 | 4 actual + 1 docstring example = 5 grep hits | PASS |
| `AgentDefinition` import / use | absent | absent (AST walk + grep) | PASS |
| `agents=` kwarg in ClaudeAgentOptions | absent | absent (AST walk over `ClaudeAgentOptions(...)`) | PASS |
| `max_turns=30` | present | present | PASS |
| `permission_mode="acceptEdits"` | present | present | PASS |
| 4 `mcp__agents__run_*` in allowed_tools | yes | yes (run_linear_op, run_builder, run_git, run_qa) | PASS |
| >= 4 `mcp__linear__*` in allowed_tools | yes | 4 (get_issue, list_issues, update_issue, create_comment) | PASS |
| `_check_qa_cycle_cap` posts 'Max QA cycles reached' | yes | yes (mocked unit test verified) | PASS |
| `disable-model-invocation: true` in migrated SKILL.md | yes (Plan 01) | yes | PASS |

### Pytest evidence

```
tests/unit/test_orchestrator.py::test_no_subagent_dispatch_in_options PASSED
tests/unit/test_orchestrator.py::test_no_subagent_dispatch PASSED
tests/unit/test_orchestrator.py::test_qa_cycle_cap_model_validator PASSED
tests/unit/test_orchestrator.py::test_qa_cycle_cap PASSED
tests/unit/test_orchestrator.py::test_qa_cycle_cap_safety_net_posts_comment PASSED
tests/unit/test_orchestrator.py::test_qa_cycle_cap_safety_net_silent_below_cap PASSED
tests/unit/test_orchestrator.py::test_tool_wrapper_requires_full_issue_content PASSED
tests/unit/test_orchestrator.py::test_full_context_in_tool_calls PASSED
tests/unit/test_orchestrator.py::test_all_tools_return_canonical_envelope PASSED
tests/unit/test_orchestrator.py::test_assemble_system_prompt_loads_all_skills PASSED
tests/unit/test_orchestrator.py::test_orchestration_options_lists_required_tools PASSED
tests/unit/test_orchestrator.py::test_valid_orch_output_passes PASSED
tests/unit/test_orchestrator.py::test_invalid_lifecycle_status_fails PASSED
tests/unit/test_orchestrator.py::test_orch_output_extra_field_rejected PASSED
tests/unit/test_orchestrator.py::test_orch_input_extra_field_rejected PASSED
15 passed in 0.46s
```

## Skill Files Loaded

- `skills/06-TASK-ORCHESTRATION.md` (meta-skill, first by intentional ordering per CONTEXT.md "Claude's Discretion")
- `skills/02-IMPLEMENTATION.md`
- `skills/03-QA-REVIEW.md`
- `skills/04-GIT-PR-MANAGEMENT.md`
- `skills/05-LINEAR-SYSTEM-OF-RECORD.md`

Combined system prompt size: **14,405 chars** (well below 200K context budget;
context-budget validation will be confirmed live in Plan 04 per D-02).

## Pitfalls Encountered & Resolution

1. **Pitfall: ``@tool`` decorator wraps the function in an ``SdkMcpTool`` object,
   not a function.** ``inspect.getsource(run_builder_tool)`` raises ``TypeError``.
   **Resolution:** tests use ``getattr(run_builder_tool, "handler", run_builder_tool)``
   to access the underlying coroutine. The schema is exposed on
   ``SdkMcpTool.input_schema``.

2. **Pitfall: A naive substring check ``"agents="`` in the function source
   fires on docstring text like "Phase 2 agents as @tool wrappers".**
   **Resolution:** the WORC-02 test now uses ``ast.walk`` to inspect every
   ``ClaudeAgentOptions(...)`` ``Call`` node and explicitly check that no
   keyword argument is named ``agents``. ``AgentDefinition`` references are
   detected via ``ast.Name`` walk.

3. **Pitfall 4 (RESEARCH.md):** ``@tool`` returns must be ``{"content":
   [{"type": "text", "text": ...}]}``. **Resolution:** all four wrappers use
   ``result.model_dump_json()`` to serialize the Pydantic output to a JSON
   string, then wrap in the canonical envelope. A regression test
   (``test_all_tools_return_canonical_envelope``) counts the literal string
   in the module source to enforce this.

## Deviations

None. Implementation follows 03-PATTERNS.md verbatim with two test-only
adaptations described under "Pitfalls Encountered" above.

## Self-Check: PASSED

- All 15 unit tests pass.
- AST inspection confirms no sub-agent dispatch (D-01).
- All four @tool wrappers return the canonical envelope shape.
- Layer 2 cycle-cap safety net posts the required Linear escalation comment.
- File size (299 lines) >> 150 line minimum.

## Commits

```
c0b197e feat(03-02): Work Item Orchestrator single-session implementation
```

## Hand-off to Plan 03-03

Plan 03-03 wires three new Typer subcommands (`run-next-step`, `show-state`,
`show-next-action`) into `src/hsb/cli/main.py` and ships `run_loop.py` at the
repo root. The Plan-03-03 unit stubs in `tests/unit/test_cli.py` (Plan 01)
must flip from "Wave 0 stub" to real assertions:

- `run_next_step` synchronous Typer handler MUST call
  ``asyncio.run(run_orchestration_cycle(work_item_id))`` (already importable
  from this plan's deliverable).
- `show_state` and `show_next_action` operate read-only against Linear via
  `run_validated_linear_agent`.
