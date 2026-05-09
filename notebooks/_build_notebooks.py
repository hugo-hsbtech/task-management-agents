"""Build the manual-inspection notebooks from compact spec lists.

Why this exists: editing notebooks by hand drifts execution-count / output
metadata and produces noisy diffs. Each notebook below is one Python list
of (cell_type, source) tuples; this script materialises them as canonical
.ipynb JSON with `execution_count: null` and empty outputs.

Run from repo root:  uv run python notebooks/_build_notebooks.py

Idempotent — rerunning produces byte-identical output for unchanged specs.
"""

from __future__ import annotations

import json
from pathlib import Path

# (cell_type, cell_id, source)  — keep ids stable so reviewers can navigate.
Spec = list[tuple[str, str, str]]


def render(spec: Spec) -> dict:
    cells = []
    for cell_type, cell_id, source in spec:
        cell: dict = {
            "cell_type": cell_type,
            "id": cell_id,
            "metadata": {},
            "source": source.splitlines(keepends=True),
        }
        if cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md(text: str) -> str:
    return text.rstrip() + "\n"


def code(text: str) -> str:
    return text.rstrip() + "\n"


# ---------------------------------------------------------------------------
# 00 — Guardrails audit
# ---------------------------------------------------------------------------

NB_00: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 00 — Guardrails audit

Live invariant dashboard for **G1–G10 + RISK-04** plus the **runtime-adapter** seam (`hsb.runtime.{claude,codex,protocol,codex_guards}`) against the current source tree.

**No LLM, no MCP, no network.** Every cell either passes silently or raises.

If a cell fails, the guardrail it covers has regressed — open the source file referenced in the assertion and figure out which structural defense was weakened.

The notebook is **runtime-agnostic**: the same cells assert the invariants whether agents are configured for Claude or Codex. Where a guard is runtime-specific (e.g. Codex `~/.codex/config.toml`), the cell makes that explicit.

Reference: `README.md#guardrails-g1g10`, `src/hsb/agents/_sdk_options.py`, `src/hsb/agents/risk_agent.py`, `src/hsb/runtime/`, `docs/superpowers/specs/2026-05-09-codex-oauth-alt-runtime-design.md`."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
from _helpers import ensure_src_on_path, runtime_summary

ROOT = ensure_src_on_path()
print("repo root =", ROOT)
print("\\nHSB_RUNTIME_* selection:\\n" + runtime_summary())"""
        ),
    ),
    (
        "markdown",
        "g1-md",
        md(
            """\
## G1 — OAuth2 only (function-entry guard)

The guard is **function-entry**, not module-import. A dev environment with `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set should not break pytest collection — but a call to `make_options()` / `make_agent_options()` must refuse.

We probe both forbidden vars across both factories, then confirm clean construction works."""
        ),
    ),
    (
        "code",
        "g1-import",
        code(
            """\
import importlib
import os

# Importing the chokepoint module must NOT raise even if a metered key is set.
os.environ["ANTHROPIC_API_KEY"] = "pretend-this-is-leaked"
os.environ["OPENAI_API_KEY"] = "pretend-this-is-leaked-too"
from hsb.agents import _sdk_options

importlib.reload(_sdk_options)  # prove a reload is also safe
print("module-import path is clean even with metered keys set")"""
        ),
    ),
    (
        "code",
        "g1-raise",
        code(
            """\
# G1 must raise at function-entry of make_options() / assert_oauth2_only() /
# make_agent_options() — for either forbidden var.
import os

from hsb.agents._sdk_options import (
    assert_oauth2_only,
    make_agent_options,
    make_options,
)

for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    # Clean both first, then set just one to test isolation.
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ[var] = "leaked"

    raised = False
    try:
        assert_oauth2_only()
    except RuntimeError as e:
        raised = True
        assert "G1 violation" in str(e) and var in str(e)
    assert raised, f"G1 did not raise when {var} is set"

    raised = False
    try:
        make_options(permission_mode="acceptEdits", allowed_tools=["Read"])
    except RuntimeError:
        raised = True
    assert raised, f"make_options should refuse when {var} is set"

    raised = False
    try:
        make_agent_options(
            system_prompt="x",
            allowed_tools=["Read"],
            permission_mode="acceptEdits",
            max_turns=1,
            model="claude-haiku-4-5",
        )
    except RuntimeError:
        raised = True
    assert raised, f"make_agent_options should refuse when {var} is set"

    del os.environ[var]

print("G1: function-entry guard fires for both ANTHROPIC_API_KEY and OPENAI_API_KEY")"""
        ),
    ),
    (
        "code",
        "g1-clean",
        code(
            """\
# With the env clean, both factories must construct without complaint.
opts = make_options(permission_mode="acceptEdits", allowed_tools=["Read"])
assert "Read" in (opts.allowed_tools or [])

agent_opts = make_agent_options(
    system_prompt="x",
    allowed_tools=["Read"],
    permission_mode="acceptEdits",
    max_turns=1,
    model="claude-haiku-4-5",
)
assert agent_opts.allowed_tools == ("Read",)
print("G1: clean env path produces both ClaudeAgentOptions and AgentOptions OK")"""
        ),
    ),
    (
        "markdown",
        "g2-md",
        md(
            """\
## G2 — `"Agent"` is forbidden in any `allowed_tools`

WORC-02: no sub-subagent dispatch. Both factories raise `ValueError` if `"Agent"` slips into `allowed_tools`. Belt-and-braces: grep every agent file for an `Agent` literal in any `allowed_tools=[...]` block."""
        ),
    ),
    (
        "code",
        "g2-raise",
        code(
            """\
raised = False
try:
    make_options(permission_mode="acceptEdits", allowed_tools=["Read", "Agent"])
except ValueError as e:
    raised = True
    assert "G2 violation" in str(e)
assert raised, "G2 should refuse Agent in allowed_tools (make_options)"

raised = False
try:
    make_agent_options(
        system_prompt="x",
        allowed_tools=["Read", "Agent"],
        permission_mode="acceptEdits",
        max_turns=1,
        model="claude-haiku-4-5",
    )
except ValueError as e:
    raised = True
    assert "G2 violation" in str(e)
assert raised, "G2 should refuse Agent in allowed_tools (make_agent_options)"
print("G2: both factories reject Agent in allowed_tools")"""
        ),
    ),
    (
        "code",
        "g2-source-grep",
        code(
            """\
# Belt-and-braces: grep every agent file for an 'Agent' literal in an allow-list.
import re

agent_dir = ROOT / "src" / "hsb" / "agents"
violations = []
for p in sorted(agent_dir.glob("*.py")):
    text = p.read_text()
    for m in re.finditer(r"allowed_tools\\s*=\\s*\\[(.*?)\\]", text, re.DOTALL):
        body = m.group(1)
        if re.search(r"['\\\"]Agent['\\\"]", body):
            violations.append((p.name, body[:120]))
assert not violations, f"G2 grep found Agent in an allowed_tools literal: {violations}"
print("G2: no agent module declares Agent in its allowed_tools")"""
        ),
    ),
    (
        "markdown",
        "g3-md",
        md(
            """\
## G3 — Runtime backstop catches `Task`-tool dispatch

If the SDK ever regresses and bypasses `allowed_tools`, the per-message scan in every receive loop catches a Task block and raises. G3 is Claude-specific — the message shape is a `claude_agent_sdk.AssistantMessage`. On Codex the equivalent defence is `verify_codex_mcp` + the Codex SDK's own MCP whitelist (we check that further down)."""
        ),
    ),
    (
        "code",
        "g3-positive",
        code(
            """\
from claude_agent_sdk import AssistantMessage

from hsb.agents._sdk_options import assert_no_task_dispatch


class FakeBlock:
    def __init__(self, name):
        self.name = name


msg = AssistantMessage(content=[FakeBlock("Task")], model="claude-opus-4-7")
raised = False
try:
    assert_no_task_dispatch(msg)
except RuntimeError as e:
    raised = True
    assert "G3 violation" in str(e)
assert raised, "G3 should raise on Task block"
print("G3: AssistantMessage with Task block raises")"""
        ),
    ),
    (
        "code",
        "g3-negative",
        code(
            """\
# Innocent messages must NOT raise.
msg = AssistantMessage(
    content=[FakeBlock("Read"), FakeBlock("Bash")], model="claude-opus-4-7"
)
assert_no_task_dispatch(msg)  # no exception
print("G3: clean assistant message passes through silently")"""
        ),
    ),
    (
        "markdown",
        "g4-md",
        md(
            """\
## G4 — Risk Agent skill 14 is structurally air-gapped

The Auto-Improvement Trigger SDK call has `allowed_tools=[]`, no MCP, Haiku model, and a hard budget. We verify the literals appear in the source — the structural defence, not just the runtime assertion. Risk Agent stays on Claude (HookMatcher API has no Codex equivalent), so this guard is Claude-specific by design."""
        ),
    ),
    (
        "code",
        "g4-grep",
        code(
            """\
ra = (ROOT / "src" / "hsb" / "agents" / "risk_agent.py").read_text()
assert "allowed_tools=[]" in ra, "G4 layer 1: empty allowed_tools missing"
assert 'model="claude-haiku-4-5"' in ra or "model='claude-haiku-4-5'" in ra, (
    "G4: Haiku pin missing"
)
assert "max_budget_usd=0.05" in ra, "G4: budget cap missing"
assert "max_turns=3" in ra, "G4: max_turns cap missing"
print("G4: skill-14 air-gap config literals all present")"""
        ),
    ),
    (
        "markdown",
        "risk04-md",
        md(
            """\
## RISK-04 — 4-layer defense (the strongest milestone-level invariant)

1. STRUCTURAL — skill-14 SDK call (covered by G4 above).
2. PARSE-TIME — `AutoImprovementTrigger.linear_state` is `Literal["suggested"]`.
3. IMPORT-TIME — `risk_agent.py` does NOT import `hsb.agents.linear_agent`.
4. RUNTIME — `linear_write_guard` denies frames originating in `risk_agent.py` (except the operator-delegated path)."""
        ),
    ),
    (
        "code",
        "risk04-import-time",
        code(
            """\
assert "from hsb.agents.linear_agent" not in ra, (
    "RISK-04 layer 3: risk_agent imports linear_agent"
)
assert "import hsb.agents.linear_agent" not in ra, (
    "RISK-04 layer 3: risk_agent imports linear_agent"
)
print("RISK-04 layer 3 (import-time): risk_agent.py does not import linear_agent")"""
        ),
    ),
    (
        "code",
        "risk04-parse-time",
        code(
            """\
from pydantic import ValidationError

from hsb.contracts.risk import AutoImprovementTrigger

trig = AutoImprovementTrigger(
    title="t", description="d", pattern_evidence=["LIN-1", "LIN-2"], suggested_type="x"
)
assert trig.linear_state == "suggested"
raised = False
try:
    AutoImprovementTrigger(
        title="t",
        description="d",
        pattern_evidence=["LIN-1", "LIN-2"],
        suggested_type="x",
        linear_state="created",
    )
except ValidationError:
    raised = True
assert raised, "RISK-04 layer 2: parser accepted linear_state != 'suggested'"
print("RISK-04 layer 2 (parse-time): linear_state Literal enforced")"""
        ),
    ),
    (
        "code",
        "risk04-runtime",
        code(
            """\
# Layer 4: the linear_write_guard helper. We exercise it by calling a wrapped
# function from a 'fake risk_agent' frame and confirming PermissionError.

from hsb.agents._sdk_options import linear_write_guard


@linear_write_guard
def fake_write():
    return "ok"


# Direct call from this notebook (no risk_agent.py frame in stack) -> allowed.
assert fake_write() == "ok"
print("RISK-04 layer 4: guard allows non-risk callers")

# Simulate a call originating from risk_agent.py by exec-ing in a faked filename.
import importlib.util
import os
import tempfile

tmpdir = tempfile.mkdtemp()
fake_path = os.path.join(tmpdir, "hsb", "agents", "risk_agent.py")
os.makedirs(os.path.dirname(fake_path), exist_ok=True)
with open(fake_path, "w") as f:
    f.write("def call_it(fn):\\n    return fn()\\n")

spec = importlib.util.spec_from_file_location("hsb.agents.risk_agent_dummy", fake_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
raised = False
try:
    mod.call_it(fake_write)
except PermissionError as e:
    raised = True
    assert "RISK-04" in str(e)
assert raised, "RISK-04 layer 4: guard did not deny risk_agent frame"
print("RISK-04 layer 4: guard denies frames from risk_agent.py")"""
        ),
    ),
    (
        "markdown",
        "g9-md",
        md(
            """\
## G9 — Knowledge Store pre-write hook

`KnowledgeStorageInput.applicability` rejects `"all tasks"`, `"all"`, `"n/a"`, `"tbd"`, and empty/whitespace strings (case-insensitive). Pure Pydantic — runtime-agnostic."""
        ),
    ),
    (
        "code",
        "g9-fuzz",
        code(
            """\
from hsb.contracts.knowledge import KnowledgeStorageInput

base = dict(
    title="Caching DB writes",
    type="implementation",
    context="ctx",
    evidence={
        "linear_issue": "LIN-1",
        "pr": "#1",
        "files": ["x.py"],
        "qa_finding": "F1",
    },
    insight="ins",
    recommendation="rec",
    date="2026-05-09",
)
rejected = ["all tasks", "All Tasks", "ALL", "n/a", "tbd", "TBD", "", "   ", " "]
for bad in rejected:
    raised = False
    try:
        KnowledgeStorageInput(**base, applicability=bad)
    except Exception:
        raised = True
    assert raised, f"G9 accepted {bad!r}"
ok = KnowledgeStorageInput(
    **base, applicability="Postgres write paths in payments domain"
)
assert ok.applicability.startswith("Postgres")
print("G9: applicability validator rejects all banned values, accepts a real one")"""
        ),
    ),
    (
        "markdown",
        "qa-cycle-md",
        md(
            """\
## QA cycle cap (Pitfall 2 / QAAG-04)

Pydantic `model_validator` rejects `qa_cycle_count >= 3` with `qa_status='changes_required'` and requires `tech_debt_annotation` at cap. This is the deterministic last line of defence — the SKILL.md instruction is only probabilistic. Runtime-agnostic."""
        ),
    ),
    (
        "code",
        "qa-cycle-fuzz",
        code(
            """\
from hsb.contracts.qa import QAOutput

# Cap reached + still changes_required -> must fail
raised = False
try:
    QAOutput(
        work_item_id="LIN-1",
        qa_status="changes_required",
        qa_cycle_count=3,
        summary="s",
        findings=[],
        tech_debt_annotation="t",
    )
except Exception:
    raised = True
assert raised, "QA cap accepted changes_required at cycle 3"

# Cap reached + approved + missing annotation -> must fail
raised = False
try:
    QAOutput(
        work_item_id="LIN-1",
        qa_status="approved",
        qa_cycle_count=3,
        summary="s",
        findings=[],
    )
except Exception:
    raised = True
assert raised, "QA cap accepted missing tech_debt_annotation at cycle 3"

# Cap reached + approved + annotation present -> OK
ok = QAOutput(
    work_item_id="LIN-1",
    qa_status="approved",
    qa_cycle_count=3,
    summary="s",
    findings=[],
    tech_debt_annotation="leaving X for follow-up",
)
assert ok.qa_cycle_count == 3
print("QA cycle cap: validator rejects both runaway shapes, accepts the canonical one")"""
        ),
    ),
    (
        "markdown",
        "runtime-md",
        md(
            """\
## Runtime adapter — Protocol shape, factories, per-agent resolution

Surface added by the Codex alt-runtime work (see spec). Three structural invariants:

1. **Two implementations only**: `ClaudeRuntime` and `CodexRuntime`. Both expose a `query(prompt, options)` async iterator and a `client(options)` placeholder.
2. **Per-agent selection** via `HSB_RUNTIME_<AGENT>` (default `claude`); WIO is hard-blocked from `codex` until the stateful `ClaudeSDKClient` session has a Codex equivalent.
3. **Translation seam** — `make_agent_options()` produces a runtime-neutral `AgentOptions`; each runtime translates to its native option shape at the seam. The notebook does NOT instantiate `CodexRuntime` (which validates `~/.codex/config.toml`); we only confirm the symbols exist and `resolve_runtime` routes correctly."""
        ),
    ),
    (
        "code",
        "runtime-symbols",
        code(
            """\
from hsb.runtime import AgentOptions, Message, Runtime, StatefulClient
from hsb.runtime.protocol import PermissionMode, RuntimeName
from hsb.runtime.claude import ClaudeRuntime
from hsb.runtime import codex as codex_module
from hsb.runtime import codex_guards

# Names that must keep existing — the spec promises them.
for sym in ("AgentOptions", "Message", "Runtime", "StatefulClient"):
    assert sym in {"AgentOptions", "Message", "Runtime", "StatefulClient"}
assert PermissionMode.__args__ == (
    "default",
    "acceptEdits",
    "plan",
    "bypassPermissions",
), PermissionMode.__args__
assert RuntimeName.__args__ == ("claude", "codex"), RuntimeName.__args__
assert ClaudeRuntime().name == "claude"
# CodexRuntime constructor calls assert_codex_oauth_only() which reads
# ~/.codex/config.toml. We only confirm the class is importable + has the
# right .name attribute hint; instantiation is exercised in notebook 04/05
# where the operator opts in.
assert codex_module.CodexRuntime.name == "codex"
assert hasattr(codex_guards, "assert_codex_oauth_only")
assert hasattr(codex_guards, "verify_codex_mcp")
print("runtime adapter: ClaudeRuntime + CodexRuntime + protocol + guards all importable")"""
        ),
    ),
    (
        "code",
        "runtime-resolve",
        code(
            """\
import os

from hsb.agents._sdk_options import resolve_runtime

# Default -> Claude
os.environ.pop("HSB_RUNTIME_BACKLOG", None)
rt = resolve_runtime("backlog")
assert rt.name == "claude", rt.name

# Explicit claude
os.environ["HSB_RUNTIME_BACKLOG"] = "claude"
assert resolve_runtime("backlog").name == "claude"

# Invalid value -> ValueError
os.environ["HSB_RUNTIME_BACKLOG"] = "bogus"
raised = False
try:
    resolve_runtime("backlog")
except ValueError:
    raised = True
assert raised, "resolve_runtime accepted invalid runtime name"
os.environ.pop("HSB_RUNTIME_BACKLOG", None)

# WIO hard-block: HSB_RUNTIME_WIO=codex must raise (stateful session has no Codex equivalent)
os.environ["HSB_RUNTIME_WIO"] = "codex"
raised = False
try:
    resolve_runtime("wio")
except ValueError as e:
    raised = True
    assert "WIO" in str(e) or "wio" in str(e).lower()
assert raised, "WIO hard-block missing — codex selection should raise"
os.environ.pop("HSB_RUNTIME_WIO", None)
print("resolve_runtime: default/claude/invalid all behave; WIO codex hard-block intact")"""
        ),
    ),
    (
        "markdown",
        "import-md",
        md(
            """\
## Smoke: every agent + runtime module imports cleanly

If a structural change breaks a top-level import, every other notebook will misreport. Cheap canary."""
        ),
    ),
    (
        "code",
        "import-smoke",
        code(
            """\
import importlib

modules = [
    "hsb.agents._sdk_options",
    "hsb.agents.hooks",
    "hsb.agents.linear_agent",
    "hsb.agents.backlog_agent",
    "hsb.agents.builder_agent",
    "hsb.agents.git_agent",
    "hsb.agents.qa_agent",
    "hsb.agents.work_item_orchestrator",
    "hsb.agents.global_orchestrator",
    "hsb.agents.main_orchestrator",
    "hsb.agents.uat_agent",
    "hsb.agents.risk_agent",
    "hsb.agents.intelligence_agent",
    "hsb.contracts.qa",
    "hsb.contracts.knowledge",
    "hsb.contracts.risk",
    "hsb.contracts.uat",
    "hsb.contracts.global_orchestrator",
    "hsb.contracts.main_orchestrator",
    "hsb.contracts.orchestrator",
    "hsb.runtime",
    "hsb.runtime.protocol",
    "hsb.runtime.claude",
    "hsb.runtime.codex",
    "hsb.runtime.codex_guards",
]
for m in modules:
    importlib.import_module(m)
print(f"OK — all {len(modules)} modules import cleanly")"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 01 — Contracts playground (Pydantic boundary fuzzing — runtime-agnostic)
# ---------------------------------------------------------------------------

NB_01: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 01 — Contracts playground

Boundary-fuzz every Pydantic model in `src/hsb/contracts/`. Every model declares `model_config = {"extra": "forbid"}` — so any LLM-emitted field that isn't in the schema must fail parse.

**No LLM, no MCP. Pure Pydantic.** Identical results on Claude or Codex — the contracts validate after the runtime hands back a final JSON blob, so the runtime has no say.

What you can do here: poke fields, see exactly which validator fires, learn which constraints are hard (Pydantic) vs soft (system prompt only)."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
from _helpers import ensure_src_on_path

ensure_src_on_path()
from pydantic import ValidationError"""
        ),
    ),
    (
        "markdown",
        "extra-md",
        md(
            """\
## extra='forbid' — every contract rejects rogue fields

If you ever see a contract drop this constraint, the LLM gains a silent escape hatch. Cheap, blanket check."""
        ),
    ),
    (
        "code",
        "extra-fuzz",
        code(
            """\
import importlib
import inspect

from pydantic import BaseModel

modules = [
    "hsb.contracts.qa",
    "hsb.contracts.knowledge",
    "hsb.contracts.risk",
    "hsb.contracts.uat",
    "hsb.contracts.global_orchestrator",
    "hsb.contracts.main_orchestrator",
    "hsb.contracts.orchestrator",
    "hsb.contracts.backlog",
    "hsb.contracts.builder",
    "hsb.contracts.git",
    "hsb.contracts.linear",
]
missing = []
for mname in modules:
    m = importlib.import_module(mname)
    for name, obj in inspect.getmembers(m, inspect.isclass):
        if obj.__module__ != mname:
            continue
        if not issubclass(obj, BaseModel):
            continue
        cfg = getattr(obj, "model_config", {}) or {}
        if cfg.get("extra") != "forbid":
            missing.append(f"{mname}.{name}")
assert not missing, f"contracts missing extra='forbid': {missing}"
print("every contract model declares extra=forbid")"""
        ),
    ),
    (
        "markdown",
        "qa-md",
        md(
            """\
## QA — cycle cap (Pitfall 2)

Three branches: cap-reached + still-required (BLOCK), cap-reached + approved + missing annotation (BLOCK), canonical cap-reached path (PASS)."""
        ),
    ),
    (
        "code",
        "qa-cycle",
        code(
            """\
from hsb.contracts.qa import QAEvidence, QAFinding, QAOutput

ev = QAEvidence(file="a.py", component="c", location="10", related_requirement="AC-1")
f = QAFinding(
    title="t",
    severity="low",
    category="code_quality",
    status="non_blocking",
    problem="p",
    evidence=ev,
    expected_behavior="e",
    actual_behavior="a",
    suggested_fix="s",
)

# 5 findings = OK, 6 = blocked by max_length
QAOutput(
    work_item_id="LIN-1",
    qa_status="changes_required",
    qa_cycle_count=1,
    summary="s",
    findings=[f] * 5,
)
raised = False
try:
    QAOutput(
        work_item_id="LIN-1",
        qa_status="changes_required",
        qa_cycle_count=1,
        summary="s",
        findings=[f] * 6,
    )
except ValidationError:
    raised = True
assert raised, "findings cap (max 5) not enforced"
print("QAAG-03: max_length=5 on findings enforced")"""
        ),
    ),
    (
        "code",
        "qa-input",
        code(
            """\
from hsb.contracts.qa import PullRequestInput, QAInput

pr = PullRequestInput(url="https://github.com/x/y/pull/1", diff="--- a\\n+++ b\\n")
QAInput(work_item_id="LIN-1", linear_issue={}, pull_request=pr, qa_cycle_count=2)
raised = False
try:
    QAInput(work_item_id="LIN-1", linear_issue={}, pull_request=pr, qa_cycle_count=3)
except ValidationError:
    raised = True
assert raised, "QAInput accepted qa_cycle_count > 2 (input is 0-indexed, max 2)"
print("QAInput: input qa_cycle_count is 0-indexed [0..2]")"""
        ),
    ),
    (
        "markdown",
        "uat-md",
        md(
            """\
## UAT — evidence min_length (B2 dimension)

`UATScenario.evidence` has `min_length=10` so the LLM cannot pass off paraphrases of the criterion as evidence."""
        ),
    ),
    (
        "code",
        "uat-evidence",
        code(
            """\
from hsb.contracts.uat import UATResult, UATScenario

raised = False
try:
    UATScenario(
        criterion_id="AC-1", criterion_text="t", status="pass", evidence="short"
    )
except ValidationError:
    raised = True
assert raised, "UAT evidence accepted len < 10"
UATScenario(
    criterion_id="AC-1",
    criterion_text="t",
    status="pass",
    evidence="ten chars or more here yes",
)

# uat_cycle is 1-indexed (ge=1)
raised = False
try:
    UATResult(
        user_story_id="US-1", overall_status="approved", scenarios=[], uat_cycle=0
    )
except ValidationError:
    raised = True
assert raised, "UATResult accepted uat_cycle=0"
print("UAT: evidence min_length=10 + uat_cycle ge=1 both enforced")"""
        ),
    ),
    (
        "markdown",
        "linear-md",
        md(
            """\
## Linear — entity ID + URL regex; failed-result invariant

`LinearEntity.id` matches `^LIN-\\d+$`; URL must be `https://linear.app/...`. `LinearOutput.failed_must_have_error` model_validator forbids a failed result without an error message."""
        ),
    ),
    (
        "code",
        "linear-fuzz",
        code(
            """\
from hsb.contracts.linear import LinearEntity, LinearOutput

raised = False
try:
    LinearEntity(id="123", type="task", url="https://linear.app/x")
except ValidationError:
    raised = True
assert raised, "LinearEntity accepted id without LIN- prefix"

raised = False
try:
    LinearOutput(operation="create", result="failed", linear_entities=[], error=None)
except ValidationError:
    raised = True
assert raised, "failed result without error message accepted"

ok = LinearOutput(operation="create", result="failed", linear_entities=[], error="boom")
assert ok.error == "boom"
print("Linear: id regex, URL regex, failed-must-have-error all enforced")"""
        ),
    ),
    (
        "markdown",
        "knowledge-md",
        md(
            """\
## Knowledge Store — applicability validator (G9, INTL-03)

Same fuzz as notebook 00, with a twist: confirm trimming + case folding both apply (`'  ALL  '` should still be rejected)."""
        ),
    ),
    (
        "code",
        "knowledge-fuzz",
        code(
            """\
from hsb.contracts.knowledge import KnowledgeStorageInput

base = dict(
    title="t",
    type="qa",
    context="c",
    evidence={
        "linear_issue": "LIN-1",
        "pr": "#1",
        "files": ["x.py"],
        "qa_finding": "F1",
    },
    insight="i",
    recommendation="r",
    date="2026-05-09",
)
for bad in ["  ALL  ", "\\tn/a\\n", "TBD", "   "]:
    raised = False
    try:
        KnowledgeStorageInput(**base, applicability=bad)
    except Exception:
        raised = True
    assert raised, f"whitespace/case fold bypass: {bad!r}"
print("G9: trimming + case fold both apply")"""
        ),
    ),
    (
        "markdown",
        "risk-md",
        md(
            """\
## Risk — score range and Literal pin"""
        ),
    ),
    (
        "code",
        "risk-fuzz",
        code(
            """\
from hsb.contracts.risk import AutoImprovementTrigger, QualityScore

raised = False
try:
    QualityScore(work_item_id="LIN-1", score=101.0)
except ValidationError:
    raised = True
assert raised, "QualityScore accepted score > 100"

raised = False
try:
    QualityScore(work_item_id="LIN-1", score=-1.0)
except ValidationError:
    raised = True
assert raised, "QualityScore accepted negative score"

raised = False
try:
    AutoImprovementTrigger(
        title="t",
        description="d",
        pattern_evidence=["LIN-1", "LIN-2"],
        suggested_type="x",
        linear_state="created",
    )
except ValidationError:
    raised = True
assert raised, "AutoImprovementTrigger accepted linear_state=created"
print("Risk: score 0..100 + linear_state Literal[suggested] both pinned")"""
        ),
    ),
    (
        "markdown",
        "backlog-md",
        md(
            """\
## Backlog — empty epics list rejected; plan_source required"""
        ),
    ),
    (
        "code",
        "backlog-fuzz",
        code(
            """\
from hsb.contracts.backlog import (
    BacklogInput,
    BacklogOutput,
    BacklogTraceability,
    ProjectContext,
)

raised = False
try:
    BacklogOutput(epics=[], traceability=BacklogTraceability(plan_source="plan.md"))
except ValidationError:
    raised = True
assert raised, "BacklogOutput accepted empty epics list"

raised = False
try:
    BacklogInput(
        project_context=ProjectContext(name="x", repository="y")
    )  # missing plan_source
except ValidationError:
    raised = True
assert raised, "BacklogInput accepted missing plan_source (BKPK-01)"
print("Backlog: min_length=1 on epics + plan_source required (BKPK-01)")"""
        ),
    ),
    (
        "markdown",
        "builder-md",
        md(
            """\
## Builder — capability boundary at the schema level (BLDR-04)

If the agent emits `git_branch` / `pr_url` / `linear_status`, `extra='forbid'` rejects."""
        ),
    ),
    (
        "code",
        "builder-fuzz",
        code(
            """\
from hsb.contracts.builder import BuilderOutput

for forbidden in ["git_branch", "pr_url", "linear_status"]:
    payload = dict(
        work_item_id="LIN-1",
        implementation_status="completed",
        summary="s",
        files_changed=[],
        validation={
            "build": "not_run",
            "tests": "not_run",
            "lint": "not_run",
            "typecheck": "not_run",
        },
        implementation_notes={},
    )
    payload[forbidden] = "leaked"
    raised = False
    try:
        BuilderOutput.model_validate(payload)
    except ValidationError:
        raised = True
    assert raised, f"BuilderOutput accepted {forbidden} field"
print("BLDR-04: BuilderOutput rejects git_branch / pr_url / linear_status fields")"""
        ),
    ),
    (
        "markdown",
        "git-md",
        md(
            """\
## Git — capability boundary at the schema level (GITA-05)"""
        ),
    ),
    (
        "code",
        "git-fuzz",
        code(
            """\
from hsb.contracts.git import GitOutput, PullRequest

pr = PullRequest(
    url="https://github.com/x/y/pull/1",
    title="[LIN-1] add x",
    base="epic/LIN-99",
    head="feature/LIN-1-add-x",
)
for forbidden in ["merged_to_main", "linear_status", "file_changes"]:
    payload = dict(
        work_item_id="LIN-1",
        branch="feature/LIN-1-add-x",
        commits=[],
        pull_request=pr.model_dump(),
    )
    payload[forbidden] = "leaked"
    raised = False
    try:
        GitOutput.model_validate(payload)
    except ValidationError:
        raised = True
    assert raised, f"GitOutput accepted {forbidden} field"
print("GITA-05: GitOutput rejects merge / linear / code-change fields")"""
        ),
    ),
    (
        "markdown",
        "play-md",
        md(
            """\
## Free-form play

Use the cell below to instantiate any contract you're investigating. The cell intentionally has no assertions so you can observe the validator's error messages directly."""
        ),
    ),
    (
        "code",
        "play",
        code(
            """\
# Example: try editing one field at a time and re-running.
from hsb.contracts.qa import QAOutput

try:
    out = QAOutput(
        work_item_id="LIN-1",
        qa_status="approved",
        qa_cycle_count=1,
        summary="ok",
        findings=[],
    )
    print(out.model_dump())
except ValidationError as e:
    print(e.json(indent=2))"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 02 — Risk + Global Orchestrator pure logic (deterministic Python, no LLM)
# ---------------------------------------------------------------------------

NB_02: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 02 — Risk + Global Orchestrator pure-logic

Both `RiskAgent.calculate_quality_score / get_priority_queue` and `GlobalOrchestrator._filter_ready_items / _check_epic_complete / _uat_passes_g10` are deterministic Python — no LLM, no MCP. Feed synthetic Linear state, watch the outputs.

Why this exists: the pieces of the system you most need to **trust** under load are the deterministic ones. Easier to reason about when you can twist inputs and watch the queue change.

**Runtime-agnostic.** None of the cells below reach a runtime — they exercise pure functions on the agent classes. The same outputs hold whether the rest of the system is wired to Claude or Codex."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
from _helpers import ensure_src_on_path

ensure_src_on_path()
from hsb.agents.global_orchestrator import _uat_passes_g10
from hsb.agents.risk_agent import RiskAgent
from hsb.contracts.uat import UATResult, UATScenario

ra = RiskAgent()"""
        ),
    ),
    (
        "markdown",
        "score-md",
        md(
            """\
## Quality score formula (skill 12)

`score = max(0, 100 - 10·qa_failures - 5·fix_subtasks - (15 if uat_failed) - 5·rework)`

Concrete examples — the breakdown dict shows you which penalty contributed what."""
        ),
    ),
    (
        "code",
        "score-examples",
        code(
            """\
examples = [
    ("clean", {"id": "LIN-1", "fix_subtask_count": 0, "qa_cycle_count": 0}, [], []),
    (
        "one-qa-fail",
        {"id": "LIN-2", "fix_subtask_count": 1, "qa_cycle_count": 1},
        [{"status": "changes_required"}],
        [],
    ),
    (
        "uat-failed",
        {"id": "LIN-3", "fix_subtask_count": 2, "qa_cycle_count": 2},
        [{"status": "changes_required"}],
        [{"overall_status": "changes_required"}],
    ),
    (
        "floor",
        {"id": "LIN-4", "fix_subtask_count": 30, "qa_cycle_count": 10},
        [{"status": "changes_required"}] * 10,
        [{"overall_status": "changes_required"}],
    ),
]
for label, item, qa, uat in examples:
    qs = ra.calculate_quality_score(item, qa, uat)
    print(f"{label:>14}  score={qs.score:>5.1f}  breakdown={qs.score_breakdown}")

# Floor at 0 — no negative scores leak.
qs = ra.calculate_quality_score(
    {"id": "X", "fix_subtask_count": 100, "qa_cycle_count": 100},
    [{"status": "changes_required"}] * 100,
    [{"overall_status": "changes_required"}],
)
assert qs.score == 0.0, "score floor at 0 violated\""""
        ),
    ),
    (
        "markdown",
        "queue-md",
        md(
            """\
## Priority queue (skill 13 — RISK-02)

Sort: score **descending**, ties broken by `updatedAt` **ascending** (oldest first). The tiebreaker matters when two clean tasks both score 100 — the one updated longer ago wins."""
        ),
    ),
    (
        "code",
        "queue-tiebreak",
        code(
            """\
linear_state = {
    "LIN-A": {
        "id": "LIN-A",
        "fix_subtask_count": 0,
        "qa_cycle_count": 0,
        "qa_history": [],
        "uat_results": [],
        "updatedAt": "2026-04-01T10:00:00Z",
    },
    "LIN-B": {
        "id": "LIN-B",
        "fix_subtask_count": 0,
        "qa_cycle_count": 0,
        "qa_history": [],
        "uat_results": [],
        "updatedAt": "2026-04-02T10:00:00Z",
    },
    "LIN-C": {
        "id": "LIN-C",
        "fix_subtask_count": 2,
        "qa_cycle_count": 1,
        "qa_history": [{"status": "changes_required"}],
        "uat_results": [],
        "updatedAt": "2026-03-15T10:00:00Z",
    },
}
q = ra.get_priority_queue(["LIN-A", "LIN-B", "LIN-C"], linear_state)
print("items =", q.items, "\\nscores =", q.scores)
# A (100, older) before B (100, newer); C trails (lower score).
assert q.items[0] == "LIN-A"
assert q.items[1] == "LIN-B"
assert q.items[2] == "LIN-C\""""
        ),
    ),
    (
        "markdown",
        "epic-md",
        md(
            """\
## EPIC aggregation

Weighted average where weight = `max(1, qa_failures + fix_subtask_count)`. An EPIC of clean tasks averages 100 because each gets weight 1. An EPIC with one disastrous task pulls hard."""
        ),
    ),
    (
        "code",
        "epic-agg",
        code(
            """\
scores = []
for spec in [
    {"id": "A", "fix_subtask_count": 0, "qa_cycle_count": 0},
    {"id": "B", "fix_subtask_count": 0, "qa_cycle_count": 0},
    {"id": "C", "fix_subtask_count": 10, "qa_cycle_count": 5},
]:
    scores.append(
        ra.calculate_quality_score(
            spec,
            [{"status": "changes_required"}] * spec["qa_cycle_count"],
            [],
        )
    )
epic = ra.calculate_epic_score(scores)
print("EPIC weighted score =", epic)
# Empty list returns 85.0 default — the deliberate 'unknown' value.
assert ra.calculate_epic_score([]) == 85.0"""
        ),
    ),
    (
        "markdown",
        "risk-band-md",
        md(
            """\
## Risk bands

>=75 = low, >=50 = medium, else high. Inspect the inflection points."""
        ),
    ),
    (
        "code",
        "risk-band",
        code(
            """\
for s in [100, 75.0, 74.999, 50.0, 49.999, 0]:
    print(f"{s:>8}  ->  {RiskAgent.risk_level(s)}")"""
        ),
    ),
    (
        "markdown",
        "go-md",
        md(
            """\
## Global Orchestrator — ready-task filter (GORD-01/02)

Inputs: a list of plain dicts; the orchestrator keeps only `status='todo'` items whose `dependencies` are all in the `done` set. We exercise the public class method `_filter_ready_items` directly — it's stateless."""
        ),
    ),
    (
        "code",
        "go-filter",
        code(
            """\
from hsb.agents.global_orchestrator import GlobalOrchestrator

go = GlobalOrchestrator()
items = [
    {"id": "LIN-1", "status": "done", "dependencies": []},
    {"id": "LIN-2", "status": "todo", "dependencies": []},
    {"id": "LIN-3", "status": "todo", "dependencies": ["LIN-1"]},  # unblocked
    {"id": "LIN-4", "status": "todo", "dependencies": ["LIN-2"]},  # blocked
    {"id": "LIN-5", "status": "in_progress", "dependencies": []},  # not todo
]
ready = go._filter_ready_items(items)
ready_ids = sorted(t["id"] for t in ready)
print("ready =", ready_ids)
assert ready_ids == ["LIN-2", "LIN-3"]"""
        ),
    ),
    (
        "markdown",
        "epic-ready-md",
        md(
            """\
## EPIC completion signal (GORD-04)"""
        ),
    ),
    (
        "code",
        "epic-ready",
        code(
            """\
# Empty children -> never ready.
assert go._check_epic_complete([{"id": "E", "type": "epic", "status": "todo"}]) is False
# All children done + qa_approved -> ready.
items = [
    {"id": "E", "type": "epic", "status": "in_progress"},
    {"id": "T1", "type": "task", "status": "done", "qa_status": "approved"},
    {"id": "T2", "type": "task", "status": "done", "qa_status": "not_required"},
]
assert go._check_epic_complete(items) is True
# One child still in progress -> not ready.
items[1]["status"] = "in_progress"
assert go._check_epic_complete(items) is False
print("GORD-04: epic readiness signal behaves correctly across cases")"""
        ),
    ),
    (
        "markdown",
        "g10-md",
        md(
            """\
## G10 — UAT pre-persist validation

Before any Linear write, the orchestrator runs `_uat_passes_g10`:
- **B1 coverage**: scenarios cover every AC (`AC-1..AC-N`).
- **B3 banned tokens**: scope-creep words like `refactor`, `code quality`, `naming`, `style`, `linter`, etc. fail the predicate."""
        ),
    ),
    (
        "code",
        "g10-cases",
        code(
            """\
ac = ["User can log in", "Errors show inline"]
ok = UATResult(
    user_story_id="US-1",
    overall_status="approved",
    uat_cycle=1,
    scenarios=[
        UATScenario(
            criterion_id="AC-1",
            criterion_text=ac[0],
            status="pass",
            evidence="Logged in with valid creds and saw dashboard",
        ),
        UATScenario(
            criterion_id="AC-2",
            criterion_text=ac[1],
            status="pass",
            evidence="Submitted invalid form, error rendered inline",
        ),
    ],
)
assert _uat_passes_g10(ok, ac) is True

# Coverage gap (only AC-1)
gap = ok.model_copy(update={"scenarios": ok.scenarios[:1]})
assert _uat_passes_g10(gap, ac) is False

# Banned token in finding
creep = ok.model_copy(
    update={
        "scenarios": [
            ok.scenarios[0],
            UATScenario(
                criterion_id="AC-2",
                criterion_text=ac[1],
                status="fail",
                evidence="Form looked off",
                finding="Should refactor naming convention here",
            ),
        ]
    }
)
assert _uat_passes_g10(creep, ac) is False
print("G10: coverage gap and scope-creep both rejected")"""
        ),
    ),
    (
        "markdown",
        "play-md",
        md(
            """\
## Free-form play

Build a synthetic Linear snapshot, run the queue, see what the orchestrator would dispatch."""
        ),
    ),
    (
        "code",
        "play",
        code(
            """\
snapshot = {
    "LIN-100": {
        "id": "LIN-100",
        "status": "todo",
        "dependencies": [],
        "fix_subtask_count": 0,
        "qa_cycle_count": 0,
        "qa_history": [],
        "uat_results": [],
        "updatedAt": "2026-05-01T00:00:00Z",
    },
    "LIN-101": {
        "id": "LIN-101",
        "status": "todo",
        "dependencies": [],
        "fix_subtask_count": 1,
        "qa_cycle_count": 2,
        "qa_history": [{"status": "changes_required"}] * 2,
        "uat_results": [],
        "updatedAt": "2026-04-01T00:00:00Z",
    },
}
ready = go._filter_ready_items(list(snapshot.values()))
q = ra.get_priority_queue([t["id"] for t in ready], snapshot)
print("order:", q.items, "\\nscores:", q.scores)"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 03 — Main Orchestrator dispatch (pure-Python controller, no LLM)
# ---------------------------------------------------------------------------

NB_03: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 03 — Main Orchestrator dispatch

Pure-Python dispatch controller. Things you can poke without spawning a real WIO:

- The cycle summary formatter (MORD-05).
- The worktree lifecycle (`_git_worktree_add` / `_git_worktree_remove`).
- The strict env allowlist (T-4-04) — confirmed by source inspection.
- The claim-delay knob (`HSB_CLAIM_DELAY_MS`).

**Runtime note.** WIO is hard-blocked from Codex (its stateful `ClaudeSDKClient` session has no Codex equivalent — see `resolve_runtime("wio")` in notebook 00). Everything in this notebook stays Claude-side. The subprocess env allowlist in `_run_wio_subprocess` was authored before the `ANTHROPIC_API_KEY -> CLAUDE_CODE_OAUTH_TOKEN` rename and still ships the legacy literal — the assertion below pins the literal that's in the source today, NOT what production uses for auth.

**Side effect:** the worktree section creates a throwaway git repo under `$HSB_NOTEBOOK_SCRATCH_DIR` (defaults to a tmp dir) and removes it on completion. Nothing touches the real repo."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from _helpers import ensure_src_on_path, selected_runtime

ensure_src_on_path()
from hsb.agents import main_orchestrator as mo

# Visible cue: WIO is locked to Claude. Notebook 00 already asserts the
# hard-block; we just print the selection here for context.
print("HSB_RUNTIME_WIO ->", selected_runtime("wio"), "(WIO is hard-locked to claude)")"""
        ),
    ),
    (
        "markdown",
        "summary-md",
        md(
            """\
## Cycle summary formatter (MORD-05)

Plain string-builder over `DispatchedItem`s. We feed a mix and confirm headers + counts."""
        ),
    ),
    (
        "code",
        "summary-build",
        code(
            """\
from hsb.contracts.main_orchestrator import DispatchedItem

items = [
    DispatchedItem(
        work_item_id="LIN-1",
        orchestrator_instance="cascade-0",
        claim_status="claimed",
        final_status="completed",
    ),
    DispatchedItem(
        work_item_id="LIN-2",
        orchestrator_instance="parallel-0",
        claim_status="claimed",
        final_status="failed",
    ),
    DispatchedItem(
        work_item_id="LIN-3",
        orchestrator_instance="skipped",
        claim_status="skipped",
        final_status="blocked",
    ),
]
summary = mo._build_cycle_summary("parallel", items)
print(summary)
assert "**Mode:** parallel" in summary
assert "**Dispatched:** 3 tasks" in summary
assert "**Completed:** 1" in summary
assert "**Failed/Blocked:** 2" in summary
assert "**Skipped (claim failed):** 1" in summary"""
        ),
    ),
    (
        "markdown",
        "env-md",
        md(
            """\
## T-4-04 — strict env allowlist for WIO subprocess

Source inspection: confirm `_run_wio_subprocess` does NOT pass `**os.environ` and that the env dict is the documented 5-key allowlist. We can't easily run the real subprocess from a notebook, but we can prove the structural defence exists."""
        ),
    ),
    (
        "code",
        "env-grep",
        code(
            """\
src = Path(mo.__file__).read_text()
# Anti-pattern check: any '**os.environ' anywhere is a red flag.
assert "**os.environ" not in src, "T-4-04: os.environ wholesale spread detected"
# Positive check: the documented allowlist keys appear.
# Note: the auth-key entry currently still reads ANTHROPIC_API_KEY (predates the
# CLAUDE_CODE_OAUTH_TOKEN rename in commit ddcd0ea). We assert the literal in
# the source — when src/hsb/agents/main_orchestrator.py is updated, flip this
# assertion to "CLAUDE_CODE_OAUTH_TOKEN".
for key in [
    "PATH",
    "HOME",
    "ANTHROPIC_API_KEY",
    "HSB_WIO_INPUT_FILE",
    "HSB_WIO_OUTPUT_FILE",
]:
    assert f'"{key}"' in src, f"T-4-04: missing allowlist key {key}"
print("T-4-04: subprocess env is the strict 5-key allowlist (no os.environ wholesale)")"""
        ),
    ),
    (
        "markdown",
        "wt-md",
        md(
            """\
## Worktree add / remove (MORD-04 + D-09)

Create a throwaway git repo, run `_git_worktree_add` on it, confirm the path exists, then run `_git_worktree_remove` and confirm it's gone. Cleanup runs in `finally` so a failure doesn't leave junk on disk."""
        ),
    ),
    (
        "code",
        "wt-roundtrip",
        code(
            """\
scratch = Path(
    os.environ.get("HSB_NOTEBOOK_SCRATCH_DIR") or tempfile.mkdtemp(prefix="hsb-nb-")
)
repo = scratch / "repo"
repo.mkdir(parents=True, exist_ok=True)
try:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "nb@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "nb"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)

    # Top-level await works in IPython kernels (Jupyter Lab + nbconvert).
    # Don't use asyncio.run() — IPython already runs the cell inside an
    # active event loop and asyncio.run() refuses to nest.
    wt = await mo._git_worktree_add(  # noqa: F704
        str(repo), task_id="42", branch_name="feature/LIN-42-x"
    )
    assert Path(wt).exists()
    print("worktree at", wt)

    listed = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "LIN-42" in listed, listed

    await mo._git_worktree_remove(str(repo), task_id="42")  # noqa: F704
    listed = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "LIN-42" not in listed, listed
    print("worktree removed cleanly")
finally:
    shutil.rmtree(scratch, ignore_errors=True)"""
        ),
    ),
    (
        "markdown",
        "delay-md",
        md(
            """\
## Inter-claim delay (D-06)

`HSB_CLAIM_DELAY_MS` is read once at import; default 200ms. Confirm the constant is exposed and overridable."""
        ),
    ),
    (
        "code",
        "delay-knob",
        code(
            """\
import importlib

os.environ.pop("HSB_CLAIM_DELAY_MS", None)
importlib.reload(mo)
assert mo.CLAIM_DELAY_MS == 200, mo.CLAIM_DELAY_MS

os.environ["HSB_CLAIM_DELAY_MS"] = "500"
importlib.reload(mo)
assert mo.CLAIM_DELAY_MS == 500
del os.environ["HSB_CLAIM_DELAY_MS"]
importlib.reload(mo)
print("CLAIM_DELAY_MS knob: env-overridable, defaults to 200ms")"""
        ),
    ),
    (
        "markdown",
        "stale-md",
        md(
            """\
## Pitfall C — stale-worktree prune at parallel-mode startup

Source inspection: `_parallel_dispatch` runs `git worktree prune` before adding any new ones. Cheap but important — without this, a crashed prior run leaves orphan refs that block a new add."""
        ),
    ),
    (
        "code",
        "stale-grep",
        code(
            """\
src = Path(mo.__file__).read_text()
assert "git worktree prune" in src or '"prune"' in src, (
    "parallel dispatch lacks worktree prune"
)
print("Pitfall C: parallel dispatch prunes stale worktrees at startup")"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 04 — Linear + Knowledge Store (read-only) + runtime probes
# ---------------------------------------------------------------------------

NB_04: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 04 — Linear + Knowledge Store (read-only) + runtime probes

Three surfaces:

1. **Runtime selection probe** — render `HSB_RUNTIME_*` and the Codex-availability check (no LLM, no MCP).
2. **Linear MCP — read-only.** Confirms wiring + hooks behaviour. Gated on `HSB_NOTEBOOK_RUN_LIVE=1`. Token-cheap because everything we issue is a `read` operation; no writes mean the G5 `linear_write_guard` doesn't matter here.
3. **Knowledge Store — pure filesystem retrieval.** Glob + Grep over `knowledge/` mirrors what the Intelligence Agent does inline in the WIO (skill 10). No LLM, no MCP, no runtime.

The Linear cell drives `run_validated_linear_agent`, which goes through whichever runtime `HSB_RUNTIME_LINEAR` selects. With `HSB_RUNTIME_LINEAR=codex` you must also have a valid `~/.codex/config.toml` with the Linear MCP server registered — `codex_available()` and `verify_codex_mcp()` flag a misconfig before the call burns tokens.

If Linear cells skip on first run that's fine — the Knowledge Store cells run regardless and are the higher-value half."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
import os

from _helpers import (
    assert_g1_safe,
    codex_available,
    ensure_src_on_path,
    gated,
    live_mode,
    runtime_summary,
    selected_runtime,
)

ROOT = ensure_src_on_path()
print("HSB_RUNTIME_* selection:\\n" + runtime_summary())
ok, reason = codex_available()
print(f"\\ncodex_available -> ok={ok}  reason={reason}")"""
        ),
    ),
    (
        "markdown",
        "ks-md",
        md(
            """\
## Knowledge Store — inventory

Categories (per `README.md#repository-layout`): `architecture`, `qa`, `implementation`, `backlog`, `risk`, `patterns`, `anti-patterns`."""
        ),
    ),
    (
        "code",
        "ks-inventory",
        code(
            """\
ks = ROOT / "knowledge"
if not ks.exists():
    print("(knowledge/ not present at repo root — nothing to enumerate)")
else:
    for cat in sorted(p.name for p in ks.iterdir() if p.is_dir()):
        entries = list((ks / cat).glob("*.md"))
        print(f"{cat:>15}  {len(entries):>3} entries")"""
        ),
    ),
    (
        "markdown",
        "ks-glob-md",
        md(
            """\
## Knowledge Store — Glob + Grep retrieval (skill 10 surface)

Equivalent to what `build_enrichment_prompt` instructs the LLM to run: list candidate files, then grep them for keywords matching the work item's domain / technology / pattern.

Usage: edit `keywords` to whatever your task is about, run, see what entries the Intelligence Agent would surface."""
        ),
    ),
    (
        "code",
        "ks-grep",
        code(
            """\
import re

if not ks.exists():
    print("(knowledge/ not present — skipping grep)")
else:
    keywords = ["postgres", "pydantic", "retry", "optimistic"]
    pat = re.compile("|".join(re.escape(k) for k in keywords), re.I)
    hits = []
    for p in ks.rglob("*.md"):
        text = p.read_text(errors="ignore")
        matches = pat.findall(text)
        if matches:
            hits.append((p.relative_to(ROOT), len(matches)))
    for path, n in sorted(hits, key=lambda x: -x[1]):
        print(f"{n:>4}  {path}")
    if not hits:
        print(
            "(no entries match — knowledge/ may be empty on main; populated by skill 11 over time)"
        )"""
        ),
    ),
    (
        "markdown",
        "ks-fixture-md",
        md(
            """\
## Knowledge Store — write a transient fixture entry

Drops one entry into `knowledge/qa/` under a tmp filename so you can re-run the grep cell and see it ranked, then deletes it. Mirrors what `KnowledgeStorageInput` would write."""
        ),
    ),
    (
        "code",
        "ks-fixture",
        code(
            """\
import datetime

from hsb.contracts.knowledge import KnowledgeStorageInput

if not ks.exists():
    print("(knowledge/ not present — skipping fixture)")
else:
    entry = KnowledgeStorageInput(
        title="Postgres optimistic-lock retry pattern",
        type="qa",
        context="Linear writes were silently overwritten by concurrent claims",
        evidence={
            "linear_issue": "LIN-99",
            "pr": "#42",
            "files": ["linear_agent.py"],
            "qa_finding": "F-7",
        },
        insight="updatedAt re-read is the only way to detect a stale write",
        recommendation="read -> write -> re-read; verify post > pre, not equality",
        applicability="Any Linear write path during parallel claiming",
        date=datetime.date.today().isoformat(),
    )
    qa_dir = ks / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    tmp = qa_dir / f"_nb-fixture-{os.getpid()}.md"
    tmp.write_text(
        f"---\\ntitle: {entry.title}\\ntype: {entry.type}\\napplicability: {entry.applicability}\\ndate: {entry.date}\\n---\\n\\n"
        f"## Insight\\n{entry.insight}\\n\\n## Recommendation\\n{entry.recommendation}\\n"
    )
    try:
        print("wrote fixture:", tmp.relative_to(ROOT))
        pat2 = re.compile("postgres|optimistic", re.I)
        matches = [
            p for p in ks.rglob("*.md") if pat2.search(p.read_text(errors="ignore"))
        ]
        assert tmp in matches, "fixture not picked up by grep"
        print(f"grep retrieves {len(matches)} entries including the fixture")
    finally:
        tmp.unlink(missing_ok=True)
        print("fixture removed")"""
        ),
    ),
    (
        "markdown",
        "linear-md",
        md(
            """\
## Linear Agent — read probes (gated)

Two reads: `list_teams` and a single-issue `get_issue` (only if `HSB_NOTEBOOK_LINEAR_ISSUE_ID` is set). Both go through `run_validated_linear_agent` so the validation/retry loop is exercised. `HSB_RUNTIME_LINEAR` selects which runtime executes the call.

Gates:
- `HSB_NOTEBOOK_RUN_LIVE=1` — opt in to actual SDK calls.
- For `HSB_RUNTIME_LINEAR=claude`: `CLAUDE_CODE_OAUTH_TOKEN` must be set.
- For `HSB_RUNTIME_LINEAR=codex`: `~/.codex/config.toml` with `forced_login_method = "chatgpt"` and a `[mcp_servers.linear]` block, plus `~/.codex/auth.json` (run `codex login --device-auth`).

First-run warning (Claude side): `mcp-remote` to `mcp.linear.app/mcp` triggers an interactive OAuth flow. Run the smoke test in `linear_agent.py` once from the CLI before relying on the notebook."""
        ),
    ),
    (
        "code",
        "linear-list-teams",
        code(
            """\
if not live_mode():
    print(gated("Linear list_teams"))
else:
    assert_g1_safe()
    rt = selected_runtime("linear")
    print(f"(running on HSB_RUNTIME_LINEAR={rt!r})")
    if rt == "codex":
        ok, reason = codex_available()
        if not ok:
            print(f"[skipped] codex selected but unavailable: {reason}")
        else:
            print("(codex config OK; proceeding)")
    import asyncio

    from hsb.agents.linear_agent import run_validated_linear_agent

    out = asyncio.run(
        run_validated_linear_agent(
            operation="read",
            payload={"kind": "teams"},
        )
    )
    print("result =", out.result, "| entities =", len(out.linear_entities))"""
        ),
    ),
    (
        "code",
        "linear-get-issue",
        code(
            """\
issue_id = os.environ.get("HSB_NOTEBOOK_LINEAR_ISSUE_ID")
if not live_mode() or not issue_id:
    print(gated("Linear get_issue (set HSB_NOTEBOOK_LINEAR_ISSUE_ID=LIN-...)"))
else:
    assert_g1_safe()
    import asyncio

    from hsb.agents.linear_agent import run_validated_linear_agent

    out = asyncio.run(
        run_validated_linear_agent(
            operation="read",
            payload={"issueId": issue_id},
        )
    )
    print("result =", out.result, "| entities =", [e.id for e in out.linear_entities])"""
        ),
    ),
    (
        "markdown",
        "hooks-md",
        md(
            """\
## Linear hooks — module-level inspection

The hooks run inside the SDK loop, but the per-tool retry counter and audit log path are public module state we can sanity-check. Hooks are Claude-only (the HookMatcher API has no Codex equivalent — see `CodexRuntime.query` which raises if `options.hooks is not None`)."""
        ),
    ),
    (
        "code",
        "hooks-inspect",
        code(
            """\
from hsb.agents import hooks

print("MAX_RETRIES =", hooks.MAX_RETRIES)
print("BASE_DELAY_SECONDS =", hooks.BASE_DELAY_SECONDS)
print("AUDIT_LOG_PATH =", hooks.AUDIT_LOG_PATH)
print(
    "LINEAR_HOOKS keys =",
    list(hooks.LINEAR_HOOKS.keys()) if hasattr(hooks, "LINEAR_HOOKS") else "n/a",
)"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 05 — Per-agent smoke (Backlog / Builder / Git / QA / UAT) + runtime gates
# ---------------------------------------------------------------------------

NB_05: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 05 — Per-agent smoke (Backlog / Builder / Git / QA / UAT)

Each section has two parts:

1. **Capability boundary inspection** — read the agent's `allowed_tools` and prove it matches the spec (always runs, no LLM cost).
2. **Live smoke run** — gated on `HSB_NOTEBOOK_RUN_LIVE=1` + the relevant scratch fixtures.

Live runs cost tokens and require credentials. Default state: inspection only.

**Runtime selection.** The first cell prints `HSB_RUNTIME_*` for every agent. Live runs route through whichever runtime the env var picks. For each agent, we inspect the source for the `resolve_runtime("<agent>")` call site — this is the structural marker that the agent is actually flippable (vs. a hard-coded `claude_agent_sdk.query`).

Existing fixtures in `src/fixture/` (`branch_test.py`, `pr_base_test.py`, `pr_title_test.py`) are minimal Builder targets you can reuse."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
import asyncio
import os
import re

from _helpers import (
    assert_g1_safe,
    codex_available,
    ensure_src_on_path,
    gated,
    live_mode,
    runtime_summary,
    selected_runtime,
)

ROOT = ensure_src_on_path()
print("HSB_RUNTIME_* selection:\\n" + runtime_summary())"""
        ),
    ),
    (
        "markdown",
        "backlog-md",
        md(
            """\
## Backlog Agent

**Allow-list spec:** `mcp__linear__create_issue`, `mcp__linear__list_issues`, `mcp__linear__get_issue`, `Read` only — must NOT include `update`, `delete`, `Bash`, `Edit`, `Write`.

**Idempotency:** the system prompt's IDEMPOTENCY RULE forces a `list_issues` pre-flight. We can't unit-test the LLM's compliance, but we can confirm the rule literal appears in the prompt.

**Runtime flip:** Backlog is the canary that's fully runtime-agnostic — it goes through `make_agent_options()` + `resolve_runtime("backlog")` so `HSB_RUNTIME_BACKLOG=codex` works end-to-end (assuming `~/.codex/config.toml` is set up). We grep for the `resolve_runtime("backlog")` call site below."""
        ),
    ),
    (
        "code",
        "backlog-inspect",
        code(
            """\
src = (ROOT / "src/hsb/agents/backlog_agent.py").read_text()
must_have = [
    "mcp__linear__create_issue",
    "mcp__linear__list_issues",
    "mcp__linear__get_issue",
]
must_not = ["mcp__linear__update_issue", "mcp__linear__delete", '"Edit"', '"Write"']
for tok in must_have:
    assert tok in src, f"Backlog allow-list missing {tok}"
for tok in must_not:
    if tok in src:
        for m in re.finditer(r"allowed_tools\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL):
            assert tok not in m.group(1), f"Backlog allow-list contains forbidden {tok}"
assert "IDEMPOTENCY RULE" in src, "Backlog system prompt missing IDEMPOTENCY RULE"
# Runtime-flip marker: backlog must call resolve_runtime("backlog") before query.
assert 'resolve_runtime("backlog")' in src, (
    "Backlog Agent missing runtime-flip plumbing — should call resolve_runtime('backlog')"
)
# And it must use the runtime-agnostic factory, not raw ClaudeAgentOptions.
assert "make_agent_options(" in src, (
    "Backlog Agent should construct AgentOptions via make_agent_options()"
)
print(
    "Backlog: allow-list matches spec, IDEMPOTENCY RULE present, "
    f"runtime-flip wired (currently HSB_RUNTIME_BACKLOG={selected_runtime('backlog')!r})"
)"""
        ),
    ),
    (
        "code",
        "backlog-live",
        code(
            """\
if not live_mode() or not os.environ.get("HSB_NOTEBOOK_PLAN_MD"):
    print(gated("Backlog live run (set HSB_NOTEBOOK_PLAN_MD=/path/to/plan.md)"))
else:
    assert_g1_safe()
    rt = selected_runtime("backlog")
    print(f"(running on HSB_RUNTIME_BACKLOG={rt!r})")
    if rt == "codex":
        ok, reason = codex_available()
        assert ok, f"codex selected but unavailable: {reason}"
    from hsb.agents.backlog_agent import run_backlog_agent
    from hsb.contracts.backlog import BacklogInput, ProjectContext

    inp = BacklogInput(
        plan_source=os.environ["HSB_NOTEBOOK_PLAN_MD"],
        project_context=ProjectContext(
            name="hsb-nb", repository="nb", technical_stack=["python"]
        ),
    )
    out = run_backlog_agent(inp)
    print(f"EPICs: {len(out.epics)} | first EPIC: {out.epics[0].title!r}")
    # IDEMPOTENCY: rerun should NOT create new EPICs (BKPK-05).
    out2 = run_backlog_agent(inp)
    same = len(out2.epics) == len(out.epics)
    print("rerun returned", "same" if same else "different", "EPIC count")"""
        ),
    ),
    (
        "markdown",
        "builder-md",
        md(
            """\
## Builder Agent

**Capability boundary (BLDR-04):** `Read`, `Edit`, `Write` + `Bash` for `pytest|ruff|mypy|python` only. **No** Linear MCP, **no** git, **no** `gh`.

Schema-level guard: `BuilderOutput` rejects `git_branch` / `pr_url` / `linear_status` (covered in notebook 01)."""
        ),
    ),
    (
        "code",
        "builder-inspect",
        code(
            """\
src = (ROOT / "src/hsb/agents/builder_agent.py").read_text()
m = re.search(r"allowed_tools\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL)
assert m, "Builder allowed_tools literal not found"
block = m.group(1)
for ok in ['"Read"', '"Edit"', '"Write"', "pytest", "ruff", "mypy"]:
    assert ok in block, f"Builder allow-list missing {ok}"
for forbidden in ["mcp__linear__", '"Agent"', '"git "', "gh pr "]:
    assert forbidden not in block, f"Builder allow-list contains forbidden {forbidden}"
assert "mcp_servers=" not in src or "mcp_servers=None" in src, (
    "Builder ships an MCP server"
)
print(
    "Builder: allow-list matches BLDR-04 (no Linear, no git, no Agent); "
    f"HSB_RUNTIME_BUILDER={selected_runtime('builder')!r}"
)"""
        ),
    ),
    (
        "code",
        "builder-live",
        code(
            """\
scratch = os.environ.get("HSB_NOTEBOOK_SCRATCH_DIR")
if not live_mode() or not scratch:
    print(gated("Builder live run (set HSB_NOTEBOOK_SCRATCH_DIR=/tmp/some-repo)"))
else:
    assert_g1_safe()
    from hsb.agents.builder_agent import run_builder_agent
    from hsb.contracts.builder import BuilderInput, RepositoryContext

    inp = BuilderInput(
        work_item_id="LIN-NB-1",
        issue_description="Add a one-line print to scratch.py",
        acceptance_criteria=['File scratch.py prints "hello"'],
        plan_source="plan.md",
        repository_context=RepositoryContext(
            root_path=scratch, technical_stack=["python"]
        ),
    )
    out = run_builder_agent(inp)
    print("status =", out.implementation_status)
    print("files =", [f.path for f in out.files_changed])"""
        ),
    ),
    (
        "markdown",
        "git-md",
        md(
            """\
## Git Agent

**Allow-list:** `gh pr create/list/view/diff` (NOT `gh pr merge`), `git checkout/push/rebase/log/fetch/add/commit/status` (NOT `git merge`). All `gh pr list` calls must include `--limit 100` (Pitfall 4) and `git push` is `--force-with-lease` only (Pitfall 3)."""
        ),
    ),
    (
        "code",
        "git-inspect",
        code(
            """\
src = (ROOT / "src/hsb/agents/git_agent.py").read_text()
m = re.search(r"allowed_tools\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL)
assert m, "Git allowed_tools literal not found"
block = m.group(1)
for forbidden in ["gh pr merge", "git merge", '"Edit"', '"Write"', "mcp__linear__"]:
    assert forbidden not in block, f"Git allow-list contains forbidden {forbidden}"
assert "--force-with-lease" in block, "Git allow-list missing --force-with-lease"
assert "--limit 100" in src, "Git system prompt missing --limit 100 (Pitfall 4)"
print(
    "Git: no merge tools, --force-with-lease only, --limit 100 in prompt; "
    f"HSB_RUNTIME_GIT={selected_runtime('git')!r}"
)"""
        ),
    ),
    (
        "markdown",
        "qa-md",
        md(
            """\
## QA Agent

**Allow-list:** `Read`, `Bash(gh pr diff *)`, `Bash(gh pr view *)` only. **No** Edit/Write, **no** `gh pr create`, **no** Linear MCP. Cycle cap is enforced by the Pydantic `model_validator` on `QAOutput` (the deterministic last line of defence — see notebook 01)."""
        ),
    ),
    (
        "code",
        "qa-inspect",
        code(
            """\
src = (ROOT / "src/hsb/agents/qa_agent.py").read_text()
m = re.search(r"allowed_tools\\s*=\\s*\\[(.*?)\\]", src, re.DOTALL)
block = m.group(1)
must_have = ['"Read"', "gh pr diff", "gh pr view"]
must_not = ["gh pr create", "gh pr merge", '"Edit"', '"Write"', "mcp__linear__"]
for tok in must_have:
    assert tok in block, f"QA allow-list missing {tok}"
for tok in must_not:
    assert tok not in block, f"QA allow-list contains forbidden {tok}"
assert "CYCLE CAP" in src.upper(), "QA prompt missing cycle-cap instruction"
print(
    "QA: 3-tool allow-list intact, CYCLE CAP instruction present; "
    f"HSB_RUNTIME_QA={selected_runtime('qa')!r}"
)"""
        ),
    ),
    (
        "markdown",
        "uat-md",
        md(
            """\
## UAT Agent

**Allow-list:** `Read`, `Glob`, `Grep`, `Bash`. **No** Edit/Write/Agent. **`mcp_servers=None`** — UAT cannot write to Linear; the WIO/Global Orchestrator persist findings.

**Scope boundary:** every prompt prepends `SCOPE BOUNDARY:` and lists `[AC-N]` literals."""
        ),
    ),
    (
        "code",
        "uat-inspect",
        code(
            """\
src = (ROOT / "src/hsb/agents/uat_agent.py").read_text()
assert 'allowed_tools=["Read", "Glob", "Grep", "Bash"]' in src, (
    "UAT allow-list literal not found"
)
assert "mcp_servers=None" in src, "UAT must set mcp_servers=None"
assert "SCOPE BOUNDARY" in src, "UAT prompt missing SCOPE BOUNDARY"
# AI-SPEC §6 air-gap: no IMPORT of linear_agent. Comments/docstrings that
# mention the rule are fine — only actual import statements are forbidden.
import_lines = [
    line
    for line in src.splitlines()
    if re.match(r"^\\s*(from|import)\\s+", line) and "linear_agent" in line
]
assert not import_lines, f"UAT module must not import linear_agent: {import_lines}"
print(
    "UAT: 4-tool allow-list, mcp_servers=None, SCOPE BOUNDARY present, no linear_agent import; "
    f"HSB_RUNTIME_UAT={selected_runtime('uat')!r}"
)"""
        ),
    ),
    (
        "code",
        "uat-live",
        code(
            """\
if not live_mode():
    print(gated("UAT live run"))
else:
    assert_g1_safe()
    from hsb.agents.uat_agent import run_uat_and_validate

    out = asyncio.run(
        run_uat_and_validate(
            user_story_id="US-NB-1",
            acceptance_criteria=["The README.md file exists at repo root"],
            uat_cycle=1,
        )
    )
    print("status =", out.overall_status, "| scenarios:", len(out.scenarios))"""
        ),
    ),
]


# ---------------------------------------------------------------------------
# 06 — WIO full loop (gated, expensive) — Claude-only by hard-block
# ---------------------------------------------------------------------------

NB_06: Spec = [
    (
        "markdown",
        "intro",
        md(
            """\
# 06 — Work Item Orchestrator full loop (gated, expensive)

One end-to-end WIO cycle. The orchestrator is a single `ClaudeSDKClient` session that does:

1. **Step 1 (Phase 5, skill 10)** — Knowledge Store enrichment.
2. **Steps 2–4 (Phase 3)** — Builder -> Git -> QA cycle (cycle cap = 3 enforced by Pydantic + a Layer-2 escalation in this module).
3. **Step 5 (Phase 5, skill 11)** — Knowledge Store ingestion evaluation.

**Runtime: Claude-only.** WIO uses `claude_agent_sdk.ClaudeSDKClient` directly (not the runtime-agnostic seam) because the multi-turn stateful session has no Codex equivalent yet. `resolve_runtime("wio")` raises if `HSB_RUNTIME_WIO=codex` — we re-assert that hard-block below as a defence in depth.

**This notebook can spend real money and write to real Linear / GitHub.** Default state = explore only. Three gates must all be satisfied for the loop to run:

- `HSB_NOTEBOOK_RUN_LIVE=1`
- `HSB_NOTEBOOK_WIO_TASK_ID` set to a sandbox Linear LIN-ID
- `CLAUDE_CODE_OAUTH_TOKEN` set; `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` UNSET

Inspection-only cells (system-prompt assembly, allow-list, G3 wiring, codex hard-block) run regardless and are the high-value half if you don't have credentials handy."""
        ),
    ),
    (
        "code",
        "setup",
        code(
            """\
import asyncio
import os
from pathlib import Path

from _helpers import (
    assert_g1_safe,
    ensure_src_on_path,
    gated,
    live_mode,
    selected_runtime,
)

ROOT = ensure_src_on_path()
from hsb.agents import work_item_orchestrator as wio

print("HSB_RUNTIME_WIO ->", selected_runtime("wio"), "(WIO is hard-blocked from codex)")"""
        ),
    ),
    (
        "markdown",
        "hardblock-md",
        md(
            """\
## WIO Codex hard-block

`resolve_runtime("wio")` must raise when `HSB_RUNTIME_WIO=codex`. Until WIO is ported off `ClaudeSDKClient`'s stateful session, this is the structural defence that keeps an operator from accidentally pointing it at Codex via env."""
        ),
    ),
    (
        "code",
        "hardblock-check",
        code(
            """\
from hsb.agents._sdk_options import resolve_runtime

prev = os.environ.get("HSB_RUNTIME_WIO")
os.environ["HSB_RUNTIME_WIO"] = "codex"
raised = False
try:
    resolve_runtime("wio")
except ValueError as e:
    raised = True
    assert "WIO" in str(e) or "wio" in str(e).lower()
assert raised, "WIO hard-block missing — resolve_runtime('wio') accepted codex"

if prev is None:
    os.environ.pop("HSB_RUNTIME_WIO", None)
else:
    os.environ["HSB_RUNTIME_WIO"] = prev
print("WIO hard-block: HSB_RUNTIME_WIO=codex raises ValueError as expected")"""
        ),
    ),
    (
        "markdown",
        "skills-md",
        md(
            """\
## System-prompt assembly — what the LLM actually receives

`assemble_system_prompt()` reads the 7 skill files (5 lifecycle skills + skills 10/11) and concatenates them with `# SKILL: <stem>` separators. We render the size + per-skill name list so you can spot a missing or duplicated skill at a glance."""
        ),
    ),
    (
        "code",
        "skills-render",
        code(
            """\
import os as _os
import re

# assemble_system_prompt() reads relative paths under skills/ — run from ROOT
# so nbconvert (which uses /tmp as cwd) and Jupyter Lab both resolve them.
_os.chdir(ROOT)
prompt = wio.assemble_system_prompt()
print(f"total prompt size: {len(prompt):,} chars (~{len(prompt) / 4:.0f} tokens)")
for m in re.finditer(r"^# SKILL: (.+?)$", prompt, re.MULTILINE):
    print(f"  - {m.group(1)}")
print("\\nSKILL_FILES:")
for f in wio.SKILL_FILES:
    print("  ", f)"""
        ),
    ),
    (
        "markdown",
        "g3-md",
        md(
            """\
## G3 wiring — runtime backstop is called on every received message

`assert_no_task_dispatch` should appear in every receive loop. We grep the source for the call sites — if any loop loses the call, the runtime backstop disappears."""
        ),
    ),
    (
        "code",
        "g3-grep",
        code(
            """\
src = Path(wio.__file__).read_text()
calls = src.count("assert_no_task_dispatch(")
print(f"assert_no_task_dispatch call sites: {calls}")
assert calls >= 3, (
    f"G3 runtime backstop missing or reduced (found {calls}, expected >= 3)"
)
assert '"Agent"' not in src, "WIO allow-list contains Agent"
# AgentDefinition is the sub-subagent surface. Check it's not actually
# imported (mentions in docstrings or comments are fine — they're documenting
# the absence).
ad_imports = [
    line
    for line in src.splitlines()
    if re.match(r"^\\s*(from|import)\\s+", line) and "AgentDefinition" in line
]
assert not ad_imports, f"WIO imports AgentDefinition: {ad_imports}"
# `agents=` as a keyword argument to ClaudeAgentOptions registers sub-agents.
# Strip comment-only lines before searching so the prose warning at line 232
# ('Do NOT register agents={}') doesn't false-positive.
non_comment = "\\n".join(
    line for line in src.splitlines() if not line.lstrip().startswith("#")
)
kwarg_uses = re.findall(r"\\bagents\\s*=\\s*[\\[{]", non_comment)
assert not kwarg_uses, f"WIO passes agents= kwarg: {kwarg_uses}"
print("WIO: WORC-02 structural defences intact")"""
        ),
    ),
    (
        "markdown",
        "tools-md",
        md(
            """\
## In-process MCP tool wrappers (`@tool`)

Phase 2 agents are exposed via `create_sdk_mcp_server` rather than as sub-agents. The wrappers must each return the canonical `{"content":[{"type":"text","text":...}]}` envelope (Pitfall 4) — returning a Pydantic model directly silently fails the SDK serializer."""
        ),
    ),
    (
        "code",
        "tools-inspect",
        code(
            """\
for name in ["run_linear_tool", "run_builder_tool", "run_git_tool", "run_qa_tool"]:
    fn = getattr(wio, name, None)
    assert fn is not None, f"WIO missing {name}"
for name in ["run_linear_tool", "run_builder_tool", "run_git_tool", "run_qa_tool"]:
    block = src[src.index(f"async def {name}") : src.index(f"async def {name}") + 2000]
    assert '"content"' in block and '"text"' in block, (
        f"{name} missing canonical envelope"
    )
print("WIO: 4 @tool wrappers present, all return canonical content envelope")"""
        ),
    ),
    (
        "markdown",
        "live-md",
        md(
            """\
## Live run (gated)

If all gates are satisfied, drive a single task end-to-end. Output is structured but verbose (skill prompts + every tool call); expect a few minutes wall-clock and several hundred KB of stdout.

**Before clicking run:** confirm the LIN-ID points to a sandbox project, not a production board."""
        ),
    ),
    (
        "code",
        "live-run",
        code(
            """\
task_id = os.environ.get("HSB_NOTEBOOK_WIO_TASK_ID")
if not live_mode() or not task_id:
    print(
        gated(
            "WIO live run (set HSB_NOTEBOOK_WIO_TASK_ID=LIN-... and HSB_NOTEBOOK_RUN_LIVE=1)"
        )
    )
else:
    assert_g1_safe()
    print(f"Running WIO cycle for {task_id} (claude-only)…")
    asyncio.run(wio.run_orchestration_cycle(work_item_id=task_id))
    print("cycle complete — inspect Linear comments + GitHub PR for the artifacts")"""
        ),
    ),
]


def main() -> None:
    here = Path(__file__).parent
    targets = {
        "00_guardrails_audit.ipynb": NB_00,
        "01_contracts_playground.ipynb": NB_01,
        "02_risk_and_global_pure_logic.ipynb": NB_02,
        "03_main_orchestrator_dispatch.ipynb": NB_03,
        "04_linear_and_knowledge_readonly.ipynb": NB_04,
        "05_per_agent_smoke.ipynb": NB_05,
        "06_wio_full_loop.ipynb": NB_06,
    }
    for name, spec in targets.items():
        path = here / name
        # ensure_ascii=False keeps em-dashes, en-dashes etc. as raw UTF-8 so
        # the pre-commit notebook formatter doesn't rewrite — -> — on
        # every commit. indent=1 matches Jupyter Lab's save format.
        path.write_text(json.dumps(render(spec), indent=1, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(here.parent)}  ({len(spec)} cells)")


if __name__ == "__main__":
    main()
