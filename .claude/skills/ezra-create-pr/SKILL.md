---
name: ezra-create-pr
description: |
  Orchestrate full PR preparation — code review, lint/format/test with auto-healing, documentation review, and PR creation via gh CLI. Use when dev says "prepare PR", "create PR", "submit PR", "PR ready", "open PR", "push PR", "ready for review", "ship it", "send PR", "merge request". Do NOT use for just reviewing code (use ezra-review-code) or just committing (use ezra-commit).
---

# PR Creation Workflow

Orchestrates code review, quality checks, documentation review, and PR creation for the Ezra platform monorepo. Each step requires user confirmation before proceeding.

## Important

- **Always confirm between steps** — never auto-proceed to the next step
- Use `ezra-commit` patterns for all fix commits: conventional commits, no Claude attribution, specific `git add` (never `-A` or `.`)
- Detect affected areas from the diff (`backend/`, `frontend/`, or both) and only run relevant checks
- If on `main`, block and suggest creating a feature branch first
- This is an orchestrator — invoke referenced skills, don't reimplement their logic

## Step 1: Setup & Target Branch

1. Run `git branch --show-current`
   - If on `main`: warn the user and stop. They need to create a branch first.

2. Ask the user: **"Target branch for this PR? (default: main)"**

3. Show the scope of changes:
   ```bash
   git diff <target>...HEAD --stat
   ```

4. Classify affected areas by checking which paths appear in the diff:
   ```bash
   git diff <target>...HEAD --name-only | grep -q '^backend/' && echo "BACKEND"
   git diff <target>...HEAD --name-only | grep -q '^frontend/' && echo "FRONTEND"
   ```

5. Present to the user: current branch, target branch, affected areas (backend/frontend/both), file count. Confirm to proceed.

## Step 2: Code Review

1. Invoke `/ezra-review-code` against the current branch — pass the branch name as the argument so it reviews the diff with the target branch.

2. Display the review results: verdict, necessity, correctness, completeness analysis, and any issues found.

3. If the verdict is APPROVE with no critical issues, note this and ask to proceed.

4. If critical or high issues are found, present them as a numbered list and ask:
   **"Fix all, some (specify numbers), or none?"**

5. For issues the user wants fixed:
   - Apply the fixes directly
   - Stage and commit following `ezra-commit` patterns (use `fix:` prefix for the commit message)
   - Optionally re-run `/ezra-review-code` to verify fixes resolved the issues

6. Confirm to proceed to Step 2b.

## Step 2b: Security Review (conditional)

This step runs only when the diff touches security-sensitive areas. Skip entirely if none of the conditions below match.

**Run `/security-review`** when the diff touches any of:
- Authentication or authorization code (middleware, guards, token handling)
- API endpoints that accept user input (request bodies, query params, file uploads)
- Secret/credential handling (env vars, config files, key management)
- Payment or billing logic
- Database queries built from user input

**Run `/security-scan`** when the diff touches any of:
- `.claude/` directory (skills, hooks, settings, agent definitions, MCP server config)
- `CLAUDE.md` files (could contain prompt injection vectors)

**Process:**
1. Determine which (if any) security skills to run based on the diff
2. If neither applies, skip to Step 3
3. Run the applicable skill(s) and present findings
4. If critical security issues found, present them numbered and ask: **"Fix all, some (specify numbers), or none?"**
5. Apply fixes → commit via `ezra-commit` patterns (`fix:` prefix, scope to `security` e.g. `fix(security): sanitize user input`)
6. Confirm to proceed to Step 3.

## Step 2c: Infrastructure Review (conditional)

This step runs only when the diff touches `infrastructure/` files. Skip entirely otherwise.

**Run when** the diff includes changes to:
- `infrastructure/modules/` (shared Terraform modules)
- `infrastructure/apps/` (app-specific Terraform configs)
- `infrastructure/aws/` (root module composition)

**Process:**
1. Check if terraform changes include any resources with `# forces replacement` or `must be replaced` semantics. Grep the diff for:
   - `health_check_custom_config` on `aws_service_discovery_service` (forces replacement — remove empty blocks)
   - `create_before_destroy` lifecycle rules on stateful resources (ECS services, RDS, service discovery)
   - Any resource being destroyed that has registered instances or active connections

2. If a new app is being added to `infrastructure/apps/`, verify the full deployment chain exists:
   - App module in `infrastructure/apps/<name>/main.tf`
   - Module wired in `infrastructure/aws/main.tf`
   - Change detection filter in `.github/workflows/deploy.yml` (must include both `frontend/apps/<name>/**` AND `infrastructure/apps/<name>/**`)
   - Build step in the `build-frontend` (or `build-backend`) job
   - Deploy job (`deploy-<name>-frontend` or similar)
   - CORS origin added to API module if the app calls the API

3. Present findings and ask to fix before proceeding. Missing CI/CD steps for a new app is a **blocker** — infrastructure without a corresponding build/deploy pipeline means the app will never be deployed.

## Step 3: Lint, Format & Tests

### 3a: Lint & Format

Run lint and format auto-fixers for affected areas.

**Backend (if affected):**
```bash
cd backend && uv run ruff check --fix . && uv run ruff format .
```

**Frontend (if affected):**
```bash
cd frontend && pnpm lint && pnpm format && pnpm check-types
```

If any files changed after auto-fix, stage them with specific `git add` and commit:
```
style: auto-fix lint and format issues
```

If `check-types` (frontend) has errors that can't be auto-fixed, present them to the user and fix before proceeding.

### 3b: Run Tests

When both backend and frontend are affected, run tests **in parallel** using concurrent agents. After both complete, present a unified summary showing pass/fail counts and failure reasons per module:

```
## Test Results Summary
### Backend
- Unit: PASS (42 passed)
- Integration: FAIL — 2 failed (test_create_user_duplicate, test_delete_cascade)
  - Reason: missing factory fixture for UserProfile

### Frontend
- Vitest: PASS (18 passed)
- E2E: FAIL — 1 failed (login-flow.spec.ts)
  - Reason: selector changed after component refactor
```

**Backend commands:**
```bash
cd backend && uv run pytest packages/ -m "not integration" -n auto -v   # unit
cd backend && uv run pytest packages/ -m "integration" -n auto -v        # integration
```

**Frontend commands:**
```bash
cd frontend && pnpm turbo run test   # unit/integration (vitest)
cd frontend && pnpm test:e2e         # e2e (playwright)
```

### 3c: Healing Loop

If tests fail, invoke the appropriate healer agent. Loop up to 3 iterations per test type.

| Failure type | Agent (`subagent_type`) |
|---|---|
| Backend pytest | `pytest-test-healer` |
| Frontend vitest | `vitest-test-healer` |
| Frontend e2e | `playwright-test-healer` |

**Loop logic:**
1. Run tests, capture output
2. If all pass → done
3. If failures → invoke healer agent with the failure output
4. Healer fixes the tests
5. Re-run tests
6. Repeat up to 3 iterations
7. If still failing after 3 → ask user: skip, fix manually, or abort

All test fixes must follow `docs/development-guides/testing-standards.md` patterns (naming conventions, file structure, fixtures, markers).

Commit healer fixes:
```
test: fix failing tests
```

Confirm to proceed to Step 3d.

### 3d: Test Coverage Check

After tests pass, verify the PR actually includes tests for new code. A green suite with no test coverage for new functionality is a false signal.

**Skip this check if** the diff only contains docs, config, skills, or test-only changes.

**Process:**
1. Get new/modified source files from the diff (exclude test files, configs, docs):
   ```bash
   git diff <target>...HEAD --name-only --diff-filter=AM | grep -E '^(backend/packages/.*/src/|frontend/(apps|packages)/.*/src/)' | grep -v '__pycache__'
   ```
2. For each source file, check if a corresponding test file exists:
   - Backend: `src/ezra_api/services/foo.py` → `tests/test_services/test_foo.py`
   - Frontend: `src/components/Foo.tsx` → `tests/unit/Foo.test.tsx` or `tests/unit/Foo.test.ts`
3. Also check if the diff includes any new API routes or pages that warrant e2e coverage — look for new route handlers (`@app.get`, `@app.post`, etc.) or new Next.js page files.
4. Present findings as a numbered list:
   - **Missing unit/integration tests** — source files with no corresponding test file
   - **Missing e2e tests** — new routes/pages with no Playwright spec

5. Ask: **"Generate tests for all, some (specify numbers), or none?"**

6. For approved items, invoke the appropriate skill:
   - Backend source → `/ezra-generate-backend-tests <file-path>`
   - Frontend source → `/ezra-generate-frontend-tests <file-path>`
   - New routes/pages → `/ezra-generate-e2e-tests <file-path>`

7. After generation, re-run the relevant test suite to confirm new tests pass. If failures, enter the healing loop (Step 3c) for the new tests.

8. Commit generated tests:
   ```
   test: add tests for <scope>
   ```

Confirm to proceed to Step 4.

## Step 4: Documentation Review

1. Analyze the full diff (`git diff <target>...HEAD`) for documentation impact:
   - New public APIs or endpoints → README.md or API docs
   - New or changed skills → SKILL.md files
   - Architecture changes → CLAUDE.md files
   - New packages or configuration → relevant README.md
   - Changed CLI commands or workflows → development guides

2. Check existing docs for staleness against the changes.

3. **Cross-reference consistency check** — scan docs touched by the diff and their neighbors for conflicts:
   - **Dangling references**: skill files or docs linking to files/sections that don't exist (e.g., "See `server/prompts.md`" when that file is missing). Use `grep` for relative links and verify targets exist.
   - **Stale lists**: CLAUDE.md files listing packages, domains, or services that no longer match the filesystem (e.g., `domains/ # (core, authentication)` when `mcp` and `llm` also exist). Cross-check listed items against actual directories.
   - **Contradictions**: two docs making conflicting claims about the same thing (e.g., a README saying "uses Django" while CLAUDE.md says "uses FastAPI"). Compare overlapping sections in changed and neighboring docs.
   - **Broken skill references**: skills referencing other skills by name — verify the referenced skill directories and SKILL.md files exist.

4. Present recommendations as a numbered list with specific file paths and what to update. Separate into two groups:
   - **Doc updates needed** (new content prompted by code changes)
   - **Doc consistency fixes** (conflicts, dangling links, stale lists found during cross-reference check)

5. Ask: **"Apply all, some (specify numbers), or none?"**

6. For approved updates, make the changes and commit:
   ```
   docs: update documentation for <scope>
   ```

7. Confirm to proceed to Step 5.

## Step 5: PR Creation

1. Show a summary of all steps completed and the commit log:
   ```bash
   git log <target>..HEAD --oneline
   ```

2. Ask: **"Ready to create PR? Draft or regular?"**

3. If yes:
   - Push the branch: `git push -u origin <branch>`
   - Invoke `/ezra-describe-pr` to generate the PR title and description
   - Present the generated title and description for user review/edit
   - Create the PR:
     ```bash
     gh pr create --title "..." --body "$(cat <<'EOF'
     ...description...
     EOF
     )" --base <target-branch> --repo Ezra-Climate/platform [--draft]
     ```
   - Show the PR URL

4. If the user wants changes to the title or description, adjust and re-create.

## Examples

```
User: create PR
User: prepare PR
User: PR ready for review
User: ship this to main
User: create PR targeting staging
User: open PR against develop
```

## Troubleshooting

| Problem | Solution |
|---|---|
| "no default remote repository" | Run `gh repo set-default Ezra-Climate/platform` |
| Tests timeout on large suite | Skip integration tests with user approval, note in PR |
| Healer loops without progress | Skip after 3 iterations, note skipped tests in PR description |
| On main branch | Create a feature branch before running this skill |
| Lint fixes create merge conflicts | Rebase on target branch first |

## Related Skills

- `/ezra-review-code` — code review only (no PR creation)
- `/ezra-commit` — commit only (no review or PR)
- `/ezra-describe-pr` — PR description generation only
- `/ezra-github-ops` — low-level GitHub API operations
- `/ezra-generate-backend-tests` — generate new backend tests
- `/ezra-generate-frontend-tests` — generate new frontend tests
- `/ezra-generate-e2e-tests` — generate new e2e tests
