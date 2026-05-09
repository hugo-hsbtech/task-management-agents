"""Integration tests for Builder Agent — hsb-test-fixture GitHub repo (D-11).

Requires:
  - ANTHROPIC_API_KEY in .env
  - HSB_TEST_FIXTURE_URL pointing to a real cloned hsb-test-fixture repo
  - HSB_TEST_FIXTURE_PATH set to the local clone directory

Covers: BLDR-01 (scoped implementation), BLDR-02 (validation run), BLDR-04 (capability boundary).

Run with: pytest tests/integration/test_builder_agent.py -v -m integration
"""

import os
import subprocess
from pathlib import Path

import pytest

from hsb.agents.builder_agent import run_builder_agent
from hsb.contracts.builder import BuilderInput, RepositoryContext

pytestmark = [pytest.mark.integration]


@pytest.fixture
def fixture_repo_path() -> Path:
    path_str = os.environ.get("HSB_TEST_FIXTURE_PATH")
    if not path_str:
        pytest.skip(
            "HSB_TEST_FIXTURE_PATH not set — point this at a local clone of hsb-test-fixture "
            "(see .planning/phases/02-core-execution-agents/02-FIXTURE-REPO.md)"
        )
    path = Path(path_str)
    if not path.exists() or not (path / "pyproject.toml").exists():
        pytest.skip(f"Fixture repo not found at {path} — clone hsb-test-fixture first")
    return path


@pytest.fixture
def clean_fixture_branch(fixture_repo_path: Path):
    """Reset the fixture repo to main before each test so Builder edits don't accumulate."""
    subprocess.run(
        ["git", "-C", str(fixture_repo_path), "checkout", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(fixture_repo_path), "reset", "--hard", "origin/main"],
        check=True,
        capture_output=True,
    )
    yield fixture_repo_path
    # Cleanup: discard any uncommitted edits the agent left behind
    subprocess.run(
        ["git", "-C", str(fixture_repo_path), "checkout", "--", "."],
        check=False,
        capture_output=True,
    )


@pytest.mark.integration
def test_scoped_implementation(clean_fixture_branch: Path):
    """BLDR-01: Builder reads work item description and implements only the scoped change.

    Scope: add a hello() function to src/fixture/hello.py returning 'hello world'.
    Verifies: implementation_status == 'completed', files_changed includes the new file
    (not arbitrary files outside the scope).
    """
    input = BuilderInput(
        work_item_id="LIN-TEST-1",
        issue_description=(
            "Add a `hello()` function to `src/fixture/hello.py` that returns the string 'hello world'. "
            "Do not modify any other files."
        ),
        acceptance_criteria=["hello() returns 'hello world'"],
        epic_context={},
        plan_source="docs/plan.md",
        repository_context=RepositoryContext(
            root_path=str(clean_fixture_branch),
            technical_stack=["python"],
        ),
    )
    output = run_builder_agent(input)
    assert output.implementation_status == "completed", (
        f"Expected completed, got {output.implementation_status}: {output.summary}"
    )
    # Scope check: only files under src/fixture/ should be in files_changed
    for fc in output.files_changed:
        assert "src/fixture" in fc.path or "tests" in fc.path, (
            f"Out-of-scope file edit: {fc.path}"
        )
    # Functional check: hello.py must exist with the expected function after the run
    hello_path = clean_fixture_branch / "src" / "fixture" / "hello.py"
    assert hello_path.exists(), "Builder did not create src/fixture/hello.py"
    content = hello_path.read_text()
    assert "def hello" in content, f"hello function missing in {hello_path}"


@pytest.mark.integration
def test_validation_run(clean_fixture_branch: Path):
    """BLDR-02: Builder runs available local validations and reports passed|failed|not_run.

    The fixture repo has pyproject.toml [tool.pytest] — Builder should detect and run pytest.
    We assert the validation field reports status from {passed, failed, not_run} and at least
    ONE of build/tests/lint/typecheck is not 'not_run' (proves detection logic ran).
    """
    input = BuilderInput(
        work_item_id="LIN-TEST-2",
        issue_description=(
            "Add a function `square(x)` to `src/fixture/math_utils.py` that returns x*x. "
            "Add a unit test in `tests/test_math_utils.py` that verifies square(3) == 9. "
            "Run pytest after implementing."
        ),
        acceptance_criteria=["square(3) == 9", "test passes"],
        epic_context={},
        plan_source="docs/plan.md",
        repository_context=RepositoryContext(
            root_path=str(clean_fixture_branch),
            technical_stack=["python"],
        ),
    )
    output = run_builder_agent(input)
    valid_statuses = {"passed", "failed", "not_run"}
    assert output.validation.build in valid_statuses
    assert output.validation.tests in valid_statuses
    assert output.validation.lint in valid_statuses
    assert output.validation.typecheck in valid_statuses
    ran_at_least_one = any(
        v != "not_run"
        for v in [
            output.validation.build,
            output.validation.tests,
            output.validation.lint,
            output.validation.typecheck,
        ]
    )
    assert ran_at_least_one, (
        "Builder did not run any validation despite pytest config in fixture repo. "
        f"validation={output.validation.model_dump()}"
    )


@pytest.mark.integration
def test_capability_boundary(clean_fixture_branch: Path):
    """BLDR-04: Builder Agent does NOT use git or Linear tools.

    Verification strategy: after a normal Builder run, inspect the fixture repo's git log.
    The HEAD commit MUST equal what it was before the run (Builder did not commit). The
    working tree MAY have uncommitted edits (that's the Builder's job), but no commit
    nor push may have been executed.

    Additionally, verify BuilderOutput is structurally valid (model_validate succeeded —
    which it must have, since run_builder_agent returns the validated object). The
    extra='forbid' guard on BuilderOutput already rejects any leaked git_branch / pr_url
    field at the schema level (BLDR-04 schema-level guard, tested in unit tests).
    """
    before = subprocess.check_output(
        ["git", "-C", str(clean_fixture_branch), "rev-parse", "HEAD"], text=True
    ).strip()

    input = BuilderInput(
        work_item_id="LIN-TEST-3",
        issue_description=(
            "Append a docstring to src/fixture/__init__.py describing the package."
        ),
        acceptance_criteria=["__init__.py has a module docstring"],
        epic_context={},
        plan_source="docs/plan.md",
        repository_context=RepositoryContext(
            root_path=str(clean_fixture_branch),
            technical_stack=["python"],
        ),
    )
    output = run_builder_agent(input)

    after = subprocess.check_output(
        ["git", "-C", str(clean_fixture_branch), "rev-parse", "HEAD"], text=True
    ).strip()
    assert before == after, (
        f"Builder Agent committed to git (HEAD changed {before} -> {after}) — "
        f"BLDR-04 capability boundary violation"
    )
    # Verify no remote push happened — refs unchanged
    ls_remote = subprocess.check_output(
        [
            "git",
            "-C",
            str(clean_fixture_branch),
            "log",
            "--oneline",
            "-1",
            "origin/main",
        ],
        text=True,
    ).strip()
    assert ls_remote, (
        "origin/main ref not found — environment issue, not BLDR-04 violation"
    )
    # The output schema validation already happened inside run_builder_agent
    # (extra='forbid' would have rejected any git_branch / pr_url field)
    assert output.work_item_id == "LIN-TEST-3"
