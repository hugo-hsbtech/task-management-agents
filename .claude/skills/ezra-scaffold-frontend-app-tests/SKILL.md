---
name: ezra-scaffold-frontend-app-tests
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Scaffold Vitest unit/integration + Playwright E2E testing infrastructure for a new frontend app. Use when creating a new app in frontend/apps/, when user says "add tests to", "scaffold tests for", "setup testing for" a frontend app, or when a new Next.js app needs vitest config, E2E with Testcontainers, POMs, and Playwright fixtures. Also use when retrofitting tests onto an existing app that has no tests yet.
---

# ezra-scaffold-frontend-app-tests

Scaffolds complete testing infrastructure (unit, integration, E2E) for a new frontend app, following `docs/development-guides/testing-standards.md`.

## Input Format

```
/ezra-scaffold-frontend-app-tests billing
/ezra-scaffold-frontend-app-tests --name billing --frontend-port 3002 --backend-package ezra-billing --backend-port 8002 --e2e-port 18002
```

**Parameters:**
- `name` (required): app name → `@ezra/{name}`
- `--frontend-port` (optional, default: ask user): Next.js dev port
- `--backend-package` (optional, default: `ezra-{name}`): backend uv package name
- `--backend-port` (optional, default: ask user): dev API port
- `--e2e-port` (optional, default: backend-port + 10000): E2E API port (avoids dev collision)

## Step 1: Create Directory Structure

```bash
mkdir -p frontend/apps/{name}/tests/{unit,integration}
mkdir -p frontend/apps/{name}/tests/e2e/{specs,poms,fixtures,config,plans,mocks/handlers}
```

## Step 2: Create Vitest Files

### `vitest.config.mts`

```ts
import { mergeConfig } from "vitest/config";
import reactConfig from "@ezra/vitest-config/react";

export default mergeConfig(reactConfig, {
  test: {
    setupFiles: ["./tests/setup.ts"],
  },
});
```

### `tests/setup.ts`

```ts
import "@ezra/test-utils/setup";
```

### `tests/unit/smoke.test.ts`

```ts
import { describe, expect, it } from "vitest";

describe("@ezra/{name} smoke test", () => {
  it("passes basic assertion", () => {
    expect(1 + 1).toBe(2);
  });
});
```

## Step 3: Create Playwright Config

### `playwright.config.ts`

```ts
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:{frontend_port}";
const apiPort = process.env.E2E_API_PORT ?? "{e2e_port}";
const apiURL = process.env.E2E_API_URL ?? `http://localhost:${apiPort}`;

export default defineConfig({
  testDir: "tests/e2e/specs",
  // Set to false when tests share a single auth user + DB (e.g., Clerk storageState)
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: process.env.CI
    ? [
        ["html", { open: "never" }],
        ["junit", { outputFile: "playwright-results.xml" }],
      ]
    : [["html"]],

  ...(!process.env.E2E_BASE_URL && {
    globalSetup: require.resolve("./tests/e2e/global-setup"),
    globalTeardown: require.resolve("./tests/e2e/global-teardown"),
  }),

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  ...(!process.env.E2E_BASE_URL && {
    webServer: {
      command: process.env.CI ? "pnpm start" : "pnpm dev",
      url: baseURL,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        ...process.env,
        NEXT_PUBLIC_API_URL: apiURL,
      },
    },
  }),
});
```

## Step 4: Create E2E Global Setup/Teardown

### `tests/e2e/global-setup.ts`

```ts
import { PostgreSqlContainer } from "@testcontainers/postgresql";
import { execSync, spawn } from "node:child_process";
import path from "node:path";

const BACKEND_ROOT = path.resolve(__dirname, "../../../../../backend");
const API_PORT = process.env.E2E_API_PORT ?? "{e2e_port}";

function waitForHealthz(url: string, timeoutMs = 30_000): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      fetch(url)
        .then((res) => {
          if (res.ok) return resolve();
          retry();
        })
        .catch(retry);
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error(`Timed out waiting for ${url}`));
      }
      setTimeout(check, 500);
    };
    check();
  });
}

async function globalSetup() {
  const postgres = await new PostgreSqlContainer("postgres:17-alpine").start();

  const dbUrl = [
    "postgresql+asyncpg://",
    `${postgres.getUsername()}:${postgres.getPassword()}`,
    `@${postgres.getHost()}:${postgres.getMappedPort(5432)}`,
    `/${postgres.getDatabase()}`,
  ].join("");

  execSync("uv run alembic upgrade head", {
    cwd: BACKEND_ROOT,
    env: { ...process.env, DATABASE_URL: dbUrl },
    stdio: "pipe",
  });

  const api = spawn(
    "uv",
    [
      "run", "--package", "{backend_package}",
      "fastapi", "run", "--host", "0.0.0.0", "--port", API_PORT,
      "packages/apps/{backend_app_dir}/src/{backend_module}/main.py",
    ],
    {
      cwd: BACKEND_ROOT,
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
        CORS_ORIGINS: '["http://localhost:{frontend_port}"]',
      },
      stdio: "pipe",
    },
  );

  await waitForHealthz(`http://localhost:${API_PORT}/healthz`);
  process.env.E2E_API_URL = `http://localhost:${API_PORT}`;

  (globalThis as Record<string, unknown>).__E2E_INFRA__ = { postgres, api };
}

export default globalSetup;
```

### `tests/e2e/global-teardown.ts`

```ts
import type { StartedPostgreSqlContainer } from "@testcontainers/postgresql";
import type { ChildProcess } from "node:child_process";

interface Infra {
  postgres: StartedPostgreSqlContainer;
  api: ChildProcess;
}

async function globalTeardown() {
  const infra = (globalThis as Record<string, unknown>).__E2E_INFRA__ as Infra | undefined;
  if (!infra) return;
  infra.api.kill("SIGTERM");
  await infra.postgres.stop();
}

export default globalTeardown;
```

## Step 5: Create E2E POMs

### `tests/e2e/poms/base.page.ts`

```ts
import type { Page } from "@playwright/test";

export class BasePage {
  constructor(public readonly page: Page) {}

  async goto(path: string = "/") {
    await this.page.goto(path);
  }

  async waitForPageLoad() {
    await this.page.waitForLoadState("load");
  }
}
```

### `tests/e2e/poms/home.page.ts`

```ts
import { expect, type Page } from "@playwright/test";
import { BasePage } from "./base.page";

export class HomePage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  readonly heading = () => this.page.getByRole("heading").first();

  async expectPageLoaded() {
    await expect(this.heading()).toBeVisible();
  }
}
```

### `tests/e2e/poms/index.ts`

```ts
export { BasePage } from "./base.page";
export { HomePage } from "./home.page";
```

## Step 6: Create E2E Fixtures

### `tests/e2e/fixtures/pages.fixture.ts`

```ts
import { test as base, expect } from "@playwright/test";
import { HomePage } from "../poms";

type PageFixtures = {
  homePage: HomePage;
};

export const test = base.extend<PageFixtures>({
  homePage: async ({ page }, use) => {
    const homePage = new HomePage(page);
    await homePage.goto();
    await use(homePage);
  },
});

export { expect };
```

### `tests/e2e/fixtures/data.fixture.ts`

```ts
import { test as base } from "./pages.fixture";

type DataFixtures = Record<string, never>;

export const test = base.extend<DataFixtures>({
  /**
   * Data fixture pattern (Request-Response-Recycle):
   *
   * 1. SEED: Insert directly into Testcontainers Postgres via `pg` pool from `db/seed.ts` — NOT via HTTP API (avoids auth tokens)
   * 2. YIELD: Give entity to test via `await use(entity)`
   * 3. TEARDOWN: Delete via API (code after `await use()` runs post-test)
   */
});

export { expect } from "@playwright/test";
```

## Step 7: Create E2E Config + Plans

### `tests/e2e/config/environments.ts`

```ts
export const ENV = {
  baseURL: process.env.E2E_BASE_URL ?? "http://localhost:{frontend_port}",
  apiURL: process.env.E2E_API_URL ?? "http://localhost:{e2e_port}",
} as const;
```

### `tests/e2e/specs/home.spec.ts`

```ts
import { test } from "../fixtures/pages.fixture";

test.describe("{AppName} Home Page", () => {
  test("page loads", async ({ homePage }) => {
    await homePage.expectPageLoaded();
  });
});
```

### `tests/e2e/mocks/handlers/index.ts`

```ts
export const handlers = [
  // Add MSW http handlers here for E2E API mocking (optional).
  // Most E2E tests hit the real API via Testcontainers.
];
```

### `tests/e2e/plans/README.md`

```markdown
# E2E Test Plans

Place test plan specs here for `/ezra-generate-e2e-tests`.
See `docs/development-guides/testing-standards.md` for the spec format.
```

## Step 8: Update package.json

Add to `frontend/apps/{name}/package.json`:

**Scripts** (merge with existing):

```json
{
  "test": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage",
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui",
  "test:e2e:headed": "playwright test --headed",
  "test:e2e:debug": "playwright test --debug",
  "test:e2e:report": "playwright show-report"
}
```

**DevDependencies** (merge with existing):

> **Before writing versions**: check `frontend/pnpm-lock.yaml` or `frontend/apps/app/package.json` for current pinned versions. Never use `^` or `~`.

```json
{
  "@ezra/vitest-config": "workspace:*",
  "@ezra/test-utils": "workspace:*",
  "vitest": "4.1.0",
  "@vitest/coverage-v8": "4.1.0",
  "@testing-library/react": "16.3.2",
  "@testing-library/jest-dom": "6.9.1",
  "msw": "2.12.13",
  "@playwright/test": "1.58.2",
  "testcontainers": "11.13.0",
  "@testcontainers/postgresql": "11.13.0"
}
```

**Note on Orval-generated code**: If the app uses TanStack Query hooks from `@ezra/api-client/<service>`, ensure `@tanstack/react-query` is in dependencies and `@tanstack/react-query-devtools` in devDependencies. Integration tests for components using these hooks must use `renderWithProviders` from `@ezra/test-utils/render` (includes QueryClientProvider). Prefer Orval-generated MSW handlers (`getXxxMockHandler` from `@ezra/api-client/<service>`) over hand-written ones.

**If the app uses Clerk auth**, also add `@clerk/testing` to devDependencies and:
- Add `storageState` to `playwright.config.ts` `use` block (sign in once, reuse)
- Add `clerkSetup()` + `clerk.signIn()` + `context.storageState()` in `global-setup.ts`
- Add `setupClerkTestingToken({ page })` in `pages.fixture.ts` page override
- Add `credentials.ts` in `config/` that loads `.env.e2e`
- Create `.env.e2e` with `E2E_CLERK_USER_USERNAME`, `E2E_CLERK_USER_PASSWORD`, `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`
- Set `fullyParallel: false` (shared user/DB)
- Test user MUST have MFA disabled (`@clerk/testing` doesn't support MFA)
- Add `authToken` data fixture: extract JWT via `window.Clerk.session.getToken()` for API seeding

## Step 9: Update Monorepo Config

### `frontend/vitest.workspace.ts`

Add `"apps/{name}"` to the array.

### `frontend/apps/{name}/tsconfig.json`

Ensure these exist:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@tests/*": ["./tests/*"]
    }
  },
  "exclude": ["node_modules", "playwright-report", "test-results"]
}
```

### `frontend/apps/{name}/eslint.config.mjs`

Add to `globalIgnores`:

```ts
globalIgnores(["...", "playwright-report/**", "test-results/**"]),
{
  files: ["tests/e2e/**/*.ts"],
  rules: { "react-hooks/rules-of-hooks": "off" },
},
```

## Step 10: Install + Verify

```bash
cd frontend && pnpm install

# TypeScript — MANDATORY, run before anything else
pnpm --filter @ezra/{name} check-types

# Vitest
pnpm --filter @ezra/{name} test

# Playwright listing
cd frontend/apps/{name} && npx playwright test --list

# Turbo
cd frontend && pnpm turbo run test --filter=@ezra/{name}
```

**CRITICAL**: If `check-types` fails, fix ALL TS errors before proceeding. Common issues:
- `protected` on BasePage.page — must be `public`
- `@faker-js/faker` import — use `@ezra/test-utils/factories/setup`
- Unused fixture params — prefix with `_`

## Examples

**Example 1:** Scaffolding tests for a billing app
```
User: /ezra-scaffold-frontend-app-tests --name billing --frontend-port 3002 --backend-package ezra-billing --backend-port 8002 --e2e-port 18002
Result: vitest.config.mts, playwright.config.ts, global-setup/teardown, POMs, fixtures, smoke tests
        vitest.workspace.ts updated, eslint + tsconfig configured
```

**Example 2:** Scaffolding with defaults
```
User: /ezra-scaffold-frontend-app-tests dashboard
Agent asks: What frontend port? What backend package name? What backend port?
Result: Same as above with user-provided values
```

## Troubleshooting

**Vitest smoke test fails with "Cannot find module @ezra/vitest-config":**
- Run `cd frontend && pnpm install` to resolve workspace dependencies

**Playwright test listing fails:**
- Ensure `playwright.config.ts` is excluded from tsconfig: `"exclude": ["playwright.config.ts"]`
- Run `npx playwright install chromium` to install browser

**E2E globalSetup fails with "uv: command not found":**
- Ensure `uv` is installed and in PATH
- Backend deps need installing: `cd backend && uv sync`

**Turbo doesn't discover the new app's tests:**
- Check the app is listed in `frontend/vitest.workspace.ts`
- Check `package.json` has `"test": "vitest run"` script

## What This Skill Does NOT Do

- Does not create the app itself (Next.js boilerplate, src/, base package.json)
- Does not create docker-compose services
- Does not modify CI workflows — **you must manually update `.github/workflows/e2e-tests.yml`** to add the new app's filter, Playwright install, and artifact upload steps (the workflow hardcodes `@ezra/app`; unit tests auto-discover via turbo but E2E does not)
- Does not write feature tests (use `/ezra-generate-frontend-tests` + `/ezra-generate-e2e-tests`)
- Does not install Playwright browsers (run `npx playwright install chromium` separately)

## Future Consideration: Shared E2E Package

When a second app gets E2E tests, consider extracting common infrastructure into `@ezra/e2e-utils`:
- `BasePage` POM, `waitForHealthz`, Testcontainers setup factory (parameterized by backend package/port)
- `createPlaywrightConfig({ frontendPort, backendPackage, e2ePort })` preset (like `@ezra/vitest-config`)
- Data fixture base patterns

This would reduce per-app scaffolding to a config call + app-specific POMs/specs. Until then, duplicating across one app is fine — extract after the second app confirms the pattern.
