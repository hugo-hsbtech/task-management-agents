---
phase: 01-foundation-and-linear-integration
plan: 01
subsystem: scaffolding
tags: [pyproject, mcp, knowledge-store, skills, linear]

requires: []
provides:
  - Python `src/` layout package skeleton (`hsb`) with subdirs `agents/`, `contracts/`, `cli/`
  - `pyproject.toml` with pinned deps (claude-agent-sdk>=0.1.73, pydantic>=2, typer, rich, python-dotenv) and `hsb` entry point
  - `.mcp.json` registering the Linear MCP server with lowercase `"linear"` key
  - `.gitignore` and `.env.example` covering all secret-bearing files
  - Knowledge Store directory tree: 7 categories under `knowledge/` each with `.gitkeep`
  - Linear skill auto-discoverable at `.claude/skills/linear-system-of-record/SKILL.md` with `disable-model-invocation: true`
affects: [01-02, 01-03, 01-04, 01-05, all phase 2+ plans]

tech-stack:
  added:
    - claude-agent-sdk>=0.1.73
    - pydantic>=2.0
    - typer>=0.12
    - rich>=13.0
    - python-dotenv>=1.0
    - hatchling (build backend)
    - pytest, pytest-asyncio (dev)
  patterns:
    - src/ layout (D-03)
    - pyproject.toml only — no requirements.txt (D-05)
    - mcp-remote command pattern for Linear OAuth
    - SDK-discoverable skill format with disable-model-invocation gate

key-files:
  created:
    - pyproject.toml
    - .mcp.json
    - .gitignore
    - .env.example
    - src/hsb/__init__.py
    - src/hsb/agents/__init__.py
    - src/hsb/contracts/__init__.py
    - src/hsb/cli/__init__.py
    - src/hsb/cli/main.py
    - tests/__init__.py
    - knowledge/architecture/.gitkeep
    - knowledge/qa/.gitkeep
    - knowledge/implementation/.gitkeep
    - knowledge/backlog/.gitkeep
    - knowledge/risk/.gitkeep
    - knowledge/patterns/.gitkeep
    - knowledge/anti-patterns/.gitkeep
    - .claude/skills/linear-system-of-record/SKILL.md
  modified: []

key-decisions:
  - "D-03 honored: src/hsb/ layout with subdirs agents/, contracts/, cli/"
  - "D-05 honored: pyproject.toml — no requirements.txt"
  - "D-06 honored: only the Linear skill is migrated to .claude/skills/ in Phase 1"
  - "D-07 honored: skills/05-LINEAR-SYSTEM-OF-RECORD.md remains unchanged as the human-readable reference"
  - "MCP key uses lowercase `linear` to match the runtime tool prefix `mcp__linear__*` (Pitfall 1 mitigation)"
  - "All 7 Knowledge Store categories created (REQUIREMENTS.md FOUND-04 lists 5; AI-SPEC adds patterns + anti-patterns) per A3 mitigation"

patterns-established:
  - "Pattern 1: pyproject + hatchling + src layout — entry point `hsb` resolves via `pip install -e .[dev]`"
  - "Pattern 2: .gitignore covers all .claude/* runtime artifacts (session_cache.json, linear_audit.log, compaction_archive_*.jsonl)"
  - "Pattern 3: SDK skills use frontmatter with disable-model-invocation: true to prevent auto-invocation of side-effecting Linear writes"

requirements-completed:
  - FOUND-02
  - FOUND-04

duration: 8min
completed: 2026-05-06
---

# Phase 01-01: Project Scaffold and Linear Skill Migration Summary

**Bootstrap scaffold delivered: pip-installable `hsb` package, Linear MCP registration, Knowledge Store tree, and SDK-discoverable Linear skill — every downstream Phase 1 plan can now import from this foundation.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06
- **Completed:** 2026-05-06
- **Tasks:** 3
- **Files modified:** 18 (all created)

## Accomplishments
- Repo now installs cleanly via `pip install -e .[dev]` and the `hsb` console script resolves to typer's help banner
- Linear MCP server registered with the correct lowercase key (`linear` → runtime prefix `mcp__linear__*`) — Pitfall 1 avoided
- Knowledge Store directory tree established with all 7 categories (REQUIREMENTS.md 5 + AI-SPEC 2 extras)
- Linear skill is auto-discoverable by the Claude Agent SDK at `.claude/skills/linear-system-of-record/SKILL.md` with `disable-model-invocation: true` so Linear writes can never auto-fire during conversation

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml, .gitignore, .env.example, and stub src/hsb/cli/main.py** - `ece38f3` (feat)
2. **Task 2: Create .mcp.json and bootstrap Knowledge Store directory tree** - `0565d9c` (feat)
3. **Task 3: Migrate Linear skill to .claude/skills/linear-system-of-record/SKILL.md and verify install** - `3c1d2c1` (feat)

## Files Created/Modified

- `pyproject.toml` — Package metadata, dependency pins, hsb entry point
- `.mcp.json` — Linear MCP server registration via mcp-remote
- `.gitignore` — Excludes .env, .venv/, .claude/session_cache.json, .claude/linear_audit.log, .claude/compaction_archive_*.jsonl
- `.env.example` — Template for ANTHROPIC_API_KEY and optional LINEAR_API_KEY
- `src/hsb/__init__.py` — Package root for src layout
- `src/hsb/agents/__init__.py` — Agent implementations module
- `src/hsb/contracts/__init__.py` — Pydantic contracts module
- `src/hsb/cli/__init__.py` — Typer CLI module
- `src/hsb/cli/main.py` — Stub typer app (real commands ship in Plan 01-05)
- `tests/__init__.py` — Empty marker for `pytest tests/`
- `knowledge/{architecture,qa,implementation,backlog,risk,patterns,anti-patterns}/.gitkeep` — 7 Knowledge Store categories
- `.claude/skills/linear-system-of-record/SKILL.md` — Migrated Linear skill with frontmatter (5 fields) + verbatim body from `skills/05-LINEAR-SYSTEM-OF-RECORD.md`

## Decisions Made

None — followed plan as specified. All four decisions (D-03, D-05, D-06, D-07) honored as written.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `python3 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]` — exits 0
- `hsb --help` — prints typer help banner and exits 0
- `python3 -c "import json; json.load(open('.mcp.json'))"` — exits 0; lowercase `"linear"` key confirmed
- All 7 Knowledge Store categories present with `.gitkeep` files
- `.claude/skills/linear-system-of-record/SKILL.md` has all 5 frontmatter fields + 7 allowed-tools entries; line count = 189 (>150 expected)
- Original `skills/05-LINEAR-SYSTEM-OF-RECORD.md` preserved unchanged

## Threats Mitigated

| Threat ID | Status | Verification |
|-----------|--------|--------------|
| T-01-01 (.env disclosure) | Mitigated | `.env` line in `.gitignore`; `.env.example` is a placeholder template |
| T-01-02 (audit log disclosure) | Mitigated | `.claude/linear_audit.log`, `.claude/session_cache.json`, `.claude/compaction_archive_*.jsonl` all in `.gitignore` |
| T-01-03 (.mcp.json contains token) | Mitigated | `.mcp.json` has only the npx mcp-remote command; no `env` field; OAuth lives at `~/.mcp-remote/` |
| T-01-04 (wrong-cased MCP key) | Mitigated | Lowercase `"linear"` key — verified via case-sensitive grep |
| T-01-05 (skill auto-invocation of Linear writes) | Mitigated | `disable-model-invocation: true` in SKILL.md frontmatter |
| T-01-06 (hatchling wrong package path) | Mitigated | `[tool.hatch.build.targets.wheel] packages = ["src/hsb"]` — verified via grep |

## Next Phase Readiness

- Plan 01-02 can now `from hsb.contracts.linear import ...` once it creates the modules
- Plan 01-03 can `from hsb.agents...` once it creates the modules
- Plan 01-04 can wire the Linear MCP server (already registered in `.mcp.json`)
- Plan 01-05 can replace `src/hsb/cli/main.py` stub with real typer commands

## Self-Check: PASSED
