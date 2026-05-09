---
name: ezra-scaffold-frontend-package-tests
description: Scaffold Vitest testing infrastructure for a new shared frontend package (unit + integration, no E2E). Use when creating a new package in frontend/packages/, when user says "add tests to", "scaffold tests for", "setup testing for" a shared package, or when a new package like hooks, forms, or validators needs vitest config and smoke tests. Also use when retrofitting tests onto an existing package that has no tests yet. Do NOT use for frontend apps (use ezra-scaffold-frontend-app-tests instead).
---

# ezra-scaffold-frontend-package-tests

Scaffolds Vitest testing infrastructure for a new shared frontend package, following `docs/development-guides/testing-standards.md`.

## Input Format

```
/ezra-scaffold-frontend-package-tests forms
/ezra-scaffold-frontend-package-tests --name validators --preset node
```

**Parameters:**
- `name` (required): package name → `@ezra/{name}`
- `--preset` (optional): `react` (default) or `node`

## Preset Decision

| Package contains | Preset |
|-----------------|--------|
| React components | `react` |
| React hooks | `react` |
| Pure utilities (formatting, validation) | `node` |
| API client / fetch wrappers | `node` |
| Zod schemas | `node` |

When in doubt, use `react`.

## Step 1: Create Directory Structure

```bash
mkdir -p frontend/packages/{name}/tests/{unit,integration}
```

## Step 2: Create Vitest Config

### `vitest.config.mts` (react preset)

```ts
import { mergeConfig } from "vitest/config";
import reactConfig from "@ezra/vitest-config/react";

export default mergeConfig(reactConfig, {
  test: {
    setupFiles: ["./tests/setup.ts"],
  },
});
```

### `vitest.config.mts` (node preset)

```ts
import { mergeConfig } from "vitest/config";
import nodeConfig from "@ezra/vitest-config/node";

export default mergeConfig(nodeConfig, {});
```

## Step 3: Create Test Setup (react preset only)

### `tests/setup.ts`

```ts
import "@ezra/test-utils/setup";
```

## Step 4: Create Smoke Test

### `tests/unit/smoke.test.ts`

```ts
import { describe, expect, it } from "vitest";

describe("@ezra/{name} smoke test", () => {
  it("passes basic assertion", () => {
    expect(1 + 1).toBe(2);
  });
});
```

## Step 5: Update package.json

Add to `frontend/packages/{name}/package.json`:

**Scripts** (merge with existing):

```json
{
  "test": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage"
}
```

**DevDependencies** — before writing versions, check `frontend/pnpm-lock.yaml` or an existing package's `package.json` for current pinned versions. Never use `^` or `~`.

**React preset:**

```json
{
  "@ezra/vitest-config": "workspace:*",
  "@ezra/test-utils": "workspace:*",
  "vitest": "4.1.0",
  "@vitest/coverage-v8": "4.1.0",
  "@testing-library/react": "16.3.2",
  "@testing-library/jest-dom": "6.9.1",
  "msw": "2.12.13"
}
```

**Note on Orval-generated code**: If the package consumes hooks from `@ezra/api-client/<service>` (TanStack Query), tests must use `renderWithProviders` from `@ezra/test-utils/render` (includes QueryClientProvider). Prefer Orval-generated MSW handlers over hand-written ones.

**Node preset:**

```json
{
  "@ezra/vitest-config": "workspace:*",
  "vitest": "4.1.0",
  "@vitest/coverage-v8": "4.1.0"
}
```


## Step 6: Update TSConfig

Ensure `frontend/packages/{name}/tsconfig.json` has:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@tests/*": ["./tests/*"]
    }
  }
}
```

## Step 7: Register in Vitest Workspace

Add `"packages/{name}"` to `frontend/vitest.workspace.ts`:

```ts
export default [
  "apps/app",
  "packages/design-system",
  "packages/hooks",
  "packages/api-client",
  "packages/{name}",
];
```

## Step 8: Install + Verify

```bash
cd frontend && pnpm install

# Run tests
pnpm --filter @ezra/{name} test

# Turbo discovers it
pnpm turbo run test --filter=@ezra/{name}

# Coverage
pnpm --filter @ezra/{name} test:coverage
```

## Examples

**Example 1:** React package with hooks
```
User: /ezra-scaffold-frontend-package-tests forms
Result: vitest.config.mts (react preset), tests/setup.ts, tests/unit/smoke.test.ts
        vitest.workspace.ts updated, @ezra/test-utils + MSW added to devDeps
```

**Example 2:** Pure utility package
```
User: /ezra-scaffold-frontend-package-tests --name validators --preset node
Result: vitest.config.mts (node preset), tests/unit/smoke.test.ts (no setup.ts)
        vitest.workspace.ts updated, minimal devDeps (no @ezra/test-utils, no MSW)
```

## Troubleshooting

**Smoke test fails with "Cannot find module @ezra/vitest-config":**
- Run `cd frontend && pnpm install`

**Turbo doesn't discover tests:**
- Check `frontend/vitest.workspace.ts` includes `"packages/{name}"`
- Check `package.json` has `"test": "vitest run"` script

**"Cannot find module @ezra/test-utils/setup" (node preset):**
- Node preset should NOT have `tests/setup.ts` — remove it
- Node preset vitest config should NOT have `setupFiles`

## What This Skill Does NOT Do

- Does not create the package itself (package.json, src/, exports)
- Does not create E2E tests (shared packages tested via app integration)
- Does not install dependencies (`pnpm install` is post-scaffold)
- Does not write feature tests (use `/ezra-generate-frontend-tests`)
- Does not create factories (created on demand by test generation skills)

## Key Conventions

- Always use explicit vitest imports: `import { describe, it, expect } from "vitest"`
- MSW servers are per-test-file (not global), with `onUnhandledRequest: "error"`
- Test files: `.test.ts` for logic, `.test.tsx` for components
- `@ezra/test-utils` optional for `node` preset (no React rendering needed)
- `renderWithProviders` from `@ezra/test-utils/render` for components needing providers
- `renderHookWithProviders` from `@ezra/test-utils/renderHook` for hooks needing providers
