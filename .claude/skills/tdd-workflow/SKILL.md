---
name: tdd-workflow
description: Enforces strict RED-GREEN-REFACTOR test-driven development for the Ezra monorepo. Use when the user explicitly wants TDD methodology — says "write tests first", "TDD", "test-driven", or wants to implement a feature with tests before code. Do NOT use when the user just wants to generate tests for existing code (use /ezra-generate-backend-tests or /ezra-generate-frontend-tests instead).
---

# Test-Driven Development Workflow

Enforces TDD methodology for the Ezra platform monorepo. All test patterns and conventions live in `docs/development-guides/testing-standards.md` — read it before writing any tests.

## When to Use This vs Other Testing Skills

| Goal | Use |
|------|-----|
| Implement a feature with tests-first (RED → GREEN → REFACTOR) | **This skill** |
| Generate tests for existing backend code | `/ezra-generate-backend-tests` |
| Generate tests for existing frontend code | `/ezra-generate-frontend-tests` |
| Generate E2E tests from a spec | `/ezra-generate-e2e-tests` |
| Scaffold test infrastructure for a new package | `/ezra-scaffold-*-tests` |

## Critical: Never Skip RED

The entire point of TDD is that tests drive the design. If you write implementation before tests, you're not doing TDD — you're retrofitting tests, which produces weaker coverage and misses edge cases the test-first approach would have caught.

**Hard rules:**
- Never write or edit production code before a failing test exists for the behavior
- If the user asks to "just implement it" without tests, push back — write the test first, show it failing, then implement
- If fixing a bug, write a test that reproduces the bug before touching the fix

## Step 1: Read Testing Standards

Read `docs/development-guides/testing-standards.md` for concrete patterns, factories, and conventions. Do not rely on examples from memory — the doc is the source of truth.

## Step 2: Identify Test Layers

| Change Type | Unit | Integration | E2E |
|-------------|------|-------------|-----|
| Backend service/CRUD | pytest | pytest (DB) | - |
| Backend API endpoint | pytest | pytest (httpx) | Playwright (if user-facing) |
| Frontend component | Vitest | - | - |
| Frontend page/feature | Vitest | Vitest (MSW) | Playwright (if critical flow) |
| Pure UI change | Vitest | - | - |
| Config/infra | - | - | - |

## Step 3: Write Tests First (RED)

Delegate to the appropriate planner/generator agent:

- **Backend**: `pytest-test-planner` → `pytest-test-generator`
- **Frontend**: `vitest-test-planner` → `vitest-test-generator`
- **E2E**: write spec in plan format, then `playwright-test-generator`

Or use the corresponding skills: `/ezra-generate-backend-tests`, `/ezra-generate-frontend-tests`, `/ezra-generate-e2e-tests`.

### Test Commands

```bash
# Backend
cd backend && uv run pytest packages/{package}/tests/ -v -x
cd backend && uv run pytest packages/ --cov --cov-report=term-missing

# Frontend
cd frontend && pnpm --filter @ezra/{package} test
cd frontend && pnpm --filter @ezra/{package} test:coverage

# E2E
cd frontend && pnpm turbo run test:e2e --filter=@ezra/{app}
```

## Step 4: Run Tests — Verify FAIL (Gate)

Run the appropriate command and confirm tests fail for the right reason — `NotImplementedError` or missing module, not import errors or syntax issues.

**This step is a gate.** Do not proceed to implementation until you have seen a genuine test failure. If tests pass already or fail for the wrong reason (syntax, import), fix the test first.

## Step 5: Implement Minimal Code (GREEN)

Write only enough code to make the existing failing tests pass. No premature abstractions. No code that isn't demanded by a failing test.

## Step 6: Run Tests — Verify PASS

## Step 7: Refactor (IMPROVE)

Remove duplication, improve names, optimize. Tests must stay green after each change.

## Step 8: Verify Coverage

Target: 80%+ coverage. 100% for critical business logic, auth, financial calculations.

## Healing Failing Tests

If tests fail after implementation, use the appropriate healer agent:

| Layer | Agent |
|-------|-------|
| Backend | `pytest-test-healer` |
| Frontend | `vitest-test-healer` |
| E2E | `playwright-test-healer` |

## Test File Organization

```
backend/packages/
  apps/api/
    tests/unit/          # pytest unit tests
    tests/integration/   # pytest integration tests (marked @pytest.mark.integration)
    tests/fixtures/      # factories

frontend/
  apps/app/
    tests/unit/          # vitest unit
    tests/integration/   # vitest + MSW
    tests/e2e/specs/     # playwright E2E
    tests/e2e/poms/      # page object models
  packages/hooks/
    tests/unit/          # vitest unit
```

## Anti-Patterns to Avoid

- **Writing implementation before tests** — the whole point of TDD is RED first
- **Testing implementation details** — test behavior, not internal state
- **Tests depending on each other** — each test creates its own data via factories
- **Mocking everything** — prefer real DB for integration tests (`@pytest.mark.integration`)
- **Skipping the RED phase** — always verify tests fail before implementing
- **Ignoring testing-standards.md** — use project conventions, not generic patterns

## CI/CD Integration

- Backend tests: `.github/workflows/backend-tests.yml`
- Frontend tests: `.github/workflows/frontend-tests.yml`
- E2E tests: `.github/workflows/e2e-tests.yml`
