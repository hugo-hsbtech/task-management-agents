---
name: ezra-generate-e2e-tests
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Generate e2e Playwright tests from test plan specs with automated healing and refinement
model: opus
---

# ezra-generate-e2e-tests

Orchestrates e2e Playwright test generation from specs defined in test plan files. Leverages `playwright-test-generator` and `playwright-test-healer` agents, follows testing-standards, handles data seeding/teardown/mocking.

## Platform Architecture (CRITICAL)

This is a multi-app monorepo. Each app has its own backend API and frontend.
NEVER mix APIs or apps that are not related to each other.

| App | Frontend | Dev API | E2E API | E2E Tests |
|-----|----------|---------|---------|-----------|
| app | localhost:3000 | localhost:8000 | localhost:18000 | frontend/apps/app/tests/e2e/ |
| example | localhost:3001 | localhost:8001 | localhost:18001 | frontend/apps/example/tests/e2e/ |

E2E infrastructure (managed by globalSetup/globalTeardown):
- **Testcontainers Postgres** on random port (isolated, ephemeral DB)
- **FastAPI subprocess** on fixed E2E port (18000) — NOT dev API (8000)
- **webServer** starts Next.js with `NEXT_PUBLIC_API_URL=http://localhost:18000`

## Input Format

**With app and spec reference:**

```
/ezra-generate-e2e-tests --app app Spec 3
/ezra-generate-e2e-tests --app app Spec 3: Home Page
/ezra-generate-e2e-tests --app app custom/plan.md Spec 1
```

**Without --app:** Defaults to `app`.

**Without params:** Prompt user with available specs from default plan.

**Default plan:** `frontend/apps/{app}/tests/e2e/plans/` (first `.md` file found)

## Phase 1: Input Parsing & Context Gathering

### Parse Input

- Extract `--app` parameter (default: `app`)
- If no spec parameter: read default plan, list all specs, prompt user to select
- If spec reference provided: extract spec number/name
- If custom plan path provided: use that path instead of default

### Gather Context

Read the following files to understand patterns and requirements:

| Resource | Path | Purpose |
|----------|------|---------|
| Test plan | (user-provided or default) | Spec definitions |
| Testing standards | `docs/development-guides/testing-standards.md` | E2E best practices |
| Playwright config | `frontend/apps/{app}/playwright.config.ts` | Test runner config |
| Page fixtures | `frontend/apps/{app}/tests/e2e/fixtures/pages.fixture.ts` | POM fixtures |
| Data fixtures | `frontend/apps/{app}/tests/e2e/fixtures/data.fixture.ts` | Data seeding pattern |
| Environment config | `frontend/apps/{app}/tests/e2e/config/environments.ts` | API URLs |
| Existing POMs | `frontend/apps/{app}/tests/e2e/poms/` (glob `**/*.ts`) | POM patterns |
| Existing specs | `frontend/apps/{app}/tests/e2e/specs/` (glob `**/*.spec.ts`) | Test patterns |
| E2E mock handlers | `frontend/apps/{app}/tests/e2e/mocks/handlers/` | Network mocking |

### Extract Spec Details

From the test plan, parse the spec section to extract:

- **File path** (where the test spec will live)
- **POM needed** (which Page Object Model(s) required)
- **Seed data** (entities to create via Playwright fixtures + API calls)
- **Auth** (authentication setup required)
- **Teardown** (cleanup strategy — fixture teardown + ephemeral DB)
- **Mocking** (API routes to mock via page.route())
- **Test table** (individual test cases with steps + assertions)

## Phase 2: Preparation (POM, Data Fixtures, Page Fixtures)

### Create/Extend Page Object Models

**If spec requires a new POM:**

1. Create class extending `BasePage` in `frontend/apps/{app}/tests/e2e/poms/`
2. Use A11y-first locators (role > label > text > testid)
3. Example structure:

```ts
import { BasePage } from "./base.page";
import type { Page } from "@playwright/test";

export class NewPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  // Locators — A11y-first
  readonly submitButton = () =>
    this.page.getByRole("button", { name: "Submit" });

  // Actions
  async submit() {
    await this.submitButton().click();
  }
}
```

4. Export from `frontend/apps/{app}/tests/e2e/poms/index.ts` barrel

**If extending existing POM:**

- Add new locators/actions following existing patterns
- Maintain consistency with A11y-first approach

### Create/Extend Data Fixtures

**Seed data directly into Testcontainers Postgres — no HTTP, no auth tokens.**

Create a `db/seed.ts` utility with helpers that INSERT directly via `pg` (node-postgres):

```ts
// tests/e2e/db/seed.ts
import pg from "pg";

let _pool: pg.Pool | null = null;
function pool(): pg.Pool {
  if (!_pool) _pool = new pg.Pool({ connectionString: process.env.E2E_DATABASE_URL, max: 5 });
  return _pool;
}

export async function seedDeal(overrides = {}): Promise<SeededDeal> {
  const userId = await getTestUserId();
  const result = await pool().query(
    `INSERT INTO deals (id, user_id, company_name, description, triage_status)
     VALUES (gen_random_uuid(), $1, $2, $3, $4)
     RETURNING id, user_id, company_name, description, triage_status`,
    [userId, overrides.company_name ?? `E2E ${crypto.randomUUID().slice(0,8)}`, ...],
  );
  return result.rows[0];
}

export async function deleteDeal(id: string) { ... }
export async function deleteAllDeals() { ... }
export async function closePool() { if (_pool) { await _pool.end(); _pool = null; } }
```

Data fixtures use these helpers:

```ts
// tests/e2e/fixtures/data.fixture.ts
import { seedDeal, deleteDeal } from "../db/seed";

seededDeal: async ({}, use) => {
  const deal = await seedDeal();
  await use(deal);
  await deleteDeal(deal.id);
},
```

**Why direct DB over API calls:**
- No auth tokens needed — bypasses Clerk entirely for seeding
- Faster — no HTTP overhead
- More reliable — no token expiry, no race conditions
- Connection string comes from `E2E_DATABASE_URL` env var set by global-setup

**Rules:**
- One fixture = one entity. Compose via fixture dependencies.
- Always use `crypto.randomUUID()` for unique identifiers.
- Cleanup in fixture teardown (code after `await use()`).
- Call `closePool()` in `global-teardown.ts` to close pg connections before stopping containers.
- Global-setup must pre-seed the test user in `auth_users` via `postgres.exec(["psql", ...])` after Clerk sign-in.

**Required devDeps:** `pg`, `@types/pg`

### Update POM Fixtures

**Register new POM in `frontend/apps/{app}/tests/e2e/fixtures/pages.fixture.ts`:**

```ts
import { NewPage } from "../poms";

// Add fixture
newPage: async ({ page }, use) => {
  await use(new NewPage(page));
};
```

### Add Network Mocks

**When to mock:** See testing standards doc for when E2E mocking is acceptable (external services with side effects: S3, AI/ML workflows, email/SMS).

**Pattern: Use reusable handlers from `tests/e2e/mocks/handlers/`**

```ts
import { mockS3Upload } from "@tests/e2e/mocks/handlers";

test("creates item with file", async ({ page, newPage }) => {
  await mockS3Upload(page);
  // ... test steps ...
});
```

**For custom mocking needs, create new handlers:**

1. Add handler file in `tests/e2e/mocks/handlers/{domain}.ts`
2. Export async functions taking `Page` parameter
3. Use `route.fallback()` for non-matching methods

```ts
// tests/e2e/mocks/handlers/notifications.ts
import { Page } from "@playwright/test";

export async function mockEmailSend(page: Page): Promise<void> {
  await page.route("**/api/notifications/email", async (route) => {
    if (route.request().method() !== "POST") {
      return route.fallback();
    }
    await route.fulfill({ status: 200, body: "" });
  });
}
```

**When to use inline `page.route()` vs handlers:**

- **Reusable flows**: Use/create handlers
- **One-off test-specific mocks**: Inline in test
- **Complex multi-step flows**: Compose handlers into barrel exports

## Phase 3: Test Generation (playwright-test-generator agent)

### For Each Test in Spec Table

Invoke `playwright-test-generator` agent via Task tool with structured input:

````
Generate Playwright test from spec:

<test-suite>{Spec describe group name from plan}</test-suite>
<test-name>{Test case name from table}</test-name>
<test-file>{File path from spec header, relative to tests/e2e/}</test-file>
<body>
{Steps from table}

Expected behavior:
{Assertions from table}
</body>

Context:
- App: {app name} (frontend/apps/{app}/)
- POM: Use {POMName} class from '../poms'
- Fixtures: Import from '../fixtures/pages.fixture' or '../fixtures/data.fixture'
- Data seeding: Use data fixtures (Request-Response-Recycle pattern)
- API URL: Use ENV.apiURL from '../config/environments'
- Mocking: {list any page.route() mocks needed}
- Standards: A11y-first selectors, no networkidle, POM encapsulation

Example imports:
```ts
import { test, expect } from '../fixtures/pages.fixture';
```
````

### Generator Output

Expect generator to create/append tests to the spec file following:

- Proper imports from per-app fixtures
- describe() block matching test-suite
- test() with name matching test-name
- POM usage instead of raw locators
- A11y-first selectors (getByRole > getByLabel > getByText > getByTestId)
- Assertions using expect()

## Phase 4: Healing Loop (playwright-test-healer agent)

### Run Generated Tests

```bash
cd frontend && pnpm turbo run test:e2e --filter=@ezra/{app}
```

Or filter by spec: `cd frontend/apps/{app} && npx playwright test --grep "{spec pattern}"`

### If Tests Fail

1. **Invoke playwright-test-healer** via Task tool:

```
Heal failing Playwright tests in {spec file path}

App: {app} (frontend/apps/{app}/)

Test failures:
{paste test output}

The healer has Edit/Write access to fix:
- Incorrect locators
- Timing issues (missing waits)
- Assertion failures
- POM method bugs
- Data fixture issues

Context:
- Testing standards: docs/development-guides/testing-standards.md
- Available POMs: {list POM classes}
- Data fixtures: frontend/apps/{app}/tests/e2e/fixtures/data.fixture.ts
- Environment: frontend/apps/{app}/tests/e2e/config/environments.ts
```

2. **Re-run tests** after healer fixes
3. **Iterate** up to 3 times
4. **If still failing after 3 iterations:**
   - Mark test as `test.fixme()` for manual review
   - Or adjust test expectations
   - Ask user to decide

## Phase 5: Refinement & Report

### Verify Testing Standards

Read the generated/healed test file fully and check:

**A11y-first selectors:**

- Use `getByRole('button', { name: 'Submit' })`, `getByLabel('Email')`, `getByText('Welcome')`
- `getByTestId` only as last resort

**POM encapsulation:**

- Use `await featurePage.submitForm()` in specs
- Never use raw `page.getByRole('button').click()` in spec files

**Proper fixture usage:**

- Import from `../fixtures/pages.fixture` or `../fixtures/data.fixture`
- Never instantiate POMs directly in specs

**No deprecated APIs:**

- No `{ waitUntil: 'networkidle' }`
- Use `await page.waitForLoadState('load')` or `await expect(element).toBeVisible()`

**Data seeding (Request-Response-Recycle):**

- Data created via API in fixtures with `crypto.randomUUID()`
- Teardown in try/catch after `await use()`
- `@faker-js/faker` for realistic data (seeded in `@ezra/test-utils/factories/setup`)
- No hardcoded test data strings
- No data created via UI navigation

**Flaky test anti-patterns:**

- No hard-coded waits (`page.waitForTimeout`)
- No dependent tests (each must run independently)
- Use Playwright auto-wait and explicit assertions

**TypeScript verification (MANDATORY — run after every generation):**

Run `pnpm --filter @ezra/{app} check-types` after generating E2E files. Fix ALL TS errors before presenting results. Common issues:
- `protected` properties: BasePage.page MUST be `public` for specs to access it
- Missing type declarations: import `faker` from `@ezra/test-utils/factories/setup`, NOT `@faker-js/faker` (not in app devDeps)
- Unused destructured fixture params: prefix with `_` (e.g., `seededDeal: _seededDeal`) — this is the Playwright pattern for activating a fixture without referencing its value
- `storageState` file doesn't exist at config load time: create `.auth/` dir with empty JSON in global-setup before tests run

**Clerk auth constraints:**

- `@clerk/testing/playwright` does NOT support MFA — test user MUST have MFA disabled
- Use the `storageState` pattern: sign in ONCE in global-setup, save to `.auth/user.json`, reuse via `storageState` in config. NEVER sign in per-test (slow, causes duplicate user DB errors)
- For API seeding in data fixtures: extract Bearer token via `window.Clerk.session.getToken()` after navigating to a page that loads Clerk, then pass as `Authorization: Bearer ${token}` header
- `setupClerkTestingToken({ page })` must be called per-page even with storageState (injects testing token route interceptor for bot detection bypass)

**Port management:**

- Kill stale processes on the E2E API port before running: `lsof -ti:{port} | xargs kill`
- Use unique ports per app (18000 for app, 18001 for deal-triage, etc.) to avoid collisions

**Serial execution:**

- Set `fullyParallel: false` when tests share a single Clerk user + Testcontainers DB — parallel tests cause data races and duplicate user constraint violations

**Env file loading:**

- Credentials load from `.env.e2e` via a `credentials.ts` config module that parses the file on import
- Module load order matters: `credentials.ts` must be imported before `clerkSetup()` runs
- `.env.e2e` is gitignored (`.env.*` pattern); CI sets env vars directly

### Present Summary

Report to user:

```
Generated {N} tests for {Spec Name}
All tests passing
POM changes: {list new/modified POMs}
Data fixtures: {describe any data.fixture.ts modifications}
Page fixtures updated: {list new POM fixtures}

{If any fixme tests:}
Manual review needed:
- {test name}: {reason for fixme}
```

## Data Cleanup Contract

Three safety nets for data cleanup:

### Fixture Teardown (Soft)

Direct DB delete after `await use()` in data fixtures:

```ts
seededDeal: async ({}, use) => {
  const deal = await seedDeal();
  await use(deal);
  await deleteDeal(deal.id);  // direct SQL DELETE
},
```

### Pool Cleanup (global-teardown)

`closePool()` in `global-teardown.ts` closes all `pg` connections before stopping containers:

```ts
import { closePool } from "./db/seed";
async function globalTeardown() {
  await closePool();  // close pg connections first
  // then stop FastAPI, then Postgres container
}
```

### Testcontainers DB Nuke (Hard)

`global-teardown.ts` stops the Testcontainers Postgres container — 100% of orphaned data is destroyed. No complex truncate scripts needed.

## Execution Flow Summary

1. **Parse input** → extract `--app` and spec reference
2. **Read context** → load plan, standards, existing POMs/specs/fixtures for that app
3. **Prepare** → create/extend POM, add data fixtures, register POM fixtures, add mocks
4. **Generate** → invoke playwright-test-generator for each test in spec table
5. **Heal** → run tests, invoke playwright-test-healer if failures, iterate up to 3 times
6. **Refine** → verify standards compliance, apply fixes, report summary

## Notes

- **No auto-commit:** Leave all changes uncommitted for user review (can use `/ezra-commit` separately)
- **Parallel generation:** If spec has multiple independent tests, can invoke multiple generator agents in parallel
- **Incremental approach:** Start with one simple test, verify it passes, then generate the rest
- **Standards trump speed:** Prioritize correct A11y selectors and POM patterns over fast generation
- **App isolation:** Never generate tests that cross app boundaries (e.g., app tests calling example API)
