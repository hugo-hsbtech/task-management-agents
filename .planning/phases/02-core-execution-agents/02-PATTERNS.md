# Phase 2: Core Execution Agents - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 16 new/modified files
**Analogs found:** 16 / 16 (all spec-derived from Phase 1 PATTERNS.md + specification documents; no Python source exists yet)

> **Greenfield note (same as Phase 1):** The repository still contains only markdown documentation — no Python source code has been created yet. Every pattern below is derived from (1) the Phase 1 PATTERNS.md (which defines the canonical patterns for `linear_agent.py`, `contracts/`, `cli/main.py`, `hooks.py`) and (2) the Phase 2 AI-SPEC.md and RESEARCH.md. Phase 2 files directly extend the Phase 1 foundation. All code excerpts below are canonical — copy verbatim, do not paraphrase. Where Phase 2 adds to an existing file (e.g., `cli/main.py`), the pattern shows the delta only.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/hsb/contracts/backlog.py` | model | CRUD (pydantic validate) | `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md §linear.py) | exact-role |
| `src/hsb/contracts/builder.py` | model | CRUD (pydantic validate) | `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md §linear.py) | exact-role |
| `src/hsb/contracts/git.py` | model | CRUD (pydantic validate) | `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md §linear.py) | exact-role |
| `src/hsb/contracts/qa.py` | model | CRUD (pydantic validate + model_validator) | `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md §linear.py, model_validator pattern) | exact-role |
| `src/hsb/agents/backlog_agent.py` | service | request-response (sync Anthropic client) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) | exact-role |
| `src/hsb/agents/builder_agent.py` | service | request-response (sync Anthropic client) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) | exact-role |
| `src/hsb/agents/git_agent.py` | service | request-response (sync Anthropic client) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) | exact-role |
| `src/hsb/agents/qa_agent.py` | service | request-response (sync Anthropic client + Linear Agent import) | `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py) | exact-role |
| `src/hsb/cli/main.py` (extend) | controller | request-response (typer CLI → synchronous run) | `src/hsb/cli/main.py` (Phase 1 PATTERNS.md §cli/main.py) | exact-role |
| `.claude/skills/backlog-planning/SKILL.md` | config | — | `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md) | exact-role |
| `.claude/skills/implementation/SKILL.md` | config | — | `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md) | exact-role |
| `.claude/skills/qa-review/SKILL.md` | config | — | `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md) | exact-role |
| `.claude/skills/git-pr-management/SKILL.md` | config | — | `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md) | exact-role |
| `tests/unit/test_backlog_contract.py` | test | CRUD (unit) | `tests/test_contracts.py` (Phase 1 PATTERNS.md §test_contracts.py) | exact-role |
| `tests/unit/test_builder_contract.py` | test | CRUD (unit) | `tests/test_contracts.py` (Phase 1 PATTERNS.md §test_contracts.py) | exact-role |
| `tests/unit/test_git_contract.py` | test | CRUD (unit) | `tests/test_contracts.py` (Phase 1 PATTERNS.md §test_contracts.py) | exact-role |
| `tests/unit/test_qa_contract.py` | test | CRUD (unit + model_validator) | `tests/test_contracts.py` + `tests/test_hooks.py` (Phase 1 PATTERNS.md) | exact-role |
| `tests/integration/test_backlog_agent.py` | test | request-response (integration) | `tests/test_integration.py` (Phase 1 PATTERNS.md §test_integration.py) | exact-role |
| `tests/integration/test_builder_agent.py` | test | request-response (integration) | `tests/test_integration.py` (Phase 1 PATTERNS.md §test_integration.py) | exact-role |
| `tests/integration/test_git_agent.py` | test | request-response (integration) | `tests/test_integration.py` (Phase 1 PATTERNS.md §test_integration.py) | exact-role |
| `tests/integration/test_qa_agent.py` | test | request-response (integration) | `tests/test_integration.py` (Phase 1 PATTERNS.md §test_integration.py) | exact-role |

---

## Pattern Assignments

### `src/hsb/contracts/backlog.py` (model, CRUD)

**Analog:** `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md; same `BaseModel` + `extra="forbid"` pattern)
**Source spec:** `agents/AGENT-CONTRACTS.md` §1 Backlog Planning Contract

**Imports pattern** (copy from Phase 1 `contracts/linear.py` imports):

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
```

**Full contract models** (mirror `agents/AGENT-CONTRACTS.md` §1 exactly — do not add fields):

```python
class ProjectContext(BaseModel):
    name: str
    repository: str
    technical_stack: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BacklogInput(BaseModel):
    """Input contract for the Backlog Planning Agent.
    Mirrors AGENT-CONTRACTS.md §1 Input exactly.
    plan_source is user-specified at runtime via --plan <path> (D-02).
    """
    plan_source: str  # absolute path to plan.md; no default (FAIL if missing — BKPK-01)
    project_context: ProjectContext

    model_config = {"extra": "forbid"}


class TaskItem(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class UserStory(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class EpicItem(BaseModel):
    title: str  # must start with "[EPIC]" per skills/01-BACKLOG-PLANNING.md
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    tasks: list[TaskItem] = Field(default_factory=list)  # direct task children

    model_config = {"extra": "forbid"}


class BacklogTraceability(BaseModel):
    plan_source: str  # path back to the plan.md that generated this backlog

    model_config = {"extra": "forbid"}


class BacklogOutput(BaseModel):
    """Output contract for the Backlog Planning Agent.
    Mirrors AGENT-CONTRACTS.md §1 Output exactly.
    """
    epics: list[EpicItem] = Field(min_length=1)
    traceability: BacklogTraceability

    model_config = {"extra": "forbid"}
```

**Critical rules (same as Phase 1 §linear.py critical rules):**
- `extra="forbid"` MANDATORY on every model — absent causes silent schema drift (PITFALLS.md Pitfall 4)
- `EpicItem.title` must start with `"[EPIC]"` — enforced in Backlog Agent system prompt; validated by unit test
- `epics` field uses `min_length=1` — Backlog Agent must produce at least one EPIC or raise ValidationError
- Do NOT add fields not in `agents/AGENT-CONTRACTS.md §1` — downstream orchestrator depends on exact mirror

---

### `src/hsb/contracts/builder.py` (model, CRUD)

**Analog:** `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md; same `BaseModel` + `extra="forbid"` + `Literal` pattern)
**Source spec:** `agents/AGENT-CONTRACTS.md` §4 Implementation Contract

**Imports pattern:**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
```

**Full contract models** (mirror `agents/AGENT-CONTRACTS.md` §4 exactly):

```python
class RepositoryContext(BaseModel):
    root_path: str
    technical_stack: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BuilderInput(BaseModel):
    """Input contract for the Builder Agent.
    Mirrors AGENT-CONTRACTS.md §4 Input exactly.
    ALWAYS fetch fresh Linear state immediately before constructing BuilderInput.
    Never pass cached linear_issue — fetch via run_validated_linear_agent at call site (Pitfall 4).
    """
    work_item_id: str
    issue_description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    epic_context: dict  # full EPIC issue JSON, fetched fresh from Linear
    plan_source: str
    repository_context: RepositoryContext
    knowledge_context: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class FileChanged(BaseModel):
    path: str
    change_summary: str

    model_config = {"extra": "forbid"}


class ValidationResults(BaseModel):
    build: Literal["passed", "failed", "not_run"]
    tests: Literal["passed", "failed", "not_run"]
    lint: Literal["passed", "failed", "not_run"]
    typecheck: Literal["passed", "failed", "not_run"]

    model_config = {"extra": "forbid"}


class ImplementationNotes(BaseModel):
    decisions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    qa_notes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BuilderOutput(BaseModel):
    """Output contract for the Builder Agent.
    Mirrors AGENT-CONTRACTS.md §4 Output exactly.
    Builder MUST NOT include git commits, branch names, or Linear updates here — BLDR-04.
    """
    work_item_id: str
    implementation_status: Literal["completed", "blocked", "failed"]
    summary: str
    files_changed: list[FileChanged] = Field(default_factory=list)
    validation: ValidationResults
    implementation_notes: ImplementationNotes

    model_config = {"extra": "forbid"}
```

**Critical rules:**
- `extra="forbid"` MANDATORY on all models
- Builder MUST NOT write branch, PR, or Linear fields into this contract (BLDR-04) — if those appear, the agent violated its boundary
- `validation` uses Literal enum with "not_run" as the safe default for missing tools (Pattern 6 from RESEARCH.md)

---

### `src/hsb/contracts/git.py` (model, CRUD)

**Analog:** `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md)
**Source spec:** `agents/AGENT-CONTRACTS.md` §5 Git/PR Management Contract

**Imports pattern:**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
```

**Full contract models** (mirror `agents/AGENT-CONTRACTS.md` §5 exactly):

```python
class ExistingPRContext(BaseModel):
    epic_pr: Optional[str] = None  # URL of the EPIC's open PR if it exists
    base_pr: Optional[str] = None  # URL of the previous task PR (not used in Phase 2 — all tasks target EPIC branch per D-07)

    model_config = {"extra": "forbid"}


class GitInput(BaseModel):
    """Input contract for the Git Agent.
    Mirrors AGENT-CONTRACTS.md §5 Input exactly.
    Per D-07: all task PRs target EPIC branch directly — base_pr is always None in Phase 2.
    """
    work_item_id: str
    implementation_output: dict  # serialized BuilderOutput.model_dump()
    epic_id: str  # e.g., "LIN-100" — used to determine branch base
    dependencies: list[str] = Field(default_factory=list)
    existing_pr_context: ExistingPRContext = Field(default_factory=ExistingPRContext)

    model_config = {"extra": "forbid"}


class PullRequest(BaseModel):
    url: str
    title: str  # format: "[LIN-{id}] {description}" (GITA-03 exact format)
    base: str   # epic branch name, e.g., "epic/LIN-100"
    head: str   # feature branch name, e.g., "feature/LIN-123-add-auth"

    model_config = {"extra": "forbid"}


class GitOutput(BaseModel):
    """Output contract for the Git Agent.
    Mirrors AGENT-CONTRACTS.md §5 Output exactly.
    Git MUST NOT include Linear update fields or code change fields — GITA-05.
    """
    work_item_id: str
    branch: str   # format: "feature/LIN-{id}-{slug}" (GITA-01 exact format)
    commits: list[str] = Field(default_factory=list)  # commit SHAs
    pull_request: PullRequest

    model_config = {"extra": "forbid"}
```

**Critical rules:**
- Branch naming must match regex `^feature/LIN-\d+-[a-z0-9-]+$` — validate in integration test (GITA-01)
- PR title must match regex `^\[LIN-\d+\]` — validate in integration test (GITA-03)
- `extra="forbid"` on all models

---

### `src/hsb/contracts/qa.py` (model, CRUD + model_validator)

**Analog:** `src/hsb/contracts/linear.py` (Phase 1 PATTERNS.md `model_validator` pattern — `failed_must_have_error`)
**Source spec:** `agents/AGENT-CONTRACTS.md` §6 QA Review Contract + `02-RESEARCH.md` Pattern 2

**Imports pattern:**

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
```

**Full contract models** (mirror `agents/AGENT-CONTRACTS.md` §6 and `02-RESEARCH.md` Pattern 2 exactly):

```python
class QAEvidence(BaseModel):
    file: str
    component: str
    location: str
    related_requirement: str

    model_config = {"extra": "forbid"}


class SuggestedSubtask(BaseModel):
    title: str   # must start with "[FIX]" per skills/03-QA-REVIEW.md
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class PRTargetingGuidance(BaseModel):
    target_pr: str

    model_config = {"extra": "forbid"}


class QAFinding(BaseModel):
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal["functional", "architecture", "code_quality", "test", "security", "regression"]
    status: Literal["blocking", "non_blocking"]
    problem: str
    evidence: QAEvidence
    expected_behavior: str
    actual_behavior: str
    suggested_fix: str
    suggested_subtask: Optional[SuggestedSubtask] = None
    pr_targeting_guidance: Optional[PRTargetingGuidance] = None

    model_config = {"extra": "forbid"}


class PullRequestInput(BaseModel):
    url: str
    diff: str  # full diff text from gh pr diff

    model_config = {"extra": "forbid"}


class QAInput(BaseModel):
    """Input contract for the QA Agent.
    Mirrors AGENT-CONTRACTS.md §6 Input exactly.
    qa_cycle_count is provided by caller (fetched fresh from Linear) — NOT fetched inside agent loop (Claude's Discretion from CONTEXT.md).
    """
    work_item_id: str
    linear_issue: dict           # full issue JSON, fetched fresh by caller immediately before invocation
    pull_request: PullRequestInput
    implementation_notes: dict   # serialized BuilderOutput.implementation_notes
    epic_context: dict
    qa_cycle_count: int = Field(ge=0, le=2)  # 0-indexed: 0=first review, 1=second, 2=third

    model_config = {"extra": "forbid"}


class QAOutput(BaseModel):
    """Output contract for the QA Agent.
    Mirrors AGENT-CONTRACTS.md §6 Output exactly.

    IMMUTABLE CONSTRAINT: The model_validator below enforces the QA cycle cap.
    NEVER remove or weaken it — it is the last line of defense against QA runaway (PITFALLS.md Pitfall 2).
    Relying on the SKILL.md system prompt alone is insufficient (probabilistic, not guaranteed).
    """
    work_item_id: str
    qa_status: Literal["approved", "changes_required"]
    qa_cycle_count: int = Field(ge=1, le=3)  # 1-indexed in output: 1=first review done, 2=second, 3=third
    summary: str
    findings: list[QAFinding] = Field(max_length=5)  # hard cap: max 5 findings (QAAG-03)
    tech_debt_annotation: Optional[str] = None  # required when qa_cycle_count == 3

    @model_validator(mode="after")
    def validate_cycle_cap_logic(self) -> "QAOutput":
        # IMMUTABLE: Do not modify this validator. See docstring above.
        if self.qa_cycle_count >= 3 and self.qa_status == "changes_required":
            raise ValueError(
                "At qa_cycle_count >= 3, status must be 'approved' with tech_debt_annotation. "
                "QA runaway prevention (QAAG-04, PITFALLS.md Pitfall 2)."
            )
        if self.qa_cycle_count >= 3 and not self.tech_debt_annotation:
            raise ValueError(
                "tech_debt_annotation required when qa_cycle_count >= 3"
            )
        return self

    model_config = {"extra": "forbid"}
```

**Critical rules (highest-priority in Phase 2):**
- `model_validator` on `QAOutput` is IMMUTABLE — never remove or relax (QAAG-04, PITFALLS.md Pitfall 2)
- `Field(max_length=5)` on `findings` enforces QAAG-03 at schema level, not just system prompt
- `extra="forbid"` on all models
- `qa_cycle_count` in `QAInput` is 0-indexed (0=first review); in `QAOutput` it is 1-indexed (1=first review done) — this asymmetry matches the pattern in `02-RESEARCH.md` Code Examples

---

### `src/hsb/agents/backlog_agent.py` (service, request-response)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md §linear_agent.py — same sync client + validation/retry pattern)
**Source spec:** `02-AI-SPEC.md` §4 Implementation Guidance + `02-RESEARCH.md` Pattern 3 (idempotency)

**Imports pattern** (extend Phase 1 linear_agent.py imports, adapt for Anthropic sync client):

```python
import json
import logging
import os
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from hsb.contracts.backlog import BacklogInput, BacklogOutput
from hsb.agents.linear_agent import run_validated_linear_agent

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core agent pattern** (`02-AI-SPEC.md` §4 + Phase 1 PATTERNS.md `run_validated_linear_agent` retry pattern):

```python
BACKLOG_SYSTEM_PROMPT = """
You are the Backlog Planning Agent for HSBTech. Your task:
1. Read the plan.md file at the path provided in the input contract.
2. Parse it using language understanding (free-form markdown — no required structure).
3. Generate a structured EPIC → User Story → Task → Subtask hierarchy.
4. For each EPIC/Story/Task, embed the relevant plan.md excerpt in the description (traceability, D-03).

IDEMPOTENCY RULE (BKPK-05, Pitfall 1): Before creating any EPIC, call mcp__linear__list_issues
with the team and a search term matching the EPIC title. If an issue with the exact title already
exists as an EPIC, use its existing ID and skip creation. Never create duplicate EPICs.

OUTPUT FORMAT: Return a JSON object matching BacklogOutput schema exactly.
{
  "epics": [...],
  "traceability": {"plan_source": "<path>"}
}
"""

MAX_VALIDATION_RETRIES = 3

def run_backlog_agent(input: BacklogInput) -> BacklogOutput:
    """Execute the Backlog Agent synchronously. Returns validated BacklogOutput."""
    client = Anthropic()
    plan_content = Path(input.plan_source).read_text()
    prompt = (
        f"Execute backlog planning for the following input contract:\n"
        f"```json\n{input.model_dump_json(indent=2)}\n```\n\n"
        f"Plan file contents:\n```markdown\n{plan_content}\n```\n\n"
        "Return ONLY a JSON object matching BacklogOutput schema."
    )

    last_error = None
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8192,
            system=BACKLOG_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[...],  # mcp__linear__create_issue, mcp__linear__list_issues, mcp__linear__get_issue, Read
        )
        result_text = _extract_text(response)
        if not result_text:
            continue
        try:
            raw = _extract_json(result_text)
            output = BacklogOutput.model_validate(raw)
            logger.info("Backlog Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, ValidationError) as e:
            last_error = e
            logger.warning("Backlog Agent attempt %d: %s", attempt, e)
            prompt += f"\n\nValidation error on previous attempt:\n{e}\nReturn corrected JSON."

    raise ValueError(
        f"Backlog Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. Last error: {last_error}"
    )
```

**Helper functions** (same as Phase 1 linear_agent.py pattern — extract to shared utility or repeat):

```python
def _extract_text(response) -> str | None:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return None

def _extract_json(text: str) -> dict:
    json_start = text.index("{")
    json_end = text.rindex("}") + 1
    return json.loads(text[json_start:json_end])
```

**Key differences from `linear_agent.py`:**
- Uses synchronous `Anthropic()` client, not `claude_agent_sdk.query()` (`02-AI-SPEC.md` §4b Async-First Design: Phase 2 is synchronous CLI)
- Model: `claude-opus-4-7` (Backlog reasoning complexity)
- `max_tokens=8192` (generates many Linear issues)
- Reads plan file content at call site and passes in user prompt
- Allowed tools scoped to Linear MCP create + list + Read only — NO git, NO Edit/Write

---

### `src/hsb/agents/builder_agent.py` (service, request-response)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — same three-phase: validate input, run agent, validate output)
**Source spec:** `02-RESEARCH.md` Pattern 6 (validation detection) + `02-AI-SPEC.md` §4

**Imports pattern:**

```python
import json
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from hsb.contracts.builder import BuilderInput, BuilderOutput

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core agent pattern** (same retry wrapper as `linear_agent.py`):

```python
BUILDER_SYSTEM_PROMPT = """
You are the Builder Agent for HSBTech. Execute ONLY what is scoped in the Linear work item.

CAPABILITY BOUNDARY (BLDR-04): You MUST NOT:
- Create or checkout git branches
- Run git commit or git push
- Call any mcp__linear__* tools
- Write to Linear in any way

ALLOWED TOOLS: Read, Edit, Write, Bash(pytest *), Bash(ruff *), Bash(mypy *), Bash(python *)

VALIDATION HEURISTIC: After implementing changes, detect and run available validations:
1. Tests: if pyproject.toml contains [tool.pytest] OR pytest.ini OR tests/ directory exists:
   Run: pytest <changed_test_files_or_tests_dir> -x --tb=short
2. Lint: if ruff.toml OR pyproject.toml contains [tool.ruff]:
   Run: ruff check <changed_files>
3. Type check: if mypy.ini OR pyproject.toml contains [tool.mypy]:
   Run: mypy <changed_files> --ignore-missing-imports

Report each validation as: passed | failed | not_run (with reason).
If validation fails, attempt to fix before reporting. Max 2 fix attempts per validation.

OUTPUT FORMAT: Return a JSON object matching BuilderOutput schema exactly.
"""

MAX_VALIDATION_RETRIES = 3

def run_builder_agent(input: BuilderInput) -> BuilderOutput:
    """Execute the Builder Agent synchronously. Returns validated BuilderOutput."""
    client = Anthropic()
    prompt = (
        f"Implement the following work item:\n"
        f"```json\n{input.model_dump_json(indent=2)}\n```\n\n"
        "Return ONLY a JSON object matching BuilderOutput schema."
    )

    last_error = None
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=BUILDER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[...],  # Read, Edit, Write, Bash(pytest), Bash(ruff), Bash(mypy), Bash(python) ONLY
        )
        result_text = _extract_text(response)
        if not result_text:
            continue
        try:
            raw = _extract_json(result_text)
            output = BuilderOutput.model_validate(raw)
            logger.info("Builder Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, ValidationError) as e:
            last_error = e
            logger.warning("Builder Agent attempt %d: %s", attempt, e)
            prompt += f"\n\nValidation error:\n{e}\nReturn corrected JSON."

    raise ValueError(
        f"Builder Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. Last error: {last_error}"
    )
```

**Key differences from `linear_agent.py`:**
- NO Linear MCP tools in allowed list — Read/Edit/Write/Bash only (BLDR-04 enforcement)
- Model: `claude-sonnet-4-6` (implementation is more deterministic)
- Caller MUST fetch fresh Linear state immediately before constructing `BuilderInput` — comment at every call site (Pitfall 6 from RESEARCH.md)

---

### `src/hsb/agents/git_agent.py` (service, request-response)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — same pattern, narrowest allowed tool scope)
**Source spec:** `02-RESEARCH.md` Pattern 5 (REBASE_STACK) + `agents/AGENT-CONTRACTS.md` §5

**Imports pattern:**

```python
import json
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from hsb.contracts.git import GitInput, GitOutput

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core agent pattern:**

```python
GIT_SYSTEM_PROMPT = """
You are the Git Agent for HSBTech. Create branches and PRs according to strict naming conventions.

BRANCH NAMING (GITA-01): feature/LIN-{id}-{slug}
  Example: feature/LIN-123-add-auth-endpoint

PR TITLE (GITA-03): [LIN-{id}] {short description}
  Example: [LIN-123] Add auth endpoint

PR BASE (D-07): All task PRs target the EPIC branch directly (e.g., epic/LIN-100).
  NEVER target main directly. NEVER target another task branch.

REBASE_STACK (GITA-04): When triggered, enumerate ALL open sibling task PRs:
  gh pr list --base <epic-branch> --state open --limit 100 --json number,headRefName
  For each sibling (excluding current): git rebase --onto <epic-branch> <old-tip> <sibling-branch>
  Then: git push --force-with-lease origin <sibling-branch>
  CRITICAL: Use --force-with-lease, NEVER --force (prevents overwriting concurrent pushes).

CAPABILITY BOUNDARY (GITA-05): You MUST NOT:
- Run git merge or git push to main
- Edit or Write any source files
- Call any mcp__linear__* tools

ALLOWED TOOLS: Bash(gh pr create *), Bash(gh pr list *), Bash(gh pr view *),
  Bash(git checkout *), Bash(git push --force-with-lease *), Bash(git rebase *),
  Bash(git log *), Bash(git fetch *)

OUTPUT FORMAT: Return a JSON object matching GitOutput schema exactly.
"""

MAX_VALIDATION_RETRIES = 3

def run_git_agent(input: GitInput) -> GitOutput:
    """Execute the Git Agent synchronously. Returns validated GitOutput."""
    client = Anthropic()
    prompt = (
        f"Execute git/PR operations for the following input contract:\n"
        f"```json\n{input.model_dump_json(indent=2)}\n```\n\n"
        "Return ONLY a JSON object matching GitOutput schema."
    )

    last_error = None
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=GIT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[...],  # Bash(gh *) and Bash(git checkout/rebase/push/log/fetch) ONLY
        )
        result_text = _extract_text(response)
        if not result_text:
            continue
        try:
            raw = _extract_json(result_text)
            output = GitOutput.model_validate(raw)
            logger.info("Git Agent attempt %d: validation succeeded", attempt)
            return output
        except (ValueError, ValidationError) as e:
            last_error = e
            logger.warning("Git Agent attempt %d: %s", attempt, e)
            prompt += f"\n\nValidation error:\n{e}\nReturn corrected JSON."

    raise ValueError(
        f"Git Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. Last error: {last_error}"
    )
```

**Key differences from `linear_agent.py`:**
- Only `Bash(gh *)` and specific `Bash(git *)` commands allowed — NO Edit/Write, NO Linear MCP (GITA-05)
- `--force-with-lease` required in allowed tools, `--force` and `merge` must NOT appear
- `--limit 100` required in `gh pr list` calls to avoid Pitfall 4 (REBASE_STACK pagination)

---

### `src/hsb/agents/qa_agent.py` (service, request-response + Linear Agent import)

**Analog:** `src/hsb/agents/linear_agent.py` (Phase 1 PATTERNS.md — same validation/retry; PLUS a post-validation Linear write step)
**Source spec:** `02-RESEARCH.md` Code Examples (qa_cycle_count read source) + `02-AI-SPEC.md` §4

**Imports pattern:**

```python
import json
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from hsb.contracts.qa import QAInput, QAOutput
from hsb.agents.linear_agent import run_validated_linear_agent  # for post-validation writes

load_dotenv()

logger = logging.getLogger(__name__)
```

**Core agent pattern** (two-phase: LLM review, then Linear writes):

```python
QA_SYSTEM_PROMPT = """
You are the QA Agent for HSBTech. Review the PR diff against the Linear work item requirements.

QA CYCLE CAP (QAAG-04, D-05): Read qa_cycle_count from the input contract.
  If qa_cycle_count >= 2 (i.e., this is the 3rd review): you MUST approve with tech_debt_annotation.
  NEVER request a 4th fix cycle.

FIX SUBTASK CAP (QAAG-03): Maximum 5 findings per report. Consolidate if needed.

CAPABILITY BOUNDARY (QAAG-05): You MUST NOT:
- Edit or Write any source files
- Create PRs or branches
- Run git commands directly

ALLOWED TOOLS: Read, Bash(gh pr diff *), Bash(gh pr view *)

REVIEW DIMENSIONS:
1. Functional Correctness
2. Acceptance Criteria Compliance
3. Code Quality (clarity, simplicity, maintainability)
4. Architecture Alignment
5. Side Effects / Regression Risk
6. Edge Cases
7. Test Coverage

OUTPUT FORMAT: Return a JSON object matching QAOutput schema exactly.
"""

MAX_VALIDATION_RETRIES = 3

def run_qa_agent(input: QAInput) -> QAOutput:
    """
    Execute the QA Agent synchronously. Returns validated QAOutput.
    After validation, writes qa_cycle_count increment and fix subtasks to Linear via run_validated_linear_agent.
    Linear writes happen OUTSIDE the agent loop — QA Agent itself has no Linear tool access (QAAG-05).
    """
    client = Anthropic()
    prompt = (
        f"Review the following PR for work item {input.work_item_id}:\n"
        f"```json\n{input.model_dump_json(indent=2)}\n```\n\n"
        "Return ONLY a JSON object matching QAOutput schema."
    )

    last_error = None
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=QA_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[...],  # Read and Bash(gh pr diff *, gh pr view *) ONLY
        )
        result_text = _extract_text(response)
        if not result_text:
            continue
        try:
            raw = _extract_json(result_text)
            output = QAOutput.model_validate(raw)  # model_validator enforces cycle cap here
            logger.info("QA Agent attempt %d: validation succeeded", attempt)
            # Post-validation: write to Linear via Python import (not inside agent loop)
            _write_qa_results_to_linear(input.work_item_id, output)
            return output
        except (ValueError, ValidationError) as e:
            last_error = e
            logger.warning("QA Agent attempt %d: %s", attempt, e)
            prompt += f"\n\nValidation error:\n{e}\nReturn corrected JSON."

    raise ValueError(
        f"QA Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. Last error: {last_error}"
    )


def _write_qa_results_to_linear(work_item_id: str, output: QAOutput) -> None:
    """
    Write QA results to Linear via the Phase 1 Linear Agent service.
    Called after output contract is validated — never inside the QA Agent tool loop.
    """
    import asyncio
    # 1. Increment qa_cycle_count
    asyncio.run(run_validated_linear_agent(
        operation="update",
        payload={"issueId": work_item_id, "qa_cycle_count": output.qa_cycle_count},
    ))
    # 2. Create fix subtasks if changes_required
    if output.qa_status == "changes_required" and output.findings:
        blocking_findings = [f for f in output.findings if f.suggested_subtask][:5]
        if blocking_findings:
            asyncio.run(run_validated_linear_agent(
                operation="create_subtasks",
                payload={
                    "parentId": work_item_id,
                    "subtasks": [
                        {
                            "title": f.suggested_subtask.title,
                            "description": f.suggested_subtask.description,
                        }
                        for f in blocking_findings
                    ],
                },
            ))
```

**Key differences from `linear_agent.py`:**
- Model: `claude-opus-4-7` (complex diff analysis)
- Only Read + `Bash(gh pr diff *, gh pr view *)` in allowed tools — NO Edit/Write, NO git, NO Linear MCP (QAAG-05)
- Linear writes happen OUTSIDE the agent loop via Python import of `run_validated_linear_agent` (D-04)
- `_write_qa_results_to_linear` uses `asyncio.run()` at its call site — same pattern as Phase 1 CLI commands (synchronous boundary)

---

### `src/hsb/cli/main.py` (controller, request-response) — extend Phase 1

**Analog:** `src/hsb/cli/main.py` (Phase 1 PATTERNS.md §cli/main.py — same typer app, `asyncio.run()` pattern)
**Source spec:** `02-RESEARCH.md` §Architecture Patterns + `02-CONTEXT.md` §code_context

**Delta: add Phase 2 subcommands** (do NOT rewrite Phase 1 commands — append these to the existing file):

```python
# Additional imports at top of existing main.py
from hsb.contracts.backlog import BacklogInput, ProjectContext
from hsb.contracts.builder import BuilderInput, RepositoryContext
from hsb.contracts.git import GitInput
from hsb.contracts.qa import QAInput, PullRequestInput
from hsb.agents.backlog_agent import run_backlog_agent
from hsb.agents.builder_agent import run_builder_agent
from hsb.agents.git_agent import run_git_agent
from hsb.agents.qa_agent import run_qa_agent

# Add Phase 2 subcommand groups
backlog_app = typer.Typer(name="backlog", help="Backlog Planning Agent commands")
builder_app = typer.Typer(name="builder", help="Builder Agent commands")
git_app = typer.Typer(name="git", help="Git/PR Agent commands")
qa_app = typer.Typer(name="qa", help="QA Review Agent commands")

app.add_typer(backlog_app)
app.add_typer(builder_app)
app.add_typer(git_app)
app.add_typer(qa_app)


@backlog_app.command("create")
def backlog_create(
    plan: str = typer.Option(..., "--plan", help="Path to plan.md file (D-02: no default; FAIL if omitted)"),
    project_name: str = typer.Option(..., "--project-name"),
    repository: str = typer.Option(..., "--repository"),
):
    """Run Backlog Agent on a plan.md and create Linear hierarchy (BKPK-01 to BKPK-05)."""
    input = BacklogInput(
        plan_source=plan,
        project_context=ProjectContext(name=project_name, repository=repository),
    )
    # run_backlog_agent is synchronous — no asyncio.run() needed here (02-AI-SPEC.md §4b Async-First)
    result = run_backlog_agent(input)
    pprint(result.model_dump())


@builder_app.command("implement")
def builder_implement(
    work_item_id: str = typer.Option(..., "--issue-id"),
    plan_source: str = typer.Option(..., "--plan"),
    repo_root: str = typer.Option(".", "--repo-root"),
):
    """Run Builder Agent on a Linear work item. Fetches fresh Linear state before invoking (Pitfall 6)."""
    # ALWAYS fetch fresh Linear state immediately before constructing BuilderInput
    issue = asyncio.run(
        run_validated_linear_agent("read", {"issueId": work_item_id})
    )
    input = BuilderInput(
        work_item_id=work_item_id,
        issue_description=str(issue.linear_entities),  # adapt to actual LinearOutput shape
        acceptance_criteria=[],
        epic_context={},
        plan_source=plan_source,
        repository_context=RepositoryContext(root_path=repo_root),
    )
    result = run_builder_agent(input)
    pprint(result.model_dump())


@git_app.command("create-pr")
def git_create_pr(
    work_item_id: str = typer.Option(..., "--issue-id"),
    epic_id: str = typer.Option(..., "--epic-id"),
    implementation_output: str = typer.Option(..., "--impl-output", help="Path to BuilderOutput JSON"),
):
    """Run Git Agent: create branch + PR for a work item."""
    import json as _json
    impl_data = _json.loads(open(implementation_output).read())
    input = GitInput(
        work_item_id=work_item_id,
        implementation_output=impl_data,
        epic_id=epic_id,
    )
    result = run_git_agent(input)
    pprint(result.model_dump())


@qa_app.command("review")
def qa_review(
    work_item_id: str = typer.Option(..., "--issue-id"),
    pr_number: int = typer.Option(..., "--pr-number"),
):
    """Run QA Agent: review PR diff and write findings to Linear."""
    import subprocess
    diff = subprocess.check_output(
        ["gh", "pr", "diff", str(pr_number)], text=True
    )
    pr_url = subprocess.check_output(
        ["gh", "pr", "view", str(pr_number), "--json", "url", "--jq", ".url"], text=True
    ).strip()
    issue = asyncio.run(run_validated_linear_agent("read", {"issueId": work_item_id}))
    qa_cycle = 0  # operator provides via env or fetched from Linear metadata
    input = QAInput(
        work_item_id=work_item_id,
        linear_issue={},
        pull_request=PullRequestInput(url=pr_url, diff=diff),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=qa_cycle,
    )
    result = run_qa_agent(input)
    pprint(result.model_dump())
```

**Critical:** Agent functions (`run_backlog_agent`, `run_builder_agent`, `run_git_agent`) are synchronous — do NOT wrap in `asyncio.run()`. Only `run_validated_linear_agent` (the Phase 1 async service) requires `asyncio.run()` at the CLI boundary, same as Phase 1.

---

### `.claude/skills/backlog-planning/SKILL.md` (config)

**Analog:** `.claude/skills/linear-system-of-record/SKILL.md` (Phase 1 PATTERNS.md §SKILL.md — same frontmatter structure)
**Source spec:** `02-RESEARCH.md` Pattern 4 + `skills/01-BACKLOG-PLANNING.md` (body content)

**Frontmatter block** (copy frontmatter structure from Phase 1 linear-system-of-record SKILL.md, adapt for Backlog Agent):

```yaml
---
name: backlog-planning
description: |
  Reads a plan.md file and generates a structured EPIC → User Story → Task → Subtask backlog in Linear.
  Only invoke when: an operator explicitly provides a plan.md path and requests backlog creation.
  Do NOT invoke during conversation or without an explicit --plan argument.
disable-model-invocation: true
context: fork
allowed-tools:
  - mcp__linear__create_issue
  - mcp__linear__list_issues
  - mcp__linear__get_issue
  - Read
arguments:
  - name: plan
    description: "Absolute path to the plan.md file to process (required — FAIL if missing)"
  - name: project_name
    description: "Project name for traceability metadata"
  - name: repository
    description: "Repository URL for traceability metadata"
---
```

**Body:** Append the full content of `skills/01-BACKLOG-PLANNING.md` verbatim after the frontmatter.

**Critical:** `disable-model-invocation: true` is MANDATORY — Backlog Agent creates Linear issues as a side effect; auto-invocation from conversation would corrupt the Linear workspace (PITFALLS.md Pitfall 7, RESEARCH.md Pitfall 5).

---

### `.claude/skills/implementation/SKILL.md` (config)

**Frontmatter block:**

```yaml
---
name: implementation
description: |
  Implements a Linear work item by making code changes, running local validations, and producing an
  implementation output contract. Does NOT create branches, commit, or write to Linear.
  Only invoke when: an operator explicitly requests implementation of a specific Linear issue.
  Do NOT invoke during conversation or code review.
disable-model-invocation: true
context: fork
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(pytest *)
  - Bash(ruff *)
  - Bash(mypy *)
  - Bash(python *)
arguments:
  - name: work_item_id
    description: "Linear work item ID to implement (e.g. LIN-123)"
  - name: plan_source
    description: "Path to the plan.md that generated this work item"
---
```

**Body:** Append the full content of `skills/02-IMPLEMENTATION.md` verbatim after the frontmatter.

---

### `.claude/skills/qa-review/SKILL.md` (config)

**Frontmatter block:**

```yaml
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

**Body:** Append the full content of `skills/03-QA-REVIEW.md` verbatim after the frontmatter.

---

### `.claude/skills/git-pr-management/SKILL.md` (config)

**Frontmatter block:**

```yaml
---
name: git-pr-management
description: |
  Creates branches and PRs from local code changes. Handles REBASE_STACK for sibling task PRs.
  Only invoke when: an operator explicitly requests branch/PR creation for a completed implementation.
  Do NOT invoke during conversation or code review.
disable-model-invocation: true
context: fork
allowed-tools:
  - Bash(gh pr create *)
  - Bash(gh pr list *)
  - Bash(gh pr view *)
  - Bash(git checkout *)
  - Bash(git push --force-with-lease *)
  - Bash(git rebase *)
  - Bash(git log *)
  - Bash(git fetch *)
arguments:
  - name: work_item_id
    description: "Linear work item ID (e.g. LIN-123)"
  - name: epic_id
    description: "Parent EPIC ID (e.g. LIN-100) — determines PR base branch"
  - name: implementation_output
    description: "Path to JSON file containing BuilderOutput contract"
---
```

**Body:** Append the full content of `skills/04-GIT-PR-MANAGEMENT.md` verbatim after the frontmatter.

**Critical:** `Bash(git push --force *)` must NOT appear — only `--force-with-lease` is permitted. No `Bash(git merge *)` (GITA-05). This is stricter than the general SKILL.md pattern — enumerate exactly what is allowed.

---

### `tests/unit/test_backlog_contract.py` (test, unit)

**Analog:** `tests/test_contracts.py` (Phase 1 PATTERNS.md §test_contracts.py — same parametrized schema-drift pattern)
**Source spec:** `02-RESEARCH.md` Validation Architecture + `02-AI-SPEC.md` §5

```python
import pytest
from pydantic import ValidationError
from hsb.contracts.backlog import BacklogInput, BacklogOutput, ProjectContext, EpicItem


def test_valid_backlog_output_passes():
    output = BacklogOutput.model_validate({
        "epics": [{"title": "[EPIC] Test", "description": "desc", "acceptance_criteria": [], "user_stories": [], "tasks": []}],
        "traceability": {"plan_source": "/docs/plan.md"},
    })
    assert output.epics[0].title == "[EPIC] Test"


def test_empty_epics_fails():
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate({"epics": [], "traceability": {"plan_source": "/docs/plan.md"}})


@pytest.mark.parametrize("bad_payload,description", [
    # Extra undeclared field
    ({"epics": [{"title": "[EPIC] T", "description": "d", "acceptance_criteria": [], "user_stories": [], "tasks": []}],
      "traceability": {"plan_source": "/p"}, "unexpected_field": "boom"}, "extra field rejected"),
    # Missing traceability
    ({"epics": [{"title": "[EPIC] T", "description": "d", "acceptance_criteria": [], "user_stories": [], "tasks": []}]}, "missing traceability"),
])
def test_invalid_backlog_output_raises(bad_payload, description):
    with pytest.raises(ValidationError):
        BacklogOutput.model_validate(bad_payload)


def test_backlog_input_requires_plan_source():
    with pytest.raises(ValidationError):
        BacklogInput.model_validate({"project_context": {"name": "x", "repository": "y"}})
```

---

### `tests/unit/test_builder_contract.py` (test, unit)

**Analog:** `tests/test_contracts.py` (Phase 1 PATTERNS.md)

```python
import pytest
from pydantic import ValidationError
from hsb.contracts.builder import BuilderInput, BuilderOutput, ValidationResults, RepositoryContext


def test_valid_builder_output_passes():
    output = BuilderOutput.model_validate({
        "work_item_id": "LIN-123",
        "implementation_status": "completed",
        "summary": "Implemented feature X",
        "files_changed": [{"path": "src/x.py", "change_summary": "added X"}],
        "validation": {"build": "passed", "tests": "passed", "lint": "passed", "typecheck": "not_run"},
        "implementation_notes": {"decisions": [], "assumptions": [], "risks": [], "qa_notes": []},
    })
    assert output.implementation_status == "completed"


def test_invalid_validation_status_fails():
    with pytest.raises(ValidationError):
        BuilderOutput.model_validate({
            "work_item_id": "LIN-123", "implementation_status": "completed", "summary": "s",
            "files_changed": [],
            "validation": {"build": "unknown", "tests": "passed", "lint": "passed", "typecheck": "not_run"},
            "implementation_notes": {"decisions": [], "assumptions": [], "risks": [], "qa_notes": []},
        })


def test_builder_output_extra_field_rejected():
    with pytest.raises(ValidationError):
        BuilderOutput.model_validate({
            "work_item_id": "LIN-123", "implementation_status": "completed", "summary": "s",
            "files_changed": [], "git_branch": "feature/X",  # BLDR-04 violation
            "validation": {"build": "passed", "tests": "passed", "lint": "passed", "typecheck": "not_run"},
            "implementation_notes": {"decisions": [], "assumptions": [], "risks": [], "qa_notes": []},
        })
```

---

### `tests/unit/test_git_contract.py` (test, unit)

**Analog:** `tests/test_contracts.py` (Phase 1 PATTERNS.md)

```python
import pytest
import re
from pydantic import ValidationError
from hsb.contracts.git import GitInput, GitOutput, PullRequest, ExistingPRContext


BRANCH_PATTERN = re.compile(r"^feature/LIN-\d+-[a-z0-9-]+$")
PR_TITLE_PATTERN = re.compile(r"^\[LIN-\d+\]")


def test_valid_git_output_passes():
    output = GitOutput.model_validate({
        "work_item_id": "LIN-123",
        "branch": "feature/LIN-123-add-auth",
        "commits": ["abc123"],
        "pull_request": {
            "url": "https://github.com/org/repo/pull/42",
            "title": "[LIN-123] Add auth endpoint",
            "base": "epic/LIN-100",
            "head": "feature/LIN-123-add-auth",
        },
    })
    assert BRANCH_PATTERN.match(output.branch), f"Branch '{output.branch}' does not match naming convention GITA-01"
    assert PR_TITLE_PATTERN.match(output.pull_request.title), f"PR title '{output.pull_request.title}' missing Linear ID GITA-03"


def test_git_output_extra_field_rejected():
    """GITA-05: Git Agent must not include merge or main push evidence."""
    with pytest.raises(ValidationError):
        GitOutput.model_validate({
            "work_item_id": "LIN-123",
            "branch": "feature/LIN-123-add-auth",
            "commits": [],
            "pull_request": {"url": "x", "title": "[LIN-123] x", "base": "epic/LIN-100", "head": "feature/LIN-123-add-auth"},
            "merged_to_main": True,  # extra field — must be rejected
        })


def test_branch_naming_regex():
    """Assert the branch naming convention pattern (GITA-01)."""
    valid = ["feature/LIN-1-slug", "feature/LIN-999-long-slug-name"]
    invalid = ["LIN-123-slug", "feature/lin-123-slug", "feature/LIN-123"]
    for b in valid:
        assert BRANCH_PATTERN.match(b), f"Should be valid: {b}"
    for b in invalid:
        assert not BRANCH_PATTERN.match(b), f"Should be invalid: {b}"
```

---

### `tests/unit/test_qa_contract.py` (test, unit + model_validator)

**Analog:** `tests/test_contracts.py` + `tests/test_hooks.py` (Phase 1 PATTERNS.md — combines schema validation with logic validation)

```python
import pytest
from pydantic import ValidationError
from hsb.contracts.qa import QAInput, QAOutput, QAFinding, QAEvidence


VALID_FINDING = {
    "title": "Missing null check",
    "severity": "high",
    "category": "functional",
    "status": "blocking",
    "problem": "x is None causes crash",
    "evidence": {"file": "src/x.py", "component": "XClass", "location": "line 42", "related_requirement": "LIN-123 AC-1"},
    "expected_behavior": "Returns 0 on None input",
    "actual_behavior": "Raises TypeError",
    "suggested_fix": "Add null guard",
}

VALID_APPROVED_OUTPUT = {
    "work_item_id": "LIN-123",
    "qa_status": "approved",
    "qa_cycle_count": 1,
    "summary": "No issues found",
    "findings": [],
}


def test_valid_approved_output_passes():
    output = QAOutput.model_validate(VALID_APPROVED_OUTPUT)
    assert output.qa_status == "approved"


def test_findings_max_5_enforced():
    """QAAG-03: Hard cap of 5 findings."""
    with pytest.raises(ValidationError):
        QAOutput.model_validate({
            **VALID_APPROVED_OUTPUT,
            "qa_status": "changes_required",
            "findings": [VALID_FINDING] * 6,  # 6 > max_length=5
        })


def test_cycle_cap_at_3_blocks_changes_required():
    """QAAG-04: At qa_cycle_count=3, status must be approved. model_validator enforces this."""
    with pytest.raises(ValidationError, match="qa_cycle_count >= 3"):
        QAOutput.model_validate({
            "work_item_id": "LIN-123",
            "qa_status": "changes_required",
            "qa_cycle_count": 3,
            "summary": "Still has issues",
            "findings": [VALID_FINDING],
        })


def test_cycle_cap_at_3_requires_tech_debt_annotation():
    """QAAG-04: At qa_cycle_count=3, tech_debt_annotation required."""
    with pytest.raises(ValidationError, match="tech_debt_annotation required"):
        QAOutput.model_validate({
            "work_item_id": "LIN-123",
            "qa_status": "approved",
            "qa_cycle_count": 3,
            "summary": "Approved with tech debt",
            "findings": [],
            # Missing tech_debt_annotation — must raise
        })


def test_cycle_cap_at_3_approved_with_annotation_passes():
    """QAAG-04: Approved at cycle 3 with annotation is valid."""
    output = QAOutput.model_validate({
        "work_item_id": "LIN-123",
        "qa_status": "approved",
        "qa_cycle_count": 3,
        "summary": "Approved on 3rd cycle",
        "findings": [],
        "tech_debt_annotation": "Known limitation: missing edge case coverage deferred to backlog item LIN-200",
    })
    assert output.qa_status == "approved"
    assert output.tech_debt_annotation is not None


def test_qa_output_extra_field_rejected():
    with pytest.raises(ValidationError):
        QAOutput.model_validate({**VALID_APPROVED_OUTPUT, "git_branch_created": "feature/x"})
```

---

### `tests/integration/test_backlog_agent.py` (test, integration)

**Analog:** `tests/test_integration.py` (Phase 1 PATTERNS.md §test_integration.py — same `@pytest.mark.integration` pattern)

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_parse_plan_and_create_linear_hierarchy(tmp_path):
    """BKPK-01 to BKPK-04: Backlog Agent creates EPIC → Story → Task in Linear."""
    from hsb.agents.backlog_agent import run_backlog_agent
    from hsb.contracts.backlog import BacklogInput, ProjectContext

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Feature A\nBuild user authentication.\n## Goal\nSecure login.")

    input = BacklogInput(
        plan_source=str(plan_file),
        project_context=ProjectContext(name="test", repository="hsb-test-fixture"),
    )
    output = run_backlog_agent(input)
    assert len(output.epics) >= 1
    assert output.traceability.plan_source == str(plan_file)


@pytest.mark.integration
async def test_idempotency_no_duplicate_epics(tmp_path):
    """BKPK-05: Running Backlog Agent twice on the same plan does not create duplicate EPICs."""
    from hsb.agents.backlog_agent import run_backlog_agent
    from hsb.contracts.backlog import BacklogInput, ProjectContext

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Feature B\nBuild payment flow.")

    input = BacklogInput(
        plan_source=str(plan_file),
        project_context=ProjectContext(name="test", repository="hsb-test-fixture"),
    )
    output1 = run_backlog_agent(input)
    output2 = run_backlog_agent(input)
    # Idempotency: same EPIC count, no duplicates (BKPK-05, Pitfall 1)
    assert len(output1.epics) == len(output2.epics)
```

---

### `tests/integration/test_builder_agent.py` (test, integration)

**Analog:** `tests/test_integration.py` (Phase 1 PATTERNS.md)

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_scoped_implementation():
    """BLDR-01, BLDR-02: Builder Agent implements work item and runs validations."""
    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext

    input = BuilderInput(
        work_item_id="LIN-TEST-1",
        issue_description="Add a hello() function to src/fixture/hello.py",
        acceptance_criteria=["Function returns 'hello world'"],
        epic_context={},
        plan_source="/docs/plan.md",
        repository_context=RepositoryContext(root_path="/path/to/hsb-test-fixture"),
    )
    output = run_builder_agent(input)
    assert output.implementation_status in ("completed", "blocked", "failed")
    assert output.validation.tests in ("passed", "failed", "not_run")


@pytest.mark.integration
async def test_capability_boundary_no_git_or_linear(mocker):
    """BLDR-04: Builder Agent must not produce git or Linear evidence in output."""
    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext
    # Inspect output contract — no branch, no Linear ID fields should appear
    # (Pydantic extra="forbid" makes this structural, but integration test confirms via tracing)
    ...
```

---

### `tests/integration/test_git_agent.py` (test, integration)

**Analog:** `tests/test_integration.py` (Phase 1 PATTERNS.md)

```python
import pytest
import re

pytestmark = [pytest.mark.integration]

BRANCH_PATTERN = re.compile(r"^feature/LIN-\d+-[a-z0-9-]+$")
PR_TITLE_PATTERN = re.compile(r"^\[LIN-\d+\]")


@pytest.mark.integration
async def test_branch_naming_convention():
    """GITA-01: Branch matches feature/LIN-{id}-{slug}."""
    from hsb.agents.git_agent import run_git_agent
    from hsb.contracts.git import GitInput

    input = GitInput(
        work_item_id="LIN-TEST-2",
        implementation_output={"files_changed": []},
        epic_id="LIN-TEST-100",
    )
    output = run_git_agent(input)
    assert BRANCH_PATTERN.match(output.branch), f"Branch naming violated GITA-01: {output.branch}"
    assert PR_TITLE_PATTERN.match(output.pull_request.title), f"PR title missing LIN ID (GITA-03): {output.pull_request.title}"
    assert "LIN-TEST-100" in output.pull_request.base or "epic" in output.pull_request.base, "PR must target EPIC branch (D-07)"
```

---

### `tests/integration/test_qa_agent.py` (test, integration)

**Analog:** `tests/test_integration.py` (Phase 1 PATTERNS.md)

```python
import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.integration
async def test_qa_review_produces_valid_contract():
    """QAAG-01, QAAG-02: QA Agent produces valid findings contract."""
    from hsb.agents.qa_agent import run_qa_agent
    from hsb.contracts.qa import QAInput, PullRequestInput

    input = QAInput(
        work_item_id="LIN-TEST-3",
        linear_issue={},
        pull_request=PullRequestInput(url="https://github.com/org/repo/pull/1", diff="--- a/x.py\n+++ b/x.py"),
        implementation_notes={},
        epic_context={},
        qa_cycle_count=0,
    )
    output = run_qa_agent(input)
    assert output.qa_status in ("approved", "changes_required")
    assert len(output.findings) <= 5  # QAAG-03


@pytest.mark.integration
async def test_capability_boundary_no_code_edits():
    """QAAG-05: QA Agent must not modify any files."""
    # Inspect tool calls in Phoenix traces after run — assert no Edit/Write calls
    ...
```

---

## Shared Patterns

### Pattern: `extra="forbid"` on all pydantic models

**Source:** Phase 1 PATTERNS.md §Shared Patterns; `02-RESEARCH.md` Anti-Patterns §5
**Apply to:** Every `BaseModel` subclass in `src/hsb/contracts/backlog.py`, `builder.py`, `git.py`, `qa.py`

```python
model_config = {"extra": "forbid"}
```

Absent on any model → silent schema drift passes undetected (PITFALLS.md Pitfall 4). This is the #1 defense against the "Silent contract failure" critical failure mode in `02-AI-SPEC.md` §1.

---

### Pattern: Synchronous Anthropic client (not `asyncio.run` inside agents)

**Source:** `02-AI-SPEC.md` §4b Async-First Design; Phase 1 PATTERNS.md §Shared Patterns
**Apply to:** All `run_<agent>_agent()` functions in `src/hsb/agents/`

```python
# CORRECT — Phase 2 agents use synchronous Anthropic client
from anthropic import Anthropic

def run_backlog_agent(input: BacklogInput) -> BacklogOutput:
    client = Anthropic()
    response = client.messages.create(...)
    ...

# WRONG — Phase 2 agents are not coroutines; no asyncio needed
async def run_backlog_agent(input: BacklogInput) -> BacklogOutput:  # do not do this
    ...
```

`asyncio.run()` is only used at the CLI boundary when calling the Phase 1 `run_validated_linear_agent()` async function — not inside agent functions themselves.

---

### Pattern: `load_dotenv()` at module level in every agent file

**Source:** Phase 1 PATTERNS.md §Shared Patterns §load_dotenv
**Apply to:** All four `src/hsb/agents/` files

```python
from dotenv import load_dotenv
load_dotenv()  # Must be before any os.environ or Anthropic() call
```

---

### Pattern: MAX_VALIDATION_RETRIES = 3 retry loop

**Source:** Phase 1 PATTERNS.md §linear_agent.py §Validation and retry layer pattern
**Apply to:** All four `run_<agent>_agent()` functions

```python
MAX_VALIDATION_RETRIES = 3

for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
    result_text = ... # call Anthropic client
    try:
        raw = _extract_json(result_text)
        output = SomeOutput.model_validate(raw)
        return output
    except (ValueError, ValidationError) as e:
        prompt += f"\n\nValidation error on previous attempt:\n{e}\nReturn corrected JSON."

raise ValueError(f"Agent failed validation after {MAX_VALIDATION_RETRIES} attempts.")
```

---

### Pattern: `disable-model-invocation: true` in every Phase 2 SKILL.md

**Source:** Phase 1 PATTERNS.md §SKILL.md; `02-RESEARCH.md` Pitfall 5
**Apply to:** All four `.claude/skills/<name>/SKILL.md` files

Every Phase 2 agent creates side effects (Linear issues, branches, PRs, code changes). None may be auto-invoked from conversation. This frontmatter field is MANDATORY.

---

### Pattern: Capability boundary dual enforcement

**Source:** `02-RESEARCH.md` §Architectural Responsibility Map; `02-AI-SPEC.md` §6 Guardrails
**Apply to:** Every `run_<agent>_agent()` function AND every SKILL.md frontmatter

Both layers must agree on the allowed tools. If SKILL.md says `allowed-tools: [Read, Edit, Write]`, the Python `client.messages.create(tools=[...])` must not include `mcp__linear__*` or `Bash(git *)`. Neither layer alone is sufficient — the SDK enforces SKILL.md at interactive layer only; Python-level `tools=[]` enforces at programmatic layer.

```python
# CORRECT: Python layer explicitly scopes tools (matches SKILL.md allowed-tools)
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[READ_TOOL, EDIT_TOOL, WRITE_TOOL, BASH_PYTEST, BASH_RUFF, BASH_MYPY],
    # NO mcp__linear__ tools here even though linear_agent.py is importable
    ...
)

# WRONG: Wildcard or broad tool list defeats the boundary enforcement
response = client.messages.create(
    tools=ALL_AVAILABLE_TOOLS,  # includes Linear MCP — violates BLDR-04
    ...
)
```

---

### Pattern: Linear writes via Python import, not inside agent tool loop

**Source:** `02-RESEARCH.md` §Architectural Responsibility Map; `02-CONTEXT.md` D-04
**Apply to:** `src/hsb/agents/qa_agent.py`

QA Agent reads diffs and writes findings as output contract. Linear writes (incrementing `qa_cycle_count`, creating fix subtasks) happen AFTER the agent tool loop completes, via `run_validated_linear_agent()` imported from Phase 1. This is the same pattern as QA Agent calling a service, not calling a tool.

```python
# CORRECT: Linear write happens post-validation, outside agent loop
output = QAOutput.model_validate(raw)
_write_qa_results_to_linear(input.work_item_id, output)  # Python function call, not tool call

# WRONG: Including mcp__linear__* in QA Agent's allowed tools
tools=[READ_TOOL, BASH_GH_DIFF, MCP_LINEAR_UPDATE]  # violates QAAG-05
```

---

### Pattern: `@pytest.mark.integration` and `pytestmark` for all integration tests

**Source:** Phase 1 PATTERNS.md §test_integration.py
**Apply to:** All files in `tests/integration/`

```python
import pytest
pytestmark = [pytest.mark.integration]

@pytest.mark.integration
async def test_something_live():
    ...
```

Run with: `pytest tests/integration/ -v -m integration`
Skip with: `pytest tests/unit/ -x` (default, no real services needed)

---

## No Analog Found

All Phase 2 files have strong analogs in Phase 1 PATTERNS.md or project specification documents. No files lack a pattern source.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | — | — | All Phase 2 files follow the Phase 1 Python foundation pattern or SKILL.md frontmatter pattern |

---

## Metadata

**Analog search scope:** Phase 1 PATTERNS.md (primary), `02-AI-SPEC.md`, `02-RESEARCH.md`, `agents/AGENT-CONTRACTS.md`, `skills/01-04` skill specs
**Files scanned:** Phase 1 PATTERNS.md, 02-CONTEXT.md, 02-RESEARCH.md, 02-AI-SPEC.md, AGENT-CONTRACTS.md, skills/01-04, 01-CONTEXT.md
**Python source files found:** 0 (greenfield; Phase 1 not yet executed)
**Pattern extraction date:** 2026-05-05
**Primary pattern source:** Phase 1 PATTERNS.md (all Phase 2 files are direct structural extensions of Phase 1 patterns)
