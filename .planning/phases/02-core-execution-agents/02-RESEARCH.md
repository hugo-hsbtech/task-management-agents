# Phase 2: Core Execution Agents — Research

**Researched:** 2026-05-05
**Domain:** Multi-agent Python implementation — Backlog Agent, Builder Agent, Git Agent, QA Agent — all using the Claude Agent SDK SKILL.md architecture with strict per-agent capability boundaries
**Confidence:** HIGH (all critical decisions are locked in CONTEXT.md and AI-SPEC.md; supporting library versions verified against Phase 1 RESEARCH.md which performed PyPI checks; no major new technology introduced in Phase 2)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Backlog Agent — plan.md Input**
- D-01: Backlog Agent accepts free-form markdown as plan.md input. No required template or heading structure. The LLM running the skill parses the plan using language understanding.
- D-02: Plan file path is user-specified at runtime via `--plan <path>` argument. No hardcoded default. If omitted → FAIL (mandatory input constraint in skills/01-BACKLOG-PLANNING.md).
- D-03: Traceability (BKPK-05) is expressed as section quotes embedded in Linear descriptions. Each Linear issue description includes the relevant excerpt from plan.md that motivated it.

**QA Agent — Linear Write Scope**
- D-04: QA Agent has full Linear write capability in Phase 2. It internally calls the Linear Agent service (built in Phase 1) to increment `qa_cycle_count` on the work item after each review (QAAG-04) and create fix subtasks in Linear (max 5 per report) when `qa_status = changes_required` (QAAG-03). No Linear writes are deferred to Phase 3.
- D-05: The QA cycle cap logic — "when `qa_cycle_count >= 3`, approve with tech-debt annotation instead of requesting further fixes" — lives inside the QA Agent SKILL.md. The LLM reads `qa_cycle_count` from the input contract and switches behavior at the threshold. No Python enforcement layer.

**Git Agent — PR Stacking Strategy**
- D-06: `gh stack` is not used in Phase 2 (or any phase). All PR operations use plain `gh` CLI commands.
- D-07: All task PRs target the EPIC branch directly (`--base <epic-branch>`). No chained task-to-task PR bases.
- D-08: REBASE_STACK cascade (GITA-04) is implemented manually: enumerate sibling open task PRs via `gh pr list --base <epic-branch> --state open`, then `git rebase --onto <epic-branch>` for each.

**Testing Strategy**
- D-09: All four Phase 2 agents are verified via integration tests against real external services — real Linear test workspace and real GitHub repo. No mocking of Linear MCP tools or `gh` CLI.
- D-10: Pydantic contract validation (input/output schema correctness) is tested with unit tests — fast, no external dependencies.
- D-11: Builder Agent integration tests run against a dedicated real GitHub repo (`hsb-test-fixture`) on a test branch.

**SKILL.md Migration**
- Claude's discretion: Each Phase 2 agent (Backlog, Builder, Git, QA) should have its SKILL.md migrated to `.claude/skills/<name>/SKILL.md` during Phase 2, following the pattern established in Phase 1 for the Linear Agent.

**`qa_cycle_count` read source**
- Claude's discretion: Whether `qa_cycle_count` is read from the input contract (caller provides it) or fetched live from Linear before QA review begins — Claude decides based on what keeps the contract clean.

**Test fixture repo setup**
- Claude's discretion: Exact structure of the `hsb-test-fixture` repo — Claude decides to minimize test setup overhead.

**Builder validation detection**
- Claude's discretion: How Builder Agent determines which local validations to run (e.g., detect pytest, ruff, mypy by checking for config files) — Claude decides the detection heuristic.

### Deferred Ideas (OUT OF SCOPE)

- `gh stack` integration — not implemented in any phase; manual `gh pr create --base` is the production strategy
- Chained task-to-task PR bases (skills/04 Case 2) — not implemented in Phase 2; all tasks target EPIC branch
- Simulation/dry-run mode for agents — explicitly out of scope per REQUIREMENTS.md
- Builder Agent validation auto-detection beyond basic heuristics — Phase 5 Intelligence Agent scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BKPK-01 | Backlog Agent reads plan.md and produces structured backlog (EPICs → User Stories → Tasks → Subtasks) traceable to the plan | Skill spec in skills/01-BACKLOG-PLANNING.md is migration-ready; LLM parses free-form markdown (D-01) |
| BKPK-02 | Every EPIC persisted to Linear with title, description, traceability reference to plan.md | `mcp__linear__create_issue` via Phase 1 Linear Agent service; parentId omitted for EPICs |
| BKPK-03 | Every User Story persisted to Linear as child of its EPIC with acceptance criteria | `mcp__linear__create_issue` with `parentId = epic_id` |
| BKPK-04 | Every Task persisted to Linear as child of User Story or directly of EPIC | `mcp__linear__create_issue` with `parentId = user_story_id` or `parentId = epic_id` |
| BKPK-05 | Backlog Agent outputs traceability metadata mapping each item back to its plan.md section | Section quotes embedded in Linear issue descriptions (D-03); idempotency check required (AI-SPEC double-claim Pitfall 1) |
| BLDR-01 | Builder Agent receives work item ID, reads full Linear issue via Linear Agent, implements only scoped change | Read via `mcp__linear__get_issue` (through Linear Agent service); context fetched fresh before implementation (Pitfall 4) |
| BLDR-02 | Builder Agent runs available local validations (build, lint, typecheck, tests) after implementation | Detection heuristic: check for pytest.ini/pyproject.toml tests, ruff.toml, mypy.ini — Claude's discretion |
| BLDR-03 | Builder Agent produces implementation output contract including files changed, validation results, decisions, assumptions, QA notes | Pydantic contract in src/hsb/contracts/builder.py mirroring AGENT-CONTRACTS.md §4 |
| BLDR-04 | Builder Agent does NOT create branches, commit code, or write to Linear directly | Enforced by SKILL.md allowed-tools: Read, Edit, Write, Bash(non-git) only; no mcp__linear__ tools in allowed-tools |
| GITA-01 | Git Agent creates branch named `feature/LIN-{id}-{slug}` | Exact format per skills/04 spec; validated by regex in integration test |
| GITA-02 | Git Agent determines correct PR base: task PR → EPIC branch; EPIC branch PR → main | Fixed strategy per D-07: all task PRs target EPIC branch (no chained task-to-task bases) |
| GITA-03 | Git Agent creates GitHub PR with Linear issue ID in title, correct --base targeting | `gh pr create --base <epic-branch> --title "[LIN-{id}] ..." --head feature/LIN-{id}-{slug}` |
| GITA-04 | Git Agent triggers REBASE_STACK for all open sibling task PRs when a task PR is merged | Manual: `gh pr list --base <epic-branch> --state open` + `git rebase --onto <epic-branch>` per D-08 |
| GITA-05 | Git Agent never merges any PR into main | Enforced by SKILL.md allowed-tools: Bash(gh pr create, gh pr list, git rebase, git push) only — no merge commands |
| QAAG-01 | QA Agent receives PR diff and full Linear issue; produces structured findings contract with approved/changes_required | Reads diff via `gh pr diff`; Linear issue via Linear Agent service |
| QAAG-02 | Every QA finding includes severity, category, blocking flag, evidence, expected vs actual behavior, suggested fix subtask | Pydantic contract in src/hsb/contracts/qa.py with QAFinding model matching AGENT-CONTRACTS.md §6 |
| QAAG-03 | QA Agent creates maximum 5 fix subtasks per QA report via Linear Agent | `Field(max_length=5)` on findings list in Pydantic model; enforced at schema level not just system prompt |
| QAAG-04 | QA Agent increments qa_cycle_count; at >= 3 approves with tech-debt annotation | QA cycle cap logic in SKILL.md (D-05); enforced at Pydantic level by model_validator |
| QAAG-05 | QA Agent never modifies code or creates PRs directly | Enforced by SKILL.md allowed-tools: Read (diff) + Linear Agent service import only |
</phase_requirements>

---

## Summary

Phase 2 builds four Python agents atop the Phase 1 foundation. The critical insight is that no new framework is being introduced: every agent follows exactly the same pattern as the Phase 1 Linear Agent — a Pydantic-validated input contract, a `query()` call with scoped `allowed_tools`, and a Pydantic-validated output contract. The work is implementing this pattern four more times with different tool scopes.

The phase has two orthogonal concerns. First, behavioral correctness: each agent must read its input contract, operate within its strict tool boundary, and produce a schema-valid output contract. These are verified by unit tests (Pydantic contract tests) and integration tests against real services. Second, capability boundary enforcement: Builder must never touch git or Linear; QA must never modify code; Git must never merge to main. These are enforced by the SKILL.md `allowed-tools` frontmatter, not by application code. Getting this wrong is the highest-risk failure mode in the entire phase.

The QA cycle cap (QAAG-04, D-05) and Backlog double-claim prevention (BKPK-05, PITFALLS Pitfall 1) are the two most implementation-sensitive requirements. Both must be enforced at the Pydantic model layer in addition to the SKILL.md system prompt — the model validator is the last line of defense against runaway behavior.

**Primary recommendation:** Build agents in dependency order — Backlog first (Linear writes, highest complexity), QA second (Linear writes via Phase 1 service + cycle cap enforcement), Git third (pure `gh` CLI, most deterministic), Builder last (code edits only, isolated from Linear/git). Migrate SKILL.md for each agent in the same plan that implements its Python layer.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backlog generation from plan.md | API / Backend (Claude Agent SDK) | — | LLM reasoning in agent loop parses plan; Python layer validates contracts |
| Linear hierarchy creation (EPICs/Stories/Tasks) | API / Backend (Linear Agent service, Phase 1) | — | QA and Backlog agents call `src/hsb/agents/linear_agent.py` directly; no direct MCP from Phase 2 agents |
| Pydantic contract validation | API / Backend (Python process) | — | Input and output models in `src/hsb/contracts/`; enforced before and after every agent invocation |
| Code implementation | API / Backend (Claude Agent SDK) | Filesystem | Builder Agent uses Read/Edit/Write/Bash tools scoped to the work item; no git/Linear |
| Branch creation and PR management | API / Backend (Claude Agent SDK / Bash) | GitHub | Git Agent uses `gh` CLI only; no code edits |
| PR diff reading | API / Backend (gh CLI) | — | `gh pr diff` retrieves diff as text; passed to QA Agent input contract |
| QA review and findings | API / Backend (Claude Agent SDK) | — | LLM reviews diff against Linear issue; structured findings in Pydantic output |
| SKILL.md capability boundary enforcement | Claude Code runtime | — | `allowed-tools` frontmatter in `.claude/skills/<name>/SKILL.md` is the primary enforcement mechanism |
| qa_cycle_count tracking | Database / Storage (Linear) | — | Linear is the system of record; QA Agent increments via Linear Agent service after each review |

---

## Standard Stack

### Core (unchanged from Phase 1)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | 0.1.73+ | Agent loop, MCP tool execution, SKILL.md runtime | Mandated; already installed in Phase 1 venv |
| `pydantic` | 2.x | Contract validation for all agent I/O | Mandated; all four new agent contracts follow Phase 1 pattern |
| `typer` | 0.12+ | CLI subcommands for each agent | Mandated; Phase 2 adds backlog, builder, git, qa subcommands to `src/hsb/cli/main.py` |
| `rich` | 13.x+ | Terminal output | Mandated; carried from Phase 1 |
| `python-dotenv` | 1.0+ | Env loading | Mandated; carried from Phase 1 |

[VERIFIED: Phase 1 RESEARCH.md PyPI checks; pyproject.toml dependency pins already established]

### External Tools (Phase 2 specific)

| Tool | Version | Purpose | Availability |
|------|---------|---------|-------------|
| `gh` CLI | 2.89.0 (verified in environment) | Branch creation, PR creation, PR diff retrieval, REBASE_STACK | Available — confirmed in Phase 1 environment probe |
| `git` | 2.43.0 (verified) | Branch ops, rebase --onto for REBASE_STACK | Available |

[VERIFIED: environment probe from Phase 1 RESEARCH.md; gh version 2.89.0 confirmed]

### Testing (Phase 2 additions)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 8.x | Test runner | All unit and integration tests |
| `pytest-asyncio` | 0.23+ | Async test support | Agent integration tests |
| `arize-phoenix` | 4.x | Trace visualization | Optional; eval sign-off |

[ASSUMED — versions from AI-SPEC.md; same as Phase 1; no additional PyPI verification needed]

### Installation

No new packages needed beyond Phase 1's `pip install -e .[dev]`. All Phase 2 dependencies are already in `pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram

```
Operator (terminal)
       |
       v
[typer CLI — hsb <agent> <command>]
       |
       +──────────────────────────────────────────────────────+
       |                                                        |
       v                                                        v
[BacklogInput validation]                             [BuilderInput validation]
       |                                                        |
       v                                                        v
[run_backlog_agent()]                             [run_builder_agent()]
   query(prompt, ClaudeAgentOptions(                query(prompt, ClaudeAgentOptions(
     allowed_tools=[                                  allowed_tools=[
       "mcp__linear__create_issue",                     "Read", "Edit", "Write",
       "mcp__linear__get_issue",                        "Bash(pytest *)", "Bash(ruff *)",
       "Read"                                           "Bash(mypy *)"
     ]                                               ]))
   ))                                                   |
       |                                                v
       v                                        [BuilderOutput validation]
[BacklogOutput validation]                      (files changed, validation results,
(EPIC/Story/Task IDs, traceability)              implementation notes)
       |                                                |
       v                                                v
[Linear Agent service]                         [Git Agent CLI call]
(create hierarchy,                             query(prompt, ClaudeAgentOptions(
 embed plan.md quotes)                           allowed_tools=[
       |                                           "Bash(gh pr create *)",
       v                                           "Bash(gh pr list *)",
[Linear — system of record]                        "Bash(git checkout *)",
                                                   "Bash(git push *)",
                                                   "Bash(git rebase *)"
                                                 ]
                                               ))
                                                        |
                                                        v
                                               [GitOutput validation]
                                               (branch, PR url, base branch)
                                                        |
                                                        v
                                               [QA Agent CLI call]
                                               query(prompt, ClaudeAgentOptions(
                                                 allowed_tools=[
                                                   "Read",
                                                   "Bash(gh pr diff *)"
                                                 ]
                                               ))
                                                        |
                                                        v
                                               [QAOutput validation]
                                               (qa_status, findings[max 5],
                                                cycle cap logic enforced)
                                                        |
                                                        v
                                               [Linear Agent service]
                                               (increment qa_cycle_count,
                                                create fix subtasks if changes_required)
```

### Recommended Project Structure

```
.claude/
├── skills/
│   ├── linear-system-of-record/SKILL.md   (Phase 1 — existing)
│   ├── backlog-planning/
│   │   └── SKILL.md                        (Phase 2 — migrate from skills/01-BACKLOG-PLANNING.md)
│   ├── implementation/
│   │   └── SKILL.md                        (Phase 2 — migrate from skills/02-IMPLEMENTATION.md)
│   ├── qa-review/
│   │   └── SKILL.md                        (Phase 2 — migrate from skills/03-QA-REVIEW.md)
│   └── git-pr-management/
│       └── SKILL.md                        (Phase 2 — migrate from skills/04-GIT-PR-MANAGEMENT.md)
src/hsb/
├── agents/
│   ├── linear_agent.py      (Phase 1 — existing, called by QA + Backlog)
│   ├── backlog_agent.py     (Phase 2 — new)
│   ├── builder_agent.py     (Phase 2 — new)
│   ├── git_agent.py         (Phase 2 — new)
│   └── qa_agent.py          (Phase 2 — new)
├── contracts/
│   ├── base.py              (Phase 1 — existing)
│   ├── linear.py            (Phase 1 — existing)
│   ├── backlog.py           (Phase 2 — new; mirrors AGENT-CONTRACTS.md §1)
│   ├── builder.py           (Phase 2 — new; mirrors AGENT-CONTRACTS.md §4)
│   ├── git.py               (Phase 2 — new; mirrors AGENT-CONTRACTS.md §5)
│   └── qa.py                (Phase 2 — new; mirrors AGENT-CONTRACTS.md §6)
└── cli/
    └── main.py              (Phase 1 stub — Phase 2 adds backlog/builder/git/qa subcommands)
tests/
├── unit/
│   ├── test_backlog_contract.py
│   ├── test_builder_contract.py
│   ├── test_git_contract.py
│   └── test_qa_contract.py    (includes qa_cycle_count model_validator tests)
└── integration/
    ├── test_backlog_agent.py  (real Linear test workspace)
    ├── test_builder_agent.py  (hsb-test-fixture GitHub repo)
    ├── test_git_agent.py      (hsb-test-fixture GitHub repo)
    └── test_qa_agent.py       (real PR diff + real Linear workspace)
```

### Pattern 1: Per-Agent ClaudeAgentOptions with Scoped Tools

**What:** Each agent has an isolated `ClaudeAgentOptions` with only the tools it is explicitly permitted to call. This is the primary mechanism for enforcing capability boundaries (BLDR-04, QAAG-05, GITA-05).

**When to use:** Every `run_<agent>_agent()` function.

```python
# Source: AI-SPEC.md Section 2 (Framework) + STACK.md Claude Agent SDK
# Builder Agent — code modification only, zero git/Linear access
async def run_builder_agent(input: BuilderInput) -> BuilderOutput:
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        allowed_tools=[
            "Read", "Edit", "Write",
            "Bash(pytest *)", "Bash(ruff *)", "Bash(mypy *)",
            "Bash(python *)",   # for running validations
        ],
        # NO mcp__linear__, NO Bash(git *), NO Bash(gh *)
        permission_mode="acceptEdits",
        system_prompt=BUILDER_SYSTEM_PROMPT,
        max_tokens=4096,
    )
    ...

# Git Agent — gh CLI and git only, no code edits, no Linear
async def run_git_agent(input: GitInput) -> GitOutput:
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        allowed_tools=[
            "Bash(gh pr create *)", "Bash(gh pr list *)",
            "Bash(gh pr view *)",
            "Bash(git checkout *)", "Bash(git push *)",
            "Bash(git rebase *)", "Bash(git log *)",
        ],
        # NO Edit/Write, NO mcp__linear__
        ...
    )
    ...

# QA Agent — read diff + call Linear Agent service via Python import
async def run_qa_agent(input: QAInput) -> QAOutput:
    options = ClaudeAgentOptions(
        model="claude-opus-4-7",
        allowed_tools=[
            "Read",
            "Bash(gh pr diff *)", "Bash(gh pr view *)",
        ],
        # NO Edit/Write, NO Bash(git *), NO mcp__linear__
        # Linear writes happen via Python import of linear_agent.py after QA output is validated
        ...
    )
    ...
```

[CITED: AI-SPEC.md Section 4 (Tool Use), Section 2 (Framework Decision)]

### Pattern 2: Pydantic Contract for QA Agent — Cycle Cap Enforced at Schema Level

**What:** The QA output model uses a `model_validator` to enforce the cycle cap at the Pydantic layer, not just in the SKILL.md system prompt. This is the last line of defense — if the LLM produces output that violates the cap, the schema validation rejects it before it reaches the Linear Agent.

**When to use:** `src/hsb/contracts/qa.py` — never modify to relax the validator.

```python
# Source: AI-SPEC.md Section 4b, Structured Outputs with Pydantic
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional

class QAFinding(BaseModel):
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal["functional", "architecture", "code_quality", "test", "security", "regression"]
    status: Literal["blocking", "non_blocking"]
    problem: str
    evidence: dict           # file, component, location, related_requirement
    expected_behavior: str
    actual_behavior: str
    suggested_fix: str
    suggested_subtask: Optional[dict] = None  # title, description, acceptance_criteria
    pr_targeting_guidance: Optional[dict] = None  # target_pr

    model_config = {"extra": "forbid"}


class QAOutput(BaseModel):
    work_item_id: str
    qa_status: Literal["approved", "changes_required"]
    qa_cycle_count: int = Field(ge=1, le=3)
    summary: str
    findings: list[QAFinding] = Field(max_length=5)  # hard cap: max 5 findings
    tech_debt_annotation: Optional[str] = None  # required when qa_cycle_count == 3

    @model_validator(mode="after")
    def validate_cycle_cap_logic(self) -> "QAOutput":
        if self.qa_cycle_count >= 3 and self.qa_status == "changes_required":
            raise ValueError(
                "At qa_cycle_count >= 3, status must be 'approved' with tech_debt_annotation"
            )
        if self.qa_cycle_count >= 3 and not self.tech_debt_annotation:
            raise ValueError(
                "tech_debt_annotation required when qa_cycle_count >= 3"
            )
        return self

    model_config = {"extra": "forbid"}
```

[CITED: AI-SPEC.md Section 4b, Structured Outputs with Pydantic]

### Pattern 3: Backlog Agent — Idempotency Check for Double-Claim Prevention

**What:** Before creating any EPIC in Linear, the Backlog Agent must check whether an EPIC with the same title already exists in the target Linear project. If it exists, the agent skips creation and uses the existing ID. This prevents PITFALLS.md Pitfall 1 (double-claim / duplicate EPICs on re-run).

**When to use:** Backlog Agent system prompt and Python post-processing layer.

```python
# Source: AI-SPEC.md Section 1b (Double-claim failure mode), PITFALLS.md Pitfall 1
# Strategy: Before creating EPIC, query Linear for existing issues with matching title
# If found with same title + type=epic → use existing ID, do not create
# Implementation: include in Backlog Agent system prompt:
BACKLOG_SYSTEM_PROMPT = """
...
IDEMPOTENCY RULE: Before creating any EPIC, call mcp__linear__list_issues with the team
and search term matching the EPIC title. If an issue with the exact title already exists
as an EPIC, use its existing ID instead of creating a new one. Never create duplicate EPICs.
...
"""
```

[CITED: AI-SPEC.md Section 1b, PITFALLS.md Pitfall 1]

### Pattern 4: SKILL.md Frontmatter for Phase 2 Agents

**What:** Each of the four Phase 2 SKILL.md files requires the same three critical frontmatter fields: `disable-model-invocation: true` (prevents auto-invocation for write-capable skills), `allowed-tools` (scoped to only what that agent is permitted), and `context: fork` for agents that should run in isolated subagent context.

**When to use:** Creating `.claude/skills/<name>/SKILL.md` for each agent. Follow the exact pattern established by Phase 1 linear-system-of-record skill.

```yaml
# Example: qa-review SKILL.md frontmatter
---
name: qa-review
description: |
  Reviews a GitHub PR diff against a Linear work item and produces structured QA findings.
  Only invoke when: an operator explicitly requests QA review of a specific PR.
  Do NOT invoke during conversation or for general code discussion.
disable-model-invocation: true
context: fork
allowed-tools:
  - Read
  - Bash(gh pr diff *)
  - Bash(gh pr view *)
arguments:
  - name: work_item_id
    description: "Linear work item ID to review against (e.g. LIN-123)"
  - name: pr_number
    description: "GitHub PR number to review"
  - name: qa_cycle_count
    description: "Current QA cycle count from caller (integer 0-2)"
---
```

[CITED: STACK.md SKILL.md frontmatter fields section; AI-SPEC.md Section 3]

### Pattern 5: Git Agent REBASE_STACK Implementation

**What:** After a sibling task PR is merged into the EPIC branch, the Git Agent must enumerate all remaining open task PRs targeting the EPIC branch and rebase each one. This uses plain `gh` and `git` commands per D-08.

**When to use:** Triggered when a task PR merge event is detected (in Phase 2, invoked explicitly by operator; in Phase 3, triggered by Work Item Orchestrator).

```bash
# Source: CONTEXT.md D-08, PITFALLS.md Pitfall 3
# Step 1: Find all open task PRs targeting the EPIC branch
gh pr list --base epic/LIN-100 --state open --json number,headRefName

# Step 2: For each open sibling PR (excluding the just-merged one):
git fetch origin
git checkout feature/LIN-{sibling_id}-{slug}
git rebase --onto epic/LIN-100 <old-epic-tip> feature/LIN-{sibling_id}-{slug}
git push --force-with-lease origin feature/LIN-{sibling_id}-{slug}
```

Critical: `--force-with-lease` instead of `--force` prevents overwriting concurrent pushes. Include in Git Agent `allowed-tools`.

[CITED: CONTEXT.md D-08; PITFALLS.md Pitfall 3]

### Pattern 6: Builder Agent Validation Detection Heuristic

**What:** Builder Agent detects which local validations to run based on config file presence. Runs only what's detected — never fails on missing tools.

**When to use:** Builder Agent system prompt and the Bash tool sequence in the implementation step.

```python
# Source: Claude's discretion per CONTEXT.md (validation detection)
# In Builder Agent system prompt:
VALIDATION_HEURISTIC = """
After implementing changes, detect and run available validations:

1. Tests: if pyproject.toml contains [tool.pytest] OR pytest.ini OR tests/ directory exists:
   Run: pytest <changed_test_files_or_tests_dir> -x --tb=short
   If no test files relate to changes: Run: pytest tests/ -x --tb=short -q

2. Lint: if ruff.toml OR pyproject.toml contains [tool.ruff]:
   Run: ruff check <changed_files>

3. Type check: if mypy.ini OR pyproject.toml contains [tool.mypy]:
   Run: mypy <changed_files> --ignore-missing-imports

Report each validation as: passed | failed | not_run (with reason).
If a validation fails, attempt to fix the issue before reporting.
If the fix attempt fails after 2 tries, report status=failed with the error.
"""
```

[ASSUMED — no official specification for this detection pattern; derived from skills/02-IMPLEMENTATION.md guidance and Claude's discretion per CONTEXT.md]

### Anti-Patterns to Avoid

- **Putting Linear writes in Builder Agent SKILL.md allowed-tools:** Even adding `mcp__linear__get_issue` for reading violates the principle. Builder reads Linear state via the Phase 1 `run_validated_linear_agent()` Python function before the agent loop starts — the work item content is passed as part of the input contract, not fetched inside the agent loop.
- **Relying on SKILL.md system prompt alone for cycle cap enforcement:** The LLM may not always follow the cap instruction. The `model_validator` in `QAOutput` is the authoritative enforcement — never remove it in favor of "just the prompt".
- **Using `gh stack` commands in Git Agent allowed-tools:** `gh stack` is in private preview (D-06). Any reference to it in SKILL.md or Python code creates a hard dependency on unavailable tooling.
- **Allowing `Bash(git merge *)` or `Bash(git push --force *)` in Git Agent:** Git Agent must never merge and never force-push without `--lease`. The allowed-tools must be explicitly enumerated — wildcard `Bash(git *)` is too permissive.
- **Leaving `extra` unset on Pydantic models:** All four new contract files (`backlog.py`, `builder.py`, `git.py`, `qa.py`) must have `model_config = {"extra": "forbid"}`. A missing `extra` setting causes silent schema drift — the same failure mode that caused Pitfall 4 in the project's history.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Capability boundary enforcement | Custom Python logic that checks tool call names at runtime | SKILL.md `allowed-tools` frontmatter | The SDK enforces allowed-tools before the tool call fires; Python-level checks come too late and create two codepaths to maintain |
| QA cycle cap enforcement | Python `if qa_cycle_count >= 3: force_approve()` in caller code | Pydantic `model_validator` on `QAOutput` + SKILL.md system prompt instruction | The model_validator fires on every output before it reaches caller code; eliminates race between caller and agent |
| Linear idempotency (dedup) | Database/cache of created EPICs | Linear list_issues check in agent system prompt + Backlog Agent pre-flight in Python | Linear is the system of record; any local cache adds state drift risk |
| REBASE_STACK cascade | Custom webhook listener for PR merge events | Git Agent invoked explicitly after each PR merge | Phase 2 agents are invoked by operator; autonomous trigger is Phase 3+ orchestrator concern |
| PR stacking base calculation | Complex dependency graph logic | Fixed rule: all task PRs target EPIC branch (D-07) | The simpler model (all → EPIC) eliminates the Case 2 complexity that the skills/04 spec describes but CONTEXT.md explicitly deferred |
| `qa_cycle_count` state management | Session state / local counter | Linear field read from input contract (D-05) | Linear is the system of record; the caller fetches `qa_cycle_count` from Linear and includes it in the QAInput contract |

**Key insight:** The Claude Agent SDK's `allowed-tools` enforcement, combined with Pydantic schema validators, creates two independent layers of boundary enforcement. Neither layer should be removed in favor of trusting the other — defense in depth against model behavior variation.

---

## Common Pitfalls

### Pitfall 1: Capability Boundary Bleed — Widest Risk in Phase 2

**What goes wrong:** Builder Agent accidentally makes a `mcp__linear__*` call. Or Git Agent calls `Edit`. These do not cause immediate errors — they succeed silently and corrupt system state in ways that are hard to detect until downstream agents fail.

**Why it happens:** The `allowed-tools` frontmatter in SKILL.md blocks calls at the Claude Code interactive layer, but if the Python integration layer (`run_<agent>_agent()`) does not also scope `ClaudeAgentOptions.allowed_tools`, a programmatic invocation via the Agent SDK bypasses the SKILL.md restriction entirely.

**How to avoid:** Every `run_<agent>_agent()` Python function MUST set its own explicit `allowed_tools` in `ClaudeAgentOptions`, independent of the SKILL.md. Both layers must agree. Integration tests must assert that the forbidden tool is not present in Phoenix traces after any run.

**Warning signs:** Any tool call beginning with `mcp__linear__` appears in Builder Agent Phoenix traces. Any `Edit` or `Write` call appears in Git Agent traces. Any `Bash(git *)` call appears in QA Agent traces.

[CITED: AI-SPEC.md Section 1 Critical Failure Mode 1, Section 6 Guardrails]

### Pitfall 2: QA Runaway — Cycle Cap Not Enforced at Both Layers

**What goes wrong:** The Pydantic `model_validator` on `QAOutput` is removed or weakened. The LLM then produces a `qa_status = "changes_required"` output when `qa_cycle_count = 3`, which passes validation and propagates to the Linear Agent, which creates more fix subtasks. The loop continues indefinitely.

**Why it happens:** A developer finds the validator "too restrictive" (e.g., edge cases where the annotated tech debt is genuinely not resolvable) and removes it, intending to rely on the SKILL.md instruction. The SKILL.md instruction is not a hard constraint — it is probabilistic.

**How to avoid:** Treat the `model_validator` as immutable. If the tech-debt annotation wording needs to change, change only the annotation content — never the validator logic. Document this constraint in a comment in `qa.py`.

**Warning signs:** `qa_cycle_count = 3` exists in Linear on a work item that also has `qa_status = changes_required`. Multiple batches of fix subtasks accumulate under the same parent task.

[CITED: AI-SPEC.md Section 1 Critical Failure Mode 2, PITFALLS.md Pitfall 2]

### Pitfall 3: Backlog Double-Claim — Re-Run Creates Phantom EPICs

**What goes wrong:** Operator runs Backlog Agent on the same `plan.md` twice (e.g., to add a missed feature). The agent creates all EPICs again. Linear now has two copies of every EPIC, doubling the work item count.

**Why it happens:** The Backlog Agent's `mcp__linear__create_issue` is called unconditionally for each parsed EPIC, with no pre-flight check against existing Linear state.

**How to avoid:** Include an explicit idempotency check in the Backlog Agent system prompt: "Before creating an EPIC, call `mcp__linear__list_issues` with the plan source context and verify no EPIC with the same title exists. If it exists, use its ID." Additionally, implement a Python pre-flight that fetches existing EPIC titles before invoking the agent loop.

**Warning signs:** Two EPICs with identical titles appear in the Linear project after a second Backlog Agent run. The integration test (run backlog agent twice, count EPICs) fails.

[CITED: AI-SPEC.md Section 1b Known Failure Modes, PITFALLS.md Pitfall 1]

### Pitfall 4: REBASE_STACK Partial Execution — Missing Sibling PRs

**What goes wrong:** Git Agent calls `gh pr list --base <epic-branch> --state open` to find siblings, but the query returns a truncated list (GitHub default pagination is 30). A sibling PR number > 30 in the list is missed. After the rebase, that PR has a stale base and will show merge conflicts at EPIC merge time.

**Why it happens:** `gh pr list` paginates by default. Large EPICs with many tasks will exceed the default page size. The Git Agent receives the first page only.

**How to avoid:** Pass `--limit 100` (or `--json` with pagination) to `gh pr list` in the Git Agent's REBASE_STACK implementation. Include a verification step that checks the rebase completed for every PR in the returned list. In practice, per D-07 (all tasks target EPIC directly, no chained bases), the number of PRs per EPIC is bounded by the task count, which is unlikely to exceed 30 for Phase 2 test scenarios.

**Warning signs:** A PR targeting the EPIC branch shows "Merge conflict" in GitHub UI after a sibling was merged. The PR's base branch shows a commit SHA that is not the current EPIC branch tip.

[CITED: AI-SPEC.md Section 1b Known Failure Modes (REBASE_STACK partial execution)]

### Pitfall 5: SKILL.md Auto-Invocation for Write-Capable Agents

**What goes wrong:** A Phase 2 agent's SKILL.md does not have `disable-model-invocation: true`. Claude Code reads the skill description during a conversational session and decides to auto-invoke the Backlog Agent when the operator says "let's plan the next feature." The Backlog Agent creates EPICs in Linear without explicit operator invocation.

**Why it happens:** Any SKILL.md without `disable-model-invocation: true` is eligible for auto-invocation. Claude Code uses the description to match user intent.

**How to avoid:** All four Phase 2 SKILL.md files must have `disable-model-invocation: true`. Only read-only or enrichment skills (e.g., Intelligence Agent in Phase 5) should be auto-invocable. This is the same constraint applied to the Phase 1 linear-system-of-record skill.

**Warning signs:** Linear has new EPICs or work items that the operator did not explicitly create via `hsb backlog create`. A SKILL.md is missing `disable-model-invocation: true` from its frontmatter.

[CITED: PITFALLS.md Pitfall 7; STACK.md SKILL.md frontmatter fields]

### Pitfall 6: Builder Agent Reads Linear State from Contract Stale State

**What goes wrong:** Builder Agent input contract includes a `linear_issue` field that was fetched by the caller 10 minutes ago. By the time Builder runs, a QA cycle has updated the work item's `qa_status` or added new acceptance criteria via a Linear comment. Builder implements against the stale state and misses the update.

**Why it happens:** The `linear_issue` field in `BuilderInput` is populated by the caller at invocation time. If the caller caches or delays the fetch, the state is stale.

**How to avoid:** The Python layer calling `run_builder_agent()` must fetch the work item from Linear immediately before constructing `BuilderInput` — not from any cached state. Add a comment in the calling code: "ALWAYS fetch fresh Linear state immediately before constructing BuilderInput."

**Warning signs:** Builder Agent implementation notes reference acceptance criteria that differ from the current Linear issue description. QA finds issues that appear to be addressed in a comment added after Builder started.

[CITED: PITFALLS.md Pitfall 4; AI-SPEC.md State Management section]

---

## Code Examples

### QA Agent — qa_cycle_count Read Source (Claude's Discretion Resolution)

The `qa_cycle_count` field should be provided in the `QAInput` contract by the caller, not fetched live inside the QA Agent loop. This keeps the agent stateless and the contract clean. The caller (in Phase 3, the Work Item Orchestrator; in Phase 2, the operator CLI) fetches the count from Linear before invoking QA.

```python
# Source: CONTEXT.md Claude's Discretion + AI-SPEC.md State Management section
class QAInput(BaseModel):
    work_item_id: str
    linear_issue: dict       # full issue content, fetched fresh by caller
    pull_request: dict       # url + diff (from gh pr diff)
    implementation_notes: dict
    epic_context: dict
    qa_cycle_count: int = Field(ge=0, le=2)  # 0-indexed: 0=first review, 1=second, 2=third

    model_config = {"extra": "forbid"}

# Caller pattern:
issue = await run_validated_linear_agent("read", {"issueId": work_item_id})
qa_cycle = issue.metadata.get("qa_cycle_count", 0)
qa_input = QAInput(..., qa_cycle_count=qa_cycle)
```

### Git Agent — Branch and PR Creation (GITA-01, GITA-03)

```bash
# Source: CONTEXT.md D-07, skills/04-GIT-PR-MANAGEMENT.md, AI-SPEC.md Section 4 (Tool Use)
# Branch naming: feature/LIN-{id}-{slug} (exact format, GITA-01)
git checkout -b feature/LIN-123-add-auth epic/LIN-100

# Commit the implementation output
git add <files_changed_from_builder_output>
git commit -m "feat(LIN-123): implement auth endpoint"

# PR creation: task PR targets EPIC branch (D-07)
# PR title format: [LIN-{id}] {description} (GITA-03, exact format)
gh pr create \
  --base epic/LIN-100 \
  --head feature/LIN-123-add-auth \
  --title "[LIN-123] Add auth endpoint" \
  --body "Implements LIN-123: Add auth endpoint\n\nCloses LIN-123"
```

### Backlog Agent — Context Window Management for Large plan.md

```python
# Source: AI-SPEC.md Section 4b (Context Window Management)
# Strategy: split plan.md by top-level heading, run per section, merge output
def chunk_plan_by_heading(plan_content: str) -> list[str]:
    """Split plan.md at each H1 heading."""
    import re
    sections = re.split(r'^# ', plan_content, flags=re.MULTILINE)
    return ['# ' + s for s in sections if s.strip()]

async def run_backlog_agent_chunked(plan_path: str) -> BacklogOutput:
    content = Path(plan_path).read_text()
    if len(content) < 4000:  # Fits in single context
        return await run_backlog_agent(BacklogInput(plan_source=plan_path, ...))

    chunks = chunk_plan_by_heading(content)
    partial_outputs = []
    for chunk in chunks:
        partial = await run_backlog_agent_on_chunk(chunk)
        partial_outputs.append(partial)
        # Write partial IDs to disk immediately (context compaction safety)
        Path("/tmp/hsb-backlog-partial.json").write_text(
            json.dumps([p.model_dump() for p in partial_outputs])
        )
    return merge_backlog_outputs(partial_outputs)
```

[CITED: AI-SPEC.md Section 4b Context Window Strategy]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gh stack` for stacked PR lifecycle | Manual `gh pr create --base` + `git rebase --onto` | April 2026 (gh stack still private preview) | Phase 2 must implement REBASE_STACK manually; no dependency on preview tooling |
| LangChain/CrewAI agent boundaries | SKILL.md `allowed-tools` frontmatter | 2024 (Claude Code skills GA) | Native enforcement without third-party framework overhead |
| Skills as flat .md files at repo root | `.claude/skills/<name>/SKILL.md` with frontmatter | Claude Code skills spec (current) | Enables progressive disclosure, `disable-model-invocation`, SDK auto-discovery |

**Deprecated/outdated:**
- `gh stack`: Do not reference in SKILL.md or plans. It is private preview. Manual approach is the production strategy. [CITED: CONTEXT.md D-06, STACK.md Alternatives Considered]
- Chained task-to-task PR bases (skills/04 Case 2): Deferred per CONTEXT.md. All tasks target EPIC branch. [CITED: CONTEXT.md D-07 Deferred]

---

## Runtime State Inventory

This is a code implementation phase, not a rename/refactor. No runtime state migration needed.

**Stored data:** None (Phase 1 not yet executed; no Linear data created yet)
**Live service config:** None
**OS-registered state:** None
**Secrets/env vars:** No new vars beyond Phase 1 (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN` for gh CLI in non-interactive environments, `LINEAR_TEST_*` for integration tests — all already in `.env.example`)
**Build artifacts:** None (Phase 1 venv will be the build environment for Phase 2)

---

## Assumptions Log

> Claims tagged [ASSUMED] in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Builder validation detection heuristic (check for pytest.ini, pyproject.toml[tool.pytest], ruff.toml) is sufficient for hsb-test-fixture repo | Pattern 6 (Builder validation detection) | Test fixture repo may use different config patterns; heuristic fails to detect available validators; fixable by updating SKILL.md system prompt |
| A2 | `arize-phoenix>=4.0` and `pytest-asyncio>=0.23` are the correct minimum versions for Phase 2 eval tooling | Standard Stack (Testing) | Version constraint mismatch on install; fixable |
| A3 | `gh pr list` default pagination (30) will not be exceeded in Phase 2 test scenarios (each EPIC has <= 30 task PRs) | Pitfall 4 (REBASE_STACK pagination) | A test with > 30 sibling PRs would miss some; highly unlikely in Phase 2 manual testing |
| A4 | The `qa_cycle_count` field is available in the Linear issue metadata via `mcp__linear__get_issue` (either as a custom field or comment-embedded) | Code Examples (QA Agent) | If Linear MCP does not expose qa_cycle_count in get_issue response, the caller cannot construct QAInput correctly; requires alternative mechanism |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.
Assumptions A1, A3 are low risk for Phase 2. A2 is identical to Phase 1 assumption. A4 is moderate risk — this was an open question in Phase 1 (resolved as "agent picks best available mechanism") and the resolution mechanism should be confirmed when Phase 1 is complete.

---

## Open Questions

1. **Phase 1 Completion Status**
   - What we know: Phase 1 plans exist but no Python source code has been created yet (repository contains only markdown). Phase 2 builds on `src/hsb/agents/linear_agent.py` which is a Phase 1 deliverable.
   - What's unclear: Whether Phase 1 will complete before Phase 2 planning is executed, and specifically whether `run_validated_linear_agent()` and the Linear Agent service will be available as imports for Phase 2 QA and Backlog agents.
   - Recommendation: Phase 2 plans must declare `depends_on: [01-05-PLAN.md]` in their frontmatter. The first Phase 2 plan should verify Phase 1 deliverables exist before proceeding.

2. **qa_cycle_count field availability in Linear**
   - What we know: Phase 1 RESEARCH.md identified this as an open question and resolved it as "agent inspects mcp__linear__update_issue schema at runtime and uses best available mechanism (custom field, label, or structured comment)."
   - What's unclear: The QA Agent's input contract requires `qa_cycle_count` as an integer. If the current mechanism stores it as a comment (`<!-- qa_cycle_count: 2 -->`), the caller must parse that comment to extract the integer.
   - Recommendation: Phase 2 plan for QA Agent (likely Plan 4 of this phase) should include a task to verify and document the exact mechanism used by Phase 1 to store `qa_cycle_count`, and implement the matching read logic in the QA Agent input preparation.

3. **hsb-test-fixture repo setup**
   - What we know: D-11 requires a dedicated `hsb-test-fixture` GitHub repo with a minimal Python package for Builder and Git Agent integration tests. Claude's discretion per CONTEXT.md.
   - What's unclear: Whether the repo already exists or needs to be created as a Wave 0 step.
   - Recommendation: Include repo creation (with minimal `pyproject.toml`, a `src/fixture/` package, and a `tests/test_placeholder.py`) as a Wave 0 task in the first Phase 2 plan that requires it. The repo should be public or accessible to the GitHub token used for integration tests.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All agents | Yes | 3.12.3 | — |
| `claude-agent-sdk` | All agents | No (not installed yet) | — | Install via `pip install -e .[dev]` after Phase 1 |
| `pydantic` | Contract models | No (not installed yet) | — | Install via Phase 1 |
| `gh` CLI | Git Agent, QA Agent | Yes | 2.89.0 | — |
| `git` | Git Agent | Yes | 2.43.0 | — |
| `pytest` | All tests | No (not installed yet) | — | Install via Phase 1 |
| `ANTHROPIC_API_KEY` | All agents | Not verified (not in env) | — | Must be set in `.env` before any agent run |
| `GITHUB_TOKEN` | Git Agent integration tests | Not verified | — | Required for `gh` CLI in non-interactive mode |
| Linear test workspace | Backlog + QA integration tests | Not verified | — | Required; LINEAR_TEST_TEAM_ID env var |
| `hsb-test-fixture` GitHub repo | Builder + Git integration tests | Unknown (may not exist) | — | Create in Wave 0 (Claude's discretion, D-11) |

**Missing dependencies with no fallback:**
- `ANTHROPIC_API_KEY` must be set before any agent invocation
- `hsb-test-fixture` GitHub repo must exist for Builder/Git integration tests — if it doesn't exist, create it in Wave 0

**Missing dependencies with fallback:**
- `claude-agent-sdk`, `pydantic`, `pytest` — all installed via Phase 1's `pip install -e .[dev]`; Phase 2 execution blocked on Phase 1 completion

[VERIFIED: gh 2.89.0, git 2.43.0, Python 3.12.3 — from environment probe in Phase 1 RESEARCH.md, confirmed available in this environment]

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ (installed via Phase 1 `pip install -e .[dev]`) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` (established Phase 1) |
| Quick run command | `pytest tests/unit/ -x` |
| Full suite command | `pytest tests/ -x --ignore=tests/integration/` |
| Integration suite | `pytest tests/integration/ -v -m integration` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BKPK-01 | Backlog Agent parses plan.md and produces structured output | integration | `pytest tests/integration/test_backlog_agent.py::test_parse_plan -x -m integration` | No — Wave 0 |
| BKPK-02 | EPICs persisted to Linear with title and traceability | integration | `pytest tests/integration/test_backlog_agent.py::test_create_epics -x -m integration` | No — Wave 0 |
| BKPK-03 | User Stories persisted as children of EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_user_stories -x -m integration` | No — Wave 0 |
| BKPK-04 | Tasks persisted as children of User Stories or EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_create_tasks -x -m integration` | No — Wave 0 |
| BKPK-05 | Idempotency: second run does not create duplicate EPICs | integration | `pytest tests/integration/test_backlog_agent.py::test_idempotency -x -m integration` | No — Wave 0 |
| BLDR-01 | Builder reads work item from Linear and implements only scoped change | integration | `pytest tests/integration/test_builder_agent.py::test_scoped_implementation -x -m integration` | No — Wave 0 |
| BLDR-02 | Builder runs local validations and reports results | integration | `pytest tests/integration/test_builder_agent.py::test_validation_run -x -m integration` | No — Wave 0 |
| BLDR-03 | BuilderOutput contract validates correctly | unit | `pytest tests/unit/test_builder_contract.py -x` | No — Wave 0 |
| BLDR-04 | Builder does not use git or Linear tools | integration | `pytest tests/integration/test_builder_agent.py::test_capability_boundary -x -m integration` | No — Wave 0 |
| GITA-01 | Branch named feature/LIN-{id}-{slug} | integration | `pytest tests/integration/test_git_agent.py::test_branch_naming -x -m integration` | No — Wave 0 |
| GITA-02 | Task PR targets EPIC branch | integration | `pytest tests/integration/test_git_agent.py::test_pr_base -x -m integration` | No — Wave 0 |
| GITA-03 | PR title includes Linear issue ID | integration | `pytest tests/integration/test_git_agent.py::test_pr_title -x -m integration` | No — Wave 0 |
| GITA-04 | REBASE_STACK triggers for all sibling PRs | integration | `pytest tests/integration/test_git_agent.py::test_rebase_stack -x -m integration` | No — Wave 0 |
| GITA-05 | Git Agent never merges | unit | `pytest tests/unit/test_git_contract.py::test_no_merge_in_allowed_tools -x` | No — Wave 0 |
| QAAG-01 | QA Agent produces approved/changes_required contract | integration | `pytest tests/integration/test_qa_agent.py::test_qa_review -x -m integration` | No — Wave 0 |
| QAAG-02 | Each finding includes all required fields | unit | `pytest tests/unit/test_qa_contract.py::test_finding_fields -x` | No — Wave 0 |
| QAAG-03 | Max 5 findings per report (Pydantic enforced) | unit | `pytest tests/unit/test_qa_contract.py::test_findings_max_length -x` | No — Wave 0 |
| QAAG-04 | qa_cycle_count=3 forces approved + tech_debt_annotation | unit | `pytest tests/unit/test_qa_contract.py::test_cycle_cap_validator -x` | No — Wave 0 |
| QAAG-05 | QA Agent never uses Edit/Write/git tools | integration | `pytest tests/integration/test_qa_agent.py::test_capability_boundary -x -m integration` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/ -x`
- **Per wave merge:** `pytest tests/ -x --ignore=tests/integration/`
- **Phase gate:** Full suite including integration tests green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_backlog_contract.py` — BacklogInput/BacklogOutput schema tests
- [ ] `tests/unit/test_builder_contract.py` — BuilderInput/BuilderOutput schema tests (BLDR-03)
- [ ] `tests/unit/test_git_contract.py` — GitInput/GitOutput schema tests + GITA-05 allowed-tools check
- [ ] `tests/unit/test_qa_contract.py` — QAFinding/QAOutput tests including cycle cap validator (QAAG-02, QAAG-03, QAAG-04)
- [ ] `tests/integration/test_backlog_agent.py` — real Linear workspace tests (BKPK-01 through BKPK-05)
- [ ] `tests/integration/test_builder_agent.py` — hsb-test-fixture repo tests (BLDR-01, BLDR-02, BLDR-04)
- [ ] `tests/integration/test_git_agent.py` — hsb-test-fixture repo tests (GITA-01 through GITA-05)
- [ ] `tests/integration/test_qa_agent.py` — real PR diff + Linear workspace tests (QAAG-01, QAAG-05)
- [ ] `hsb-test-fixture` GitHub repo creation (if it does not exist) — required by BLDR integration tests

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 2 adds no new auth) | Phase 1 mcp-remote OAuth handles Linear auth |
| V3 Session Management | No | Same as Phase 1 |
| V4 Access Control | Yes (capability boundaries) | SKILL.md allowed-tools + ClaudeAgentOptions.allowed_tools — two-layer enforcement |
| V5 Input Validation | Yes | Pydantic v2 with `extra="forbid"` on all 4 new contract files |
| V6 Cryptography | No | No new crypto requirements |

### Phase 2 Specific Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Builder Agent writes to Linear (capability bleed) | Elevation of Privilege | SKILL.md `allowed-tools` excludes `mcp__linear__*`; ClaudeAgentOptions excludes same; integration test asserts boundary |
| QA Agent modifies code (capability bleed) | Tampering | SKILL.md `allowed-tools` excludes Edit/Write; integration test asserts boundary |
| Git Agent force-pushes to main | Tampering | `allowed-tools` excludes `Bash(git push * main)`; GITA-05 unit test verifies |
| Backlog Agent creates duplicate EPICs | Denial of Service (backlog pollution) | Idempotency check in system prompt + Python pre-flight; integration test runs agent twice, asserts count unchanged |
| QA runaway (4th+ cycle) | Denial of Service (infinite loop) | model_validator on QAOutput blocks changes_required at cycle_count >= 3; cannot be relaxed |
| `GITHUB_TOKEN` in gh CLI commands | Information Disclosure | Token loaded from env var via `python-dotenv`; never hardcoded in SKILL.md or Python; `.env` gitignored |

[ASSUMED — ASVS mapping based on project threat model; no formal ASVS review performed for Phase 2 specifically]

---

## Sources

### Primary (HIGH confidence)

- `.planning/phases/02-core-execution-agents/02-CONTEXT.md` — locked decisions D-01 through D-11, all Claude's Discretion areas, Deferred list
- `.planning/phases/02-core-execution-agents/02-AI-SPEC.md` — framework selection (SKILL.md architecture), implementation guidance, evaluation dimensions, Pydantic contract patterns, critical failure modes
- `agents/AGENT-CONTRACTS.md` — canonical JSON schemas for §1 (Backlog), §4 (Builder), §5 (Git), §6 (QA); Pydantic models must match exactly
- `.planning/research/PITFALLS.md` — Pitfalls 1-7 directly applicable to Phase 2; authored from verified sources
- `.planning/research/STACK.md` — library versions, SDK patterns, SKILL.md frontmatter spec; verified against PyPI and official docs 2026-05-05
- `.planning/phases/01-foundation-and-linear-integration/01-RESEARCH.md` — PyPI version verifications, environment probe results, established patterns for Phase 2 to extend
- `skills/01-BACKLOG-PLANNING.md`, `skills/02-IMPLEMENTATION.md`, `skills/03-QA-REVIEW.md`, `skills/04-GIT-PR-MANAGEMENT.md` — behavioral specs for each Phase 2 agent; migration-ready to SKILL.md
- `agents/AGENTS.md` — capability boundary definitions per agent (Must Not sections)

### Secondary (MEDIUM confidence)

- GitHub CLI documentation (`gh` 2.89.0) — `gh pr create`, `gh pr list`, `gh pr diff` command syntax
- Python 3.12 asyncio documentation — `asyncio.run()` at CLI boundary pattern

### Tertiary (LOW confidence)

- ASVS category mapping for Phase 2 — training knowledge; no tool-verified review performed
- `arize-phoenix>=4.0`, `pytest-asyncio>=0.23` version pins — from AI-SPEC.md, not re-verified against PyPI

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages are Phase 1 dependencies already pinned; gh and git versions verified in environment
- Architecture: HIGH — derived directly from AI-SPEC.md, CONTEXT.md, and existing skill specs; no new framework
- Pitfalls: HIGH — sourced from PITFALLS.md (HIGH/MEDIUM ratings) plus AI-SPEC.md critical failure modes
- Test approach: HIGH — D-09 (real services, no mocking) is locked; test structure mirrors Phase 1 hybrid approach

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (stable stack; claude-agent-sdk minor versions may update but 0.1.73+ pin is sufficient)
