---
name: ezra-generate-backend-tests
description: Generate pytest tests for Python backend code with planning, generation, and automated healing
---

# Backend Test Generation Workflow

Generate comprehensive pytest tests for backend Python code using a structured workflow with specialized agents.

## When to Use This Skill

Use `/ezra-generate-backend-tests` when:

- You need to create unit tests for Python services, models, or utilities
- You need integration tests for API endpoints or database operations
- You want comprehensive test coverage following project standards
- You need to fix failing tests with automated healing

## Workflow Overview

This skill orchestrates three specialized agents:

1. **pytest-test-planner**: Analyzes code and creates detailed test plans
2. **pytest-test-generator**: Generates test code from plans
3. **pytest-test-healer**: Fixes failing tests automatically

## Usage Patterns

### Pattern 1: Generate Tests for a New Module

```
/ezra-generate-backend-tests backend/packages/apps/api/src/ezra_api/services/user_service.py
```

This will:

1. Resolve the package from the file path
2. Spawn pytest-test-planner to analyze the module
3. Review the test plan with you
4. Spawn pytest-test-generator to create tests
5. Run the tests
6. If failures occur, spawn pytest-test-healer to fix them

### Pattern 2: Generate Tests with Custom Plan

```
/ezra-generate-backend-tests --plan backend/packages/apps/api/tests/plans/user-service-plan.md
```

This will:

1. Read the existing test plan
2. Spawn pytest-test-generator to implement it
3. Run and heal tests as needed

### Pattern 3: Heal Failing Tests Only

```
/ezra-generate-backend-tests --heal backend/packages/apps/api/tests/test_user_service.py
```

This will:

1. Run the test file to capture failures
2. Spawn pytest-test-healer to fix issues
3. Verify fixes and report results

## Package Resolution

Given any source or test file path, resolve:

- **Package root**: Walk up from the file to find the nearest `pyproject.toml`
- **Package name**: Read `[project].name` from that `pyproject.toml`
- **Test dir**: `<package-root>/tests/`
- **Factories**: `<package-root>/tests/fixtures/factories.py`
- **Run command**: `cd backend && uv run pytest <test-path> -v`
- **Lint command**: `cd backend && uv run ruff check <test-file-path>`

Example: `backend/packages/apps/api/src/ezra_api/services/foo.py` →

- Package root: `backend/packages/apps/api/`
- Test file: `backend/packages/apps/api/tests/services/test_foo.py`
- Run: `cd backend && uv run pytest packages/apps/api/tests/services/test_foo.py -v`

## Execution Steps

### Step 1: Understand the Request

Parse command arguments:

- File path to test (required unless `--heal` or `--plan`)
- `--plan <path>`: Use existing test plan
- `--heal <test-file>`: Heal failing tests only
- `--unit-only`: Generate only unit tests
- `--integration-only`: Generate only integration tests

Resolve the package from the file path.

### Step 2: Create Test Plan (if not provided)

Spawn the **pytest-test-planner** agent:

```python
Task(
    subagent_type="pytest-test-planner",
    prompt=f"""Analyze {implementation_file} and create a comprehensive test plan.

The package is {package_name} at {package_root}.
Test dir: {package_root}/tests/
Factories: {package_root}/tests/fixtures/factories.py

CRITICAL — Unit vs Integration Test Boundary:

**Unit tests** (default, no marker) mock the layer below the code under test:
- Router tests: mock service layer functions via @patch, mock auth dependency, NO database.
  Test HTTP contract only: status codes, request validation (422), response shaping,
  correct service function called with correct args.
- Service tests: mock database session (AsyncMock), mock external clients.
  Test business logic in isolation.
- If a test needs a database to pass, it is NOT a unit test.

**Integration tests** (@pytest.mark.integration) only mock truly external services:
- Real Postgres via db_session fixture (savepoint rollback per test)
- Real service layer, real ORM queries
- Mock only: S3, SQS, auth providers, email, LLM APIs
- Test ONLY Postgres-specific behavior: JSONB, FK CASCADE, atomic UPDATE, string length,
  timezone-aware timestamps, onupdate triggers
- Do NOT duplicate unit test cases against real DB — only test what SQLite can't catch.

Generate BOTH unit and integration tests. Unit tests go in tests/routers/test_<name>.py.
Integration tests go in tests/routers/test_<name>_integration.py.

Include:
- All functions and methods to test
- Required factories
- Mocking strategies (service layer for unit, external services for integration)
- Edge cases and error scenarios
- Async test requirements

Focus on: {scope}  # unit, integration, or both
""",
    description="Analyze code and create test plan"
)
```

Present the test plan to the user for review and approval.

### Step 3: Generate Test Code

After plan approval, decide whether to write tests directly or delegate to an agent:

**Write directly** when:

- The main session already has context from the planning phase
- The test plan has ≤15 test cases
- The existing test file patterns are clear from prior reads

**Use pytest-test-generator agent** when:

- Generating tests for a large module from scratch (many test cases, complex setup)
- The main context window would be overwhelmed by the volume of code
- You haven't read the implementation or test files yet

#### Option A: Write directly (preferred when context is loaded)

Read the existing test file, match its patterns (imports, fixtures, mock setup, assertion style), and add the new tests directly using the Edit tool.

#### Option B: Delegate to agent

```python
Task(
    subagent_type="pytest-test-generator",
    prompt=f"""Generate pytest tests following this plan:

{test_plan}

Package: {package_name} at {package_root}
Implementation file: {implementation_file}
Test file: {test_file_path}

Follow project conventions:
- Use factories from tests/fixtures/factories.py
- Use fixtures from root conftest.py (via ezra_test_utils.fixtures plugin)
- asyncio_mode = "auto" so NO @pytest.mark.asyncio needed
- Follow naming convention: test_<function>_<condition>_<result>
- See docs/development-guides/testing-standards.md
""",
    description="Generate pytest test code"
)
```

### Step 4: Run Tests

```bash
cd backend && uv run pytest {test_file_path} -v
```

Capture the output and analyze results.

### Step 5: Heal Failures (if needed)

If tests fail, spawn the **pytest-test-healer** agent:

```python
Task(
    subagent_type="pytest-test-healer",
    prompt=f"""Fix failing tests in {test_file_path}.

Package: {package_name} at {package_root}
Run command: cd backend && uv run pytest {test_file_path} -v

Test output:
{pytest_output}

Steps:
1. Analyze each failure
2. Read implementation and test code
3. Apply minimal fixes
4. Verify each fix
5. Report results

Do not change test behavior unless it's incorrect.
""",
    description="Heal failing tests"
)
```

### Step 6: Final Verification

After healing:

1. Re-run all tests in the file: `cd backend && uv run pytest {test_file_path} -v`
2. Run linting: `cd backend && uv run ruff check {test_file_path}`
3. Report final status to user

## Important Guidelines

### Test Plan Review

- Always present the test plan to the user before generation
- Allow modifications to scope and test cases
- Confirm factories and mocking strategies

### Code Generation

- Follow project conventions from `docs/development-guides/testing-standards.md`
- Use existing factories from `<package>/tests/fixtures/factories.py`
- Use shared fixtures from root conftest (registered via `ezra_test_utils.fixtures`)
- Match test file structure to `src/` structure

### Test Healing

- Limit healing attempts to 3 iterations per test
- If tests still fail after 3 attempts, report to user for manual review
- Don't change test assertions without verifying correctness
- Preserve test coverage and intent

### Workflow Control

- Use Task tool to spawn agents (they run in separate contexts)
- Wait for agent completion before proceeding
- Present results at each stage for user review
- Allow user to skip healing if they prefer manual fixes
