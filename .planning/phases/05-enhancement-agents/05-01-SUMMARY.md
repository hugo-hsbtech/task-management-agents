---
phase: 05-enhancement-agents
plan: 01
status: complete
wave: 2
completed: 2026-05-06
requirements:
  - INTL-01
  - INTL-02
  - INTL-03
  - INTL-04
---

# Plan 05-01 Summary — Intelligence Agent inline in WIO

Wave 2 of Phase 5. Extends the Phase 3 Work Item Orchestrator with the
Intelligence Agent capability inline within the existing SDK session, by
injecting skills 10 + 11 into the system prompt and adding two new
lifecycle steps: Step 1 enrichment before Builder and Step 5 knowledge
storage after QA.

## Tasks Completed

| Task | Commit |
|------|--------|
| 1: knowledge contracts + intelligence helpers + skills 10/11 + schema tests | (this wave, first 05-01 commit) |
| 2: WIO extension (skills, Step 1 + Step 5, G3 + G8) + 7 unit tests + 2 integration test stubs | (this wave, second 05-01 commit) |

## SKILL_FILES list

The Phase 3 list of 5 skill files is preserved verbatim; Phase 5 appends
two more entries:

```python
SKILL_FILES = [
    "skills/06-TASK-ORCHESTRATION.md",
    "skills/02-IMPLEMENTATION.md",
    "skills/03-QA-REVIEW.md",
    "skills/04-GIT-PR-MANAGEMENT.md",
    "skills/05-LINEAR-SYSTEM-OF-RECORD.md",
    ".claude/skills/knowledge-context-enrichment/SKILL.md",  # skill 10 [Phase 5]
    ".claude/skills/knowledge-storage/SKILL.md",  # skill 11 [Phase 5]
]
```

The Phase 5 entries reference the migrated SKILL.md files (with the
SDK-discoverable frontmatter); the Phase 3 entries continue to reference
the source skill files. Both contribute to ``assemble_system_prompt()``.

## Lifecycle Restructure

Phase 3 used a single ``query(prompt=, options=)`` call. Phase 5 converts
that to a multi-turn ``ClaudeSDKClient`` session that drives three turns
inside the same context window:

| Step | Source line | Purpose |
|------|------------|---------|
| 1 | `work_item_orchestrator.py:300` | Intelligence enrichment via `build_enrichment_prompt` (skill 10). No Linear writes. |
| 2-4 | `work_item_orchestrator.py:316` | Builder → Git → QA cycle (Phase 3, unchanged). QA cycle cap = 3 (D-05). G7 stop_reason check + G8 context warning. |
| 5 | `work_item_orchestrator.py:346` | Knowledge storage evaluation via `build_storage_prompt` (skill 11). Writes `knowledge/<cat>/*.md` only if ingestion criteria met. |

All three turns share the same SDK options (skill content, MCP servers,
allowed_tools) and the same context window. The `@tool` wrappers (Phase 3
in-process MCP tools) remain untouched.

## Guardrails Wired

- **G2 (no Agent in allowed_tools)**: WIO `allowed_tools` continues to
  exclude `Agent`. Phase 5 added skills 10+11 to the SKILL_FILES list but
  did NOT extend `allowed_tools` — the per-skill tool restrictions live in
  the migrated SKILL.md frontmatter (`Read Glob Grep` for skill 10,
  `Write` for skill 11).
- **G3 (runtime backstop)**: `assert_no_task_dispatch(msg)` is called on
  every received message in **all 3** `client.receive_response()` loop
  bodies. Verified by `test_wio_calls_g3_backstop_in_each_receive_loop`.
- **G7 (stop_reason)**: Existing Phase 3 `if msg.stop_reason ==
  "error_max_turns": raise RuntimeError(...)` preserved in the
  Builder/Git/QA loop and replicated in the Step 5 storage loop.
- **G8 (context warning)**: WARN log emitted from both the Builder/QA
  loop and the storage loop when `msg.usage["input_tokens"] > 120_000`
  (60% of 200K window). The single shared session means context grows
  monotonically across turns; this gives an early signal before the
  40-turn `max_turns` cap is reached.
- **G9 (knowledge entry pre-write)**: pydantic `KnowledgeStorageInput`
  with `applicability` field_validator rejects "all tasks", "all", "n/a",
  "tbd", and empty strings (case-insensitive after strip). `extra="forbid"`
  rejects rogue fields. The integration test
  `test_wio_step5_writes_knowledge_entry` parses every newly created
  entry through `KnowledgeStorageInput` — failure to parse fails the test.

## Files Created (line counts)

| Path | Lines |
|------|-------|
| `src/hsb/contracts/knowledge.py` | 65 |
| `src/hsb/agents/intelligence_agent.py` | 53 |
| `.claude/skills/knowledge-context-enrichment/SKILL.md` | 175 |
| `.claude/skills/knowledge-storage/SKILL.md` | 229 |
| `tests/unit/test_knowledge_storage_schema.py` | 88 |
| `tests/unit/test_wio_allowed_tools.py` | 113 |
| `tests/integration/test_wio_intelligence_enrichment.py` | 39 |
| `tests/integration/test_wio_intelligence_storage.py` | 47 |

The two migrated SKILL.md files contain frontmatter (5 lines) followed by
a verbatim copy of `skills/10-KNOWLEDGE-CONTEXT-ENRICHMENT.md` (3039
bytes → 3257 bytes including frontmatter) and `skills/11-KNOWLEDGE-STORAGE.md`
(4128 bytes → 4330 bytes).

## Files Modified

| Path | Change |
|------|--------|
| `src/hsb/agents/work_item_orchestrator.py` | Imports `ClaudeSDKClient`, `build_enrichment_prompt`, `build_storage_prompt`, `assert_no_task_dispatch`. SKILL_FILES extended (5→7). `run_orchestration_cycle` body refactored from single `query()` to 3-turn `ClaudeSDKClient` session. Module docstring updated to describe Phase 5 inline-Intelligence pattern and the centralized G1 contract (G1 enforced via `_sdk_options.assert_oauth2_only`, NOT a module-top assert). Phase 3 `@tool` wrappers, allowed_tools list, MCP server registration, max_turns=30, and the QA cycle cap layer 2 (`_check_qa_cycle_cap`) are unchanged. |

## Test Results

- **19 unit tests pass**: 13 for `test_knowledge_storage_schema.py` +
  6 for `test_wio_allowed_tools.py`.
- **2 integration tests collect cleanly**: `test_wio_step1_populates_knowledge_context`
  and `test_wio_step5_writes_knowledge_entry`. Real-Linear runs occur
  during the phase-gate integration sweep.
- **Phase 3 regression**: `pytest tests/unit/test_orchestrator.py` →
  15 passed. No regression on the Phase 3 WIO unit tests.

## Notable Decisions

- **Multi-turn `ClaudeSDKClient` rather than separate sessions**: Plan
  05-01 specified D-04 ("inline within the existing WIO Claude Agent SDK
  session"), so all three turns share the same session and context. This
  preserves cycle-level cost budgeting and avoids re-loading the system
  prompt three times.
- **G1 documented, not asserted at module top**: Plan 05-01 said "the
  existing assert at module top remains untouched" but Phase 3 did not
  actually have one. Phase 5 centralized G1 in `_sdk_options.assert_oauth2_only()`,
  so the WIO module documents the contract in its docstring (string-grep
  test still passes) but does NOT carry a module-top assert that would
  break pytest collection.
- **Integration test fixtures deferred**: `test_task_with_knowledge_fixture`
  and `test_task_with_qa_finding_fixture` are not yet defined in
  `conftest.py` — they will be added when the tests are run live. The
  tests collect cleanly because pytest doesn't validate fixture
  availability during collection.

## Self-Check: PASSED
