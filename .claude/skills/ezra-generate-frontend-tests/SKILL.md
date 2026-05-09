---
name: ezra-generate-frontend-tests
description: Generate Vitest unit and integration tests for frontend packages with automated healing and refinement
model: opus
---

# ezra-generate-frontend-tests

Orchestrates Vitest unit/integration test generation using a 3-agent architecture (planner → generator → healer). Follows testing standards, handles factories/MSW setup, auto-heals failures, and updates catalog. Works across all frontend packages in the Turborepo monorepo.

## Architecture

```
Skill (orchestrator)
  ├─ vitest-test-planner agent     → Creates test plan with infrastructure analysis
  ├─ vitest-test-generator agent   → Generates tests + factories + MSW handlers
  └─ vitest-test-healer agent      → Fixes failing tests + TS errors
```

## Input Format

**With source file path:**

```
/ezra-generate-frontend-tests frontend/packages/design-system/src/components/Button/Button.tsx
/ezra-generate-frontend-tests frontend/packages/hooks/src/queryProvider.tsx
/ezra-generate-frontend-tests frontend/apps/app/src/components/deal/DealCard.tsx
/ezra-generate-frontend-tests frontend/packages/api-client/src/mutators/base.ts
```

**With catalog section reference:**

```
/ezra-generate-frontend-tests stripHtmlTags, stripMarkdown, truncateText
/ezra-generate-frontend-tests text.utils
/ezra-generate-frontend-tests "Tier 1"
```

**With custom file + filter:**

```
/ezra-generate-frontend-tests path/to/specs.md "Section Name"
```

**With inline bullet list:**

```
/ezra-generate-frontend-tests
- stripHtmlTags removes all HTML tags
- truncateText adds ellipsis when truncated
```

**Without params:** Prompt user with catalog sections from default plan.

## Execution Flow

### Step 1: Parse Input & Detect Package

**Parse input mode:**

| Mode | Example | Behavior |
|------|---------|----------|
| No args | `/ezra-generate-frontend-tests` | List catalog sections, prompt user |
| Catalog section | `stripHtmlTags, stripMarkdown` | Read catalog, find matching section |
| Source file | `frontend/packages/hooks/src/useApi.ts` | Ad-hoc mode (will add to catalog after) |
| Custom file + filter | `path/to/specs.md "Section"` | Read file, filter to section |
| Inline text | Pasted bullet list | Parse each line as test case |

**Package Detection** (for source file mode):

Given the source file path, derive:

1. **Package root**: Walk up to find `package.json` with `@ezra/` name
2. **Package name**: Read `name` from that `package.json`
3. **Test dir**: `<package-root>/tests/`
4. **Plan dir**: `<package-root>/tests/plans/`
5. **Catalog**: `<package-root>/tests/plans/test-catalog.md`
6. **Run cmd**: `cd frontend && pnpm --filter <pkg-name> test -- <test-path>`
7. **Typecheck cmd**: `cd frontend && pnpm --filter <pkg-name> check-types`

**Gather context files:**

- `<package-root>/tests/plans/test-catalog.md` - Spec definitions (if exists)
- `docs/development-guides/testing-standards.md` - Testing best practices
- Source file(s) from input

**For ad-hoc mode (source file not in catalog):**

Extract basename without extension for plan filename:
- `src/lib/utils/text.utils.ts` → `text.utils`
- `src/useApi.ts` → `useApi`

### Step 2: Spawn Planner Agent

**Invoke agent:**

```
Task tool:
  subagent_type: vitest-test-planner
  prompt: "Create test plan for {source-file-path}.

          Package root: {package-root}
          Package name: {pkg-name}
          Test dir: {package-root}/tests/

          Source file: {source-file-path}
          Test cases: {test-cases-if-provided}

          CRITICAL — Unit vs Integration Test Boundary:
          IMPORTANT: Do NOT mock TanStack Query hooks (useQuery, useMutation, Orval hooks)
          via vi.mock. Mocking the hook bypasses cache, retries, and state transitions.
          Use MSW to intercept fetch calls in BOTH unit and integration tests.

          Unit tests (tests/unit/): use MSW with one response per test for components/hooks
          that use TanStack Query. Mock child components with complex deps, external modules
          (Clerk, sonner). Cover ALL logic branches, edge cases, error states (HTTP 404/500 via MSW).

          Integration tests (tests/integration/): use MSW to simulate sequences of API calls
          (GET → POST → refetch). Keep real child components. Test multi-step happy-path flows.

          The difference is SCOPE (single component vs component tree), not whether MSW is used.
          Golden rule: if testing logic permutations (even with MSW), it's a unit test.
          If testing multi-step user flows across components, it's an integration test.
          Context: {any-additional-context}

          CRITICAL — Infrastructure discovery (do this FIRST):
          1. Glob for {package-root}/tests/setup.ts and read it — it has global mocks and MSW lifecycle
          2. Glob for {package-root}/tests/utils/** to find renderWithProviders, factories, server
          3. Glob for {package-root}/tests/mocks/handlers/** to find existing custom MSW handlers
          4. Glob for {package-root}/tests/**/*.test.* to see existing test files
          5. Read 1-2 existing tests from same tier as reference
          6. Check if @ezra/api-client/<service> exports exist — these provide Orval-generated
             TanStack Query hooks AND MSW mock handlers (getXxxMockHandler) in the SAME file.
             Prefer generated handlers over hand-written ones for any endpoint that has a spec.
             Generated handlers are in @ezra/api-client/<service>, NOT in a separate .msw.ts file.
          7. For endpoints without Orval handlers (e.g., S3 uploads, download URLs), plan custom
             handlers in {package-root}/tests/mocks/handlers/<name>.ts — NEVER inline in test files.
          8. When planning handler overrides, READ the actual generated TypeScript interface at
             @ezra/api-client/model/<service>/ to verify exact field names before writing.
          Never assume greenfield. Report what infrastructure exists.

          Then: classify tier, analyze infrastructure gaps (factories, MSW handlers),
          find reference tests, and write plan to:
          {package-root}/tests/plans/vitest-plan-{source-name}.md

          FACTORY GAP ANALYSIS: Check for factories for EVERY type that test data
          will include, including nested types. If a generated type from @ezra/api-client/model/<service> exists
          but no factory, flag it as a gap to be created."
```

**Agent output:**

Plan file created at `<package-root>/tests/plans/vitest-plan-{source-name}.md`

### Step 3: Read Plan & Get User Approval

**Read plan file:**

```bash
Read: <package-root>/tests/plans/vitest-plan-{source-name}.md
```

**Present to user:**

```markdown
## Test Plan Created

**Source**: {source-path}
**Package**: {pkg-name}
**Test file**: {test-path}
**Tier**: {tier-number}

### Test Cases ({count})

[List test cases from plan]

### Infrastructure Needs

**Factories**: {list or "None needed"}
**MSW Handlers**: {list or "None needed"}

Proceed with generation?
```

**Wait for user approval before continuing.**

### Step 4: Spawn Generator Agent

**Invoke agent:**

```
Task tool:
  subagent_type: vitest-test-generator
  prompt: "Generate tests from plan at {package-root}/tests/plans/vitest-plan-{source-name}.md.

          Package root: {package-root}
          Package name: {pkg-name}

          Create:
          1. Missing factories (if needed)
          2. Missing MSW handlers (if needed, Tier 5 only)
          3. Test file following tier-specific patterns
          4. Update barrel exports for factories/handlers

          FACTORY USAGE RULE: Use @faker-js/faker for test data, typed against generated models.
          - Check {package-root}/tests/utils/factories/ for existing factories first
          - If no factory exists, CREATE one using @faker-js/faker + types from @ezra/api-client/model/<service>
          - Use factory.create({...overrides}) instead of inline object literals
          - For MSW handlers: prefer Orval-generated handlers from @ezra/api-client/<service> (getXxxMockHandler)
          - Only write custom MSW handlers for non-standard scenarios

          MSW HANDLER PLACEMENT RULE: NEVER inline custom http.get/http.post/etc handlers directly in test files.
          - Custom handlers MUST be placed in {package-root}/tests/mocks/handlers/<name>.ts
          - Export handler arrays (e.g., `export const dealDownloadHandlers = [...]`)
          - Add barrel export to {package-root}/tests/mocks/handlers/index.ts
          - Import and spread in test files: `...dealDownloadHandlers`
          - Only Orval-generated handlers and per-test server.use() overrides belong directly in test files

          TYPE ACCURACY RULE: When passing override objects to Orval-generated mock handlers,
          ALWAYS read the actual generated TypeScript interface first to verify field names.
          Never guess field names — e.g., `UnreadCountResponse` has `count`, not `unread_count`.
          Read the type definition at @ezra/api-client/model/<service>/ before writing overrides.

          Follow all conventions from testing standards."
```

### Step 5: Run Tests

**Command:**

```bash
cd frontend && pnpm --filter <pkg-name> test -- <test-path>
```

**Parse output:**
- Count passing tests
- Identify failing tests
- Capture error messages

### Step 6: Spawn Healer Agent (If Failures)

If tests fail, invoke healer up to 3 times total:

**Invoke agent:**

```
Task tool:
  subagent_type: vitest-test-healer
  prompt: "Fix failing tests in {test-file-path}.

          Package root: {package-root}
          Package name: {pkg-name}
          Run tests: cd frontend && pnpm --filter {pkg-name} test -- {test-path}
          Typecheck: cd frontend && pnpm --filter {pkg-name} check-types

          Run tests, classify errors, apply fixes iteratively.
          After tests pass, run TypeScript check on generated files.

          Iterate up to 3 times. On iteration 3, escalate to user with options."
```

**If healer escalates:**

Present options to user, get guidance, pass back to healer or handle in skill.

**Repeat healing up to 3 times** if initial fixes don't resolve all issues.

### Step 7: Refinement Pass

**Check generated test file(s) against standards checklist:**

- Explicit vitest imports (no global test/expect)
- A11y-first selectors (role > label > text > testid)
- Test isolation (no `test.only`, no inter-test dependencies)
- No `any` types
- No `// @ts-ignore` (use `// @ts-expect-error` with explanation if needed)
- No hardcoded timeouts (use `waitFor`)
- Cleanup in `beforeEach`/`afterEach`
- `@/` alias for source imports
- `@tests/` alias for test utility imports
- No `as any` type assertions

**For each violation found:**

1. Read test file
2. Apply Edit tool to fix
3. Re-run tests to ensure no breakage

**Note:** Refinement only touches test files, not shared infrastructure.

### Step 8: Regression Check

**Run full package test suite:**

```bash
cd frontend && pnpm --filter <pkg-name> test
```

**If existing tests break:**

1. Check MSW handler ordering (nested routes before generic)
2. Check factory conflicts (overlapping mocks)
3. Check global setup changes

**If unfixable without modifying existing tests:**

Present problem to user and ask for guidance before modifying existing tests.

### Step 9: Update Catalog & Summary Report

**Update test-catalog.md:**

**If input came from catalog:**

Mark section as completed:

```markdown
### stripHtmlTags, stripMarkdown, truncateText ✅

**Status**: Completed
**Test file**: `tests/unit/lib/utils/text.utils.test.ts`
...
```

**If ad-hoc input (not from catalog):**

Auto-append new entry to `<package-root>/tests/plans/test-catalog.md`:

```markdown
### [Function/Component Names]

**Source**: `src/...`
**Test file**: `tests/...`
**Priority**: [inferred] | **Effort**: [inferred]

**Test cases**:
1. [Generated test case 1]
2. [Generated test case 2]
...

**Setup notes**: [Factories used, mocks, etc.]
```

**Present summary report to user:**

```markdown
✅ Generated N test files:
- {test-file-path} ({test-count} cases, passing)

✅ Infrastructure created:
- {factory-files}
- {handler-files}

✅ Catalog updated:
- Marked "{section-name}" as done
- Or: Added new entry for "{source-name}"

✅ Regression: All M existing tests passing

✅ TypeScript: No type errors in generated files

TypeScript suppressions (if any):
- {file:line} // @ts-expect-error {reason}

⚠️ Skipped (if any):
- {test-name}: {reason with TODO comment}
```

**No auto-commit.** Suggest `/ezra-commit` separately.

## Key Resources

| Resource | Path | Purpose |
|----------|------|---------|
| Test catalog | `<package-root>/tests/plans/test-catalog.md` | Spec definitions & tiers |
| Testing standards | `docs/development-guides/testing-standards.md` | Best practices |
| Factory index | `<package-root>/tests/utils/factories/index.ts` | Existing factories |
| MSW handlers index | `<package-root>/tests/mocks/handlers/index.ts` | API mocks |
| Plan files | `<package-root>/tests/plans/vitest-plan-*.md` | Generated test plans (gitignored) |
| Shared setup | `@ezra/test-utils/setup` | Global test setup (jest-dom, cleanup, mocks) |
| Shared render | `@ezra/test-utils/render` | renderWithProviders (Theme + QueryClient wrapper) |
| Shared renderHook | `@ezra/test-utils/renderHook` | renderHookWithProviders (Theme + QueryClient) |
| Shared providers | `@ezra/test-utils/allProviders` | AllProviders component (Theme + QueryClient) |
| Shared QueryClient | `@ezra/test-utils/testQueryClient` | createTestQueryClient (retry:false, gcTime:0) |
| Shared MSW factory | `@ezra/test-utils/server` | createMswServer(handlers) |
| Generated API hooks | `@ezra/api-client/<service>` | Orval-generated TanStack Query hooks + MSW handlers |
| Generated types | `@ezra/api-client/model/<service>` | Orval-generated TypeScript interfaces from Pydantic |

## Agent Responsibilities

### vitest-test-planner

- Detects package from source file path
- Reads source file(s)
- Classifies tier (1-5)
- Determines test file path (package-relative)
- Analyzes infrastructure gaps (factories, MSW handlers)
- Finds 1-2 reference tests from same tier within the package
- Writes plan to `<package-root>/tests/plans/vitest-plan-{source-name}.md`

### vitest-test-generator

- Reads test plan
- Creates missing factories at `<package-root>/tests/utils/factories/`
- Creates missing MSW handlers at `<package-root>/tests/mocks/handlers/` (Tier 5 only) — NEVER inline custom handlers in test files
- Updates barrel exports (factories + handlers)
- Reads generated type definitions before passing overrides to Orval mock handlers (verify exact field names)
- Generates test file following tier-specific patterns
- Follows all testing conventions

### vitest-test-healer

- Runs tests: `cd frontend && pnpm --filter <pkg-name> test -- <test-path>`
- Classifies failures (7 error types)
- Applies targeted fixes iteratively (up to 3 attempts)
- Runs TypeScript check: `cd frontend && pnpm --filter <pkg-name> check-types`
- Fixes TS errors using error code table (12 codes)
- Escalates to user on iteration 3 with options

## Notes

- **Plan file lifecycle**: Plans are gitignored, created per source file, read by skill after planner
- **Filename convention**: `vitest-plan-{source-name}.md` where source-name is basename without extension
- **Agent isolation**: Each agent has focused responsibility, skill orchestrates
- **Refinement in skill**: Checklist-driven refinement stays in skill (not delegated to healer)
- **Healing iterations**: Up to 3 healer invocations if issues persist
- **No auto-commit**: Leave changes uncommitted for user review
- **Catalog maintenance**: Keep catalog updated with completion status and new entries
- **Package-relative paths**: All test infrastructure is relative to the package root, not the monorepo root
