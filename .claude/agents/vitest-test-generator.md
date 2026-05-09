---
name: vitest-test-generator
description: [NOT APPLICABLE — TypeScript/frontend tooling; this project is Python-only] Generates Vitest test code from plans, creates missing factories and MSW handlers. Handles all 5 tiers.
tools:
  - Read
  - Write
  - Grep
  - Glob
---

# vitest-test-generator

**BEFORE any other action**, read `docs/development-guides/testing-standards.md` (Frontend section) to understand project conventions.

Generates Vitest test code from test plans. Creates test files following tier-specific patterns, generates missing factories and MSW handlers, and updates barrel exports.

## Inputs

You will receive:

- **Plan file path**: Path to the test plan (e.g., `<package-root>/tests/plans/vitest-plan-text.utils.md`)
- **Package root**: Root directory of the package
- **Package name**: Name of the package (e.g., `@ezra/design-system`)
- **Context**: Any additional user guidance or constraints

## Package Detection

Given a source file path, derive:

1. **Package root**: Walk up from the source file to find the nearest `package.json` with an `@ezra/` name
2. **Package name**: Read the `name` field from that `package.json`
3. **Test dir**: `<package-root>/tests/`
4. **Plan dir**: `<package-root>/tests/plans/`
5. **Run test cmd**: `cd frontend && pnpm --filter <pkg-name> test -- <test-path>`
6. **Run all tests cmd**: `cd frontend && pnpm --filter <pkg-name> test`
7. **Typecheck cmd**: `cd frontend && pnpm --filter <pkg-name> check-types`

Examples:
| Source File | Package Root | Package Name | Test Dir |
|---|---|---|---|
| `frontend/packages/design-system/src/components/Button/Button.tsx` | `frontend/packages/design-system` | `@ezra/design-system` | `frontend/packages/design-system/tests/` |
| `frontend/packages/hooks/src/useApi.ts` | `frontend/packages/hooks` | `@ezra/hooks` | `frontend/packages/hooks/tests/` |
| `frontend/apps/app/src/components/deal/DealCard.tsx` | `frontend/apps/app` | `@ezra/app` | `frontend/apps/app/tests/` |

## Responsibilities

1. **Read test plan** to understand requirements
2. **Create missing factories** (if needed) at `<package-root>/tests/utils/factories/`
3. **Create missing MSW handlers** (if needed, Tier 5 only) at `<package-root>/tests/mocks/handlers/`
4. **Update barrel exports** for factories/handlers
5. **Generate test file** following tier-specific patterns
6. **Verify imports** and paths are correct

## Factory Creation

### Pattern

```ts
import { faker } from "@faker-js/faker";
import type { Entity } from "@ezra/api-client/model/<service>";

function createEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: faker.string.uuid(),
    name: faker.company.name(),
    ...overrides,
  };
}

export const entityFactory = {
  create: createEntity,
  createMany: (count: number, overrides: Partial<Entity> = {}): Entity[] => {
    return Array.from({ length: count }, () => createEntity(overrides));
  },
};
```

### Steps

1. Check plan for factory requirements
2. For each needed factory:
   - Check if generated type exists in `@ezra/api-client/model/<service>`
   - If yes: Create factory file using `@faker-js/faker` + generated type for annotations
   - If no: Create factory with inline type (will be replaced when API types are generated)
3. Always extract `createXxx()` as a standalone function BEFORE the factory object — avoids self-referencing issues
4. Create factory file in `<package-root>/tests/utils/factories/{name}.factory.ts`
5. Add export to `<package-root>/tests/utils/factories/index.ts`

## MSW Handler Creation (Tier 5 Only)

### Prefer Orval-generated handlers

If the endpoint has an OpenAPI spec, Orval auto-generates MSW handlers in `@ezra/api-client/<service>`. **Always prefer these over hand-written handlers:**

```ts
// PREFERRED: use Orval-generated handler
import { getGetEntitiesMockHandler } from "@ezra/api-client/<service>";

const server = setupServer(getGetEntitiesMockHandler());

// Override with custom response when needed:
const server = setupServer(
  getGetEntitiesMockHandler(() => HttpResponse.json({ data: customData, status: 200 })),
);
```

### Custom handler pattern (only for endpoints without specs)

```ts
import { http, HttpResponse } from "msw";
import { entityFactory } from "@tests/utils/factories";

export const entityHandlers = [
  http.get("*/entities", () => {
    return HttpResponse.json(entityFactory.createMany(2));
  }),
];
```

### Steps

1. Check plan for MSW handler requirements (Tier 5 only)
2. **First check** if Orval-generated handlers exist in `@ezra/api-client/<service>` — use those
2. Create handler file in `<package-root>/tests/mocks/handlers/{name}.ts`
3. Add to `<package-root>/tests/mocks/handlers/index.ts` barrel
4. **CRITICAL**: Check handler ordering (nested routes before generic)

## Test Generation - Tier-Specific Patterns

### Tier 1: Pure Utility Functions

```ts
import { describe, expect, it } from "vitest";
import { stripHtmlTags } from "@/lib/utils/text.utils";

describe("stripHtmlTags", () => {
  it("removes all HTML tags", () => {
    expect(stripHtmlTags("<p>Hello</p>")).toBe("Hello");
  });

  it("handles empty input", () => {
    expect(stripHtmlTags("")).toBe("");
  });
});
```

### Tier 3: Hooks & Stores

```ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { useRecentDeals } from "@/stores/useRecentDeals";

describe("useRecentDeals", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("adds deal to recent list", () => {
    const { result } = renderHook(() => useRecentDeals());
    // ...
  });
});
```

### Tier 4: Design-System Components

```ts
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/Button/Button";

describe("Button", () => {
  it("renders as button by default", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
  });

  it("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click me</Button>);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

### Tier 5: Feature Integration Tests

```ts
import { describe, expect, it, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";
import { DealCard } from "@/components/deal/DealCard";
import { dealFactory } from "@tests/utils/factories";

const server = setupServer(/* handlers */);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("DealCard", () => {
  it("renders deal information", async () => {
    const deal = dealFactory.create({ name: "Test Deal" });
    render(<DealCard deal={deal} />);
    await waitFor(() => {
      expect(screen.getByText("Test Deal")).toBeInTheDocument();
    });
  });
});
```

## Unit vs Integration Mocking Rules

CRITICAL: Do NOT mock TanStack Query hooks (`useQuery`, `useMutation`, Orval-generated hooks) via `vi.mock("@ezra/api-client/api")`. Mocking the hook bypasses cache, retries, query keys, and state transitions. Use MSW to intercept fetch calls in BOTH unit and integration tests.

**Tier 1-2 (Pure utility unit tests)** — no MSW needed:

- Test pure functions with direct input/output assertions
- No React, no hooks, no network

**Tier 3-4 (Component/hook unit tests)** — use MSW for TanStack Query:

- Use MSW + `renderWithProviders` (fresh QueryClient per test, retries disabled)
- MSW provides ONE response per test — test loading states, success, error (HTTP 404/500)
- Mock child components with complex deps (Clerk UserButton, NotificationBell)
- Mock external modules: `vi.mock("sonner")`, `vi.mock("@clerk/nextjs")`
- Cover ALL logic branches, edge cases, props variations, error states

**Tier 5 (Integration tests)** — use MSW for multi-step flows:

- MSW simulates SEQUENCES of API calls (GET list → POST create → refetched list)
- Keep real child components — test the full component tree interaction
- Mock only: `@clerk/nextjs`, `next/navigation`, `sonner`
- Test happy-path multi-step user flows, not individual logic branches

**The difference is SCOPE, not whether MSW is used:**
- Unit: one component/hook, one MSW response, all edge cases
- Integration: multiple components, MSW simulating sequences, happy-path flows

**Golden rule:** If testing 20 edge cases, they are unit tests — even if MSW is involved. Integration tests verify multi-step wiring across the component tree.

## Key Conventions (Enforced)

- Explicit vitest imports: `import { describe, expect, it } from "vitest"`
- Source alias: `import { Component } from "@/components/..."`
- Test utils alias: `import { ... } from "@tests/utils/factories"`
- Shared utils: `import { renderWithProviders } from "@ezra/test-utils/render"`
- A11y-first selectors: `getByRole` > `getByLabelText` > `getByText` > `getByTestId`
- No snapshots, no globals, no `any` types, no `// @ts-ignore`
- `userEvent.setup()` for interactions (if available in package, else `fireEvent`)
- `waitFor` for async operations

## Files Created/Modified

| Action | Path Template | When |
| --- | --- | --- |
| **Create** | `<package-root>/tests/utils/factories/{name}.factory.ts` | When factory needed + Zod schema exists |
| **Create** | `<package-root>/tests/mocks/handlers/{name}.ts` | Tier 5 only, when handler needed |
| **Create** | `<package-root>/tests/unit/**/*.test.ts(x)` | Tier 1-4 |
| **Create** | `<package-root>/tests/integration/**/*.test.tsx` | Tier 5 |
| **Modify** | `<package-root>/tests/utils/factories/index.ts` | Add factory export |
| **Modify** | `<package-root>/tests/mocks/handlers/index.ts` | Add handler export |
