---
description: Enforce test-driven development workflow. Scaffold interfaces, generate tests FIRST, then implement minimal code to pass. Ensure 80%+ coverage.
---

# TDD Command

Invokes the **tdd-guide** agent to enforce test-driven development following `docs/development-guides/testing-standards.md`.

## TDD Cycle

```
RED → GREEN → REFACTOR → REPEAT

RED:      Write a failing test (delegate to planner/generator agent)
GREEN:    Write minimal code to pass
REFACTOR: Improve code, keep tests passing
REPEAT:   Next feature/scenario
```

## Usage

```
/tdd I need a service to list users by organization
/tdd Add a hook to format currency values
/tdd Fix the duplicate email bug in user registration
```

The tdd-guide agent will:
1. Read `docs/development-guides/testing-standards.md` for project conventions
2. Identify scope — backend (pytest), frontend (Vitest), or E2E (Playwright)
3. Write failing tests via specialized planner/generator agents
4. Implement minimal code to pass
5. Refactor while keeping tests green
6. Verify 80%+ coverage

## Related Skills

- `/ezra-generate-backend-tests` — generate pytest tests (skips TDD ceremony, just tests)
- `/ezra-generate-frontend-tests` — generate Vitest tests
- `/ezra-generate-e2e-tests` — generate Playwright E2E tests
- `/ezra-create-plan` — plan includes test specs for all layers
