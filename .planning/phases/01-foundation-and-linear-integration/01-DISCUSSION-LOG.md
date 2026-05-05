# Phase 1: Foundation and Linear Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 01-foundation-and-linear-integration
**Areas discussed:** Linear auth method, Python project structure, Skill file migration scope

---

## Linear auth method

| Option | Description | Selected |
|--------|-------------|----------|
| API key in .env | LINEAR_API_KEY env var via python-dotenv. Headless, no browser, works in CI. | |
| OAuth 2.1 interactive | One-time browser flow, token persisted by mcp-remote. | ✓ |

**User's choice:** OAuth 2.1 interactive

**Follow-up: Token refresh handling**

| Option | Description | Selected |
|--------|-------------|----------|
| Let mcp-remote handle it automatically | Transparent token refresh, re-auth in browser when prompted. | ✓ |
| Document the re-auth step in setup | Clear CLI instructions for operators when auth expires. | |

**User's choice:** mcp-remote handles refresh automatically

**Notes:** OAuth preferred over API key management. mcp-remote transport handles the full OAuth lifecycle.

---

## Python project structure

| Option | Description | Selected |
|--------|-------------|----------|
| src/ layout with agent modules | src/hsb/ package with agents/, contracts/, cli/ subdirectories. Standard Python packaging. | ✓ |
| Flat modules at root | linear_agent.py, contracts.py, run_loop.py at project root. Simpler but harder to extend. | |
| You decide | Leave structural choice to planner. | |

**User's choice:** src/ layout with agent modules

**Follow-up: Contract model location**

| Option | Description | Selected |
|--------|-------------|----------|
| src/hsb/contracts/ — one file per agent | linear.py, backlog.py, qa.py etc. Mirrors AGENT-CONTRACTS.md structure. | ✓ |
| src/hsb/contracts.py — single module | All pydantic models in one file. Simpler imports, grows large. | |

**User's choice:** src/hsb/contracts/ — one file per agent

**Follow-up: Packaging**

| Option | Description | Selected |
|--------|-------------|----------|
| pyproject.toml | Modern packaging, entry points for CLI commands, dependency pins. | ✓ |
| requirements.txt only | No package install step, scripts called directly. | |

**User's choice:** pyproject.toml

---

## Skill file migration scope

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate Linear skill only | Only .claude/skills/linear-system-of-record/SKILL.md created in Phase 1. | ✓ |
| Migrate all 14 skills now | Full migration, clean repo, but adds scope not needed until Phase 2+. | |
| Defer all migration | Keep skills/ as reference docs, reference explicitly in prompts. | |

**User's choice:** Migrate Linear skill only (recommended)

**Follow-up: Original file handling**

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both — original stays as reference | skills/05-LINEAR-SYSTEM-OF-RECORD.md stays; new SKILL.md added to .claude/skills/. | ✓ |
| Delete original after migration | Remove skills/05 to avoid duplication. | |

**User's choice:** Keep both

---

## Claude's Discretion

- Linear verification testing strategy (live calls vs mock)
- Knowledge Store initialization method (auto-create vs setup script)
- SKILL.md frontmatter exact content for the Linear skill

## Deferred Ideas

- Full 14-skill migration — belongs in respective phases (Phase 2+)
- API key fallback for CI auth — not in Phase 1 scope
- run_loop.py CLI loop — Phase 3 scope
