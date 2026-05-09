---
name: github-actions-workflows
description: >
  GitHub Actions CI/CD workflow authoring and debugging for the Ezra monorepo.
  Always use this skill when touching .github/workflows/ files, debugging CI
  failures, adding services to CI, or discussing GitHub Actions in any way —
  even for small changes like fixing a failing check or adding a new step.
  Also use when setting up path-based change detection, caching, release
  workflows, workflow_dispatch triggers, approval gates, environments,
  matrix strategies, reusable workflows, composite actions, or Slack
  notifications for CI. If the user mentions "CI", "pipeline", "workflow",
  "deploy workflow", "GitHub Actions", or "actions YAML", this skill applies.
origin: Ezra
---

# GitHub Actions Workflows

CI/CD workflow authoring and debugging for the Ezra multi-server, multi-client monorepo.

## When to Activate

- Creating or modifying `.github/workflows/` files
- Debugging CI failures or flaky workflows
- Adding new services or apps to CI pipelines
- Setting up path-based change detection for monorepo
- Configuring caching for uv, pnpm, Turbo, or Docker
- Creating release workflows or manual dispatch triggers
- Setting up GitHub environments with approval gates

**Do NOT use for:** Docker image design (`docker-patterns`), deployment strategy selection (`deployment-patterns`), Turborepo task config (`turborepo`), Terraform module design.

## First Reads

Always read these before authoring or debugging workflows:

- `.github/workflows/backend-tests.yml` — Python lint/test, Postgres service
- `.github/workflows/frontend-tests.yml` — Node lint/typecheck/test, codegen drift
- `.github/workflows/deploy.yml` — Docker build → ECR → ECS, path-based change detection
- `.github/workflows/e2e-tests.yml` — Playwright + Testcontainers integration
- `.github/workflows/terraform.yml` — TF plan/apply with OIDC
- `backend/compose.yml` — service container parity reference
- `frontend/apps/app/tests/e2e/global-setup.ts` — Testcontainers pattern

## Core Rules

1. **Action SHA pinning**: pin third-party actions by full SHA, not just tag — tags are mutable and vulnerable to supply chain attacks. Official GitHub actions (`actions/*`, `aws-actions/*`) may use `@v4` tags.

```yaml
# Third-party — pin by SHA
- uses: dorny/paths-filter@de90cc6fb38fc0963ad72b210f1f284cd68cea36  # v3.0.2

# Official GitHub — tag is acceptable
- uses: actions/checkout@v4
```

2. **`persist-credentials: false`**: on `actions/checkout` in workflows that don't need git push — prevents the token from leaking to subsequent steps

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
```

3. **`working-directory`**: EVERY `run` step must specify `working-directory: backend` or `working-directory: frontend` — the repo root is never the working directory for any tool
4. **Frozen installs**: `pnpm install --frozen-lockfile` (frontend), `uv sync --frozen` (backend) in all CI jobs
5. **`if: always()`**: required on artifact upload steps so reports upload even when tests fail
6. **`permissions`**: always explicit, least privilege — never rely on defaults. Start with `permissions: {}` (no permissions) and add only what's needed.
7. **`timeout-minutes`**: set on ALL jobs — tests (10), E2E (15), deploys (10), terraform (10). Prevents stuck jobs from consuming runner minutes.
8. **Postgres 17**: standard version across compose, E2E Testcontainers, and CI service containers
9. **`concurrency`**: always set on deploy and long-running workflows to prevent parallel execution

## Concurrency Controls

Prevent parallel deploys and duplicate CI runs:

```yaml
# Deploy workflows — one deploy per service at a time
concurrency:
  group: deploy-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false  # NEVER cancel in-progress deploys

# Test workflows — cancel previous runs on same PR
concurrency:
  group: test-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true  # Safe to cancel superseded test runs

# Terraform — one plan/apply at a time
concurrency:
  group: terraform-production
  cancel-in-progress: false
```

Rules:
- **Deploy/Terraform**: `cancel-in-progress: false` — never cancel a running deployment
- **Tests**: `cancel-in-progress: true` — cancel outdated runs to save runner minutes
- **Group key**: include `github.ref` to allow parallel runs on different branches

## Security Hardening

### Fork and PR Safety

Never use `pull_request_target` unless absolutely necessary — it runs with write permissions on fork PRs:

```yaml
# SAFE: pull_request runs in fork context with read-only permissions
on:
  pull_request:
    paths: ['backend/**']

# DANGEROUS: pull_request_target runs with base repo permissions
# Only use when you MUST write (e.g., PR labels) and NEVER checkout PR code
on:
  pull_request_target:
    types: [opened]
```

If you must use `pull_request_target`:
- NEVER checkout the PR head (`ref: ${{ github.event.pull_request.head.sha }}`)
- Only use it for metadata operations (labels, comments)
- Keep the job minimal with `permissions: { pull-requests: write }` only

### Workflow File Protection

Changes to `.github/workflows/` and `.github/actions/` should require CODEOWNERS review:

```
# .github/CODEOWNERS
/.github/workflows/ @Ezra-Climate/platform-leads
/.github/actions/   @Ezra-Climate/platform-leads
```

### Secret Hygiene

- Never echo or log secrets — use `::add-mask::` to redact values that pass through steps
- Always `jq -r` with explicit field access when parsing Secrets Manager responses (never dump full JSON)
- Use `environment` protection to scope secrets to specific environments (staging/production)

## Monorepo Path Filtering

### Pattern 1: Native `paths:` — skip entire workflow

Use for test workflows where all jobs share the same trigger scope.

```yaml
on:
  push:
    branches: [main]
    paths: ['backend/**']
  pull_request:
    paths: ['backend/**']
```

### Pattern 2: `dorny/paths-filter@v3` — conditional job execution

Use when a single workflow must conditionally run different jobs based on which subdirectories changed.

```yaml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      deal-triage-frontend: ${{ steps.filter.outputs.deal-triage-frontend }}
      deal-triage-worker: ${{ steps.filter.outputs.deal-triage-worker }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@de90cc6fb38fc0963ad72b210f1f284cd68cea36  # v3.0.2
        id: filter
        with:
          filters: |
            api:
              - 'backend/packages/apps/api/**'
              - 'backend/packages/domains/**'
              - 'backend/pyproject.toml'
              - 'backend/uv.lock'
            deal-triage-frontend:
              - 'frontend/apps/deal-triage/**'
              - 'frontend/packages/**'
              - 'frontend/pnpm-lock.yaml'

  deploy-api:
    needs: detect-changes
    if: needs.detect-changes.outputs.api == 'true'
    # ...
```

### Dependency Map

Which paths trigger which workflows — shared deps MUST appear in every filter that depends on them:

```
backend/packages/apps/api/**              → backend-tests, deploy-api
backend/packages/apps/worker/**           → backend-tests, deploy-deal-triage-worker
backend/packages/apps/document-investigation/** → backend-tests (not yet deployed)
backend/packages/domains/**               → backend-tests, deploy-api, deploy-worker
backend/pyproject.toml, backend/uv.lock   → all backend jobs
frontend/apps/app/**                      → frontend-tests, e2e-tests
frontend/apps/deal-triage/**              → frontend-tests, deploy-deal-triage-frontend
frontend/packages/**                      → frontend-tests, deploy-deal-triage-frontend, e2e-tests
frontend/pnpm-lock.yaml                   → all frontend jobs
infrastructure/aws/**                     → terraform (excluding bootstrap/, local/)
```

## Service Containers

### Postgres

```yaml
services:
  postgres:
    image: postgres:17
    env:
      POSTGRES_USER: ezra
      POSTGRES_PASSWORD: ezra
      POSTGRES_DB: ezra
    ports: ['5432:5432']
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### Redis

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ['6379:6379']
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

### MiniStack (S3, SQS, Secrets Manager)

Use when backend integration tests need AWS services. The worker uses aiobotocore SQS poller (not Celery/Temporal) — no Temporal container needed.

```yaml
services:
  ministack:
    image: nahuelnucera/ministack:1.1.12
    ports: ['4566:4566']
    options: >-
      --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:4566/_ministack/health')\""
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

Environment variables for MiniStack connectivity:

```yaml
env:
  AWS_ENDPOINT_URL: http://localhost:4566
  AWS_DEFAULT_REGION: us-east-1
  AWS_ACCESS_KEY_ID: test
  AWS_SECRET_ACCESS_KEY: test
```

### Testcontainers (E2E — programmatic)

E2E tests use `@testcontainers/postgresql` and optionally `testcontainers` `GenericContainer` (for MiniStack) in `global-setup.ts`. These are spun up programmatically, NOT via GitHub Actions service containers:

1. Postgres 17-alpine via Testcontainers (random port)
2. Alembic migrations via `uv run alembic upgrade head`
3. FastAPI on fixed port 18000
4. Next.js webServer on port 3000
5. MiniStack ready to enable (currently commented out in global-setup.ts)

See `frontend/apps/app/tests/e2e/global-setup.ts` for the full pattern.

## Caching Patterns

```yaml
# uv (backend) — setup-uv handles caching automatically
# Pin version for reproducibility (don't use "latest" in CI)
- uses: astral-sh/setup-uv@v4
  with:
    version: "0.10.11"

# pnpm + node (frontend)
- uses: pnpm/action-setup@v4
  with:
    package_json_file: frontend/package.json
- uses: actions/setup-node@v4
  with:
    node-version: '22'
    cache: 'pnpm'
    cache-dependency-path: 'frontend/pnpm-lock.yaml'

# Turbo cache (frontend CI)
- uses: actions/cache@v4
  with:
    path: frontend/.turbo
    key: turbo-${{ runner.os }}-${{ hashFiles('frontend/**/turbo.json', 'frontend/pnpm-lock.yaml') }}
    restore-keys: turbo-${{ runner.os }}-

# Docker layer cache (deploy builds) — use GitHub Actions cache backend
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v6
  with:
    context: backend
    file: backend/packages/apps/api/Dockerfile
    push: true
    tags: ${{ steps.ecr.outputs.registry }}/${{ vars.ECR_REPO_API }}:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

Docker layer cache uses GitHub Actions cache backend (`type=gha`) — no external registry needed. Requires `docker/setup-buildx-action` for BuildKit support.

## Secrets and AWS OIDC

- **`vars.*`** for non-sensitive config: role ARNs, cluster names, ECR repo names
- **AWS Secrets Manager** for sensitive values: fetched at runtime in workflow steps (see `deploy.yml` Clerk key fetch)
- **OIDC** for AWS auth — no long-lived access keys:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
      aws-region: us-east-2

  - uses: aws-actions/amazon-ecr-login@v2
    id: ecr
```

- **`NEXT_PUBLIC_*`** must be passed as `--build-arg` in Docker builds (Next.js inlines at build time):

```yaml
- name: Build frontend image
  run: |
    docker build \
      --build-arg NEXT_PUBLIC_API_URL=https://api.ezra.deals \
      --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${{ steps.secrets.outputs.clerk_pk }} \
      -f apps/deal-triage/Dockerfile .
```

## Matrix Strategies

Use matrix builds to test across multiple configurations:

```yaml
jobs:
  test:
    strategy:
      fail-fast: false  # Don't cancel other matrix jobs on first failure
      matrix:
        python-version: ['3.12', '3.13']
        # Or for frontend:
        # node-version: ['22', '24']
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
```

### Monorepo Matrix — test multiple packages in parallel

```yaml
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        package:
          - { name: 'api', path: 'backend/packages/apps/api' }
          - { name: 'worker', path: 'backend/packages/apps/worker' }
          - { name: 'deals', path: 'backend/packages/domains/deals' }
    runs-on: ubuntu-latest
    steps:
      - name: Run tests for ${{ matrix.package.name }}
        working-directory: backend
        run: uv run pytest ${{ matrix.package.path }} -v
```

Rules:
- Always use `fail-fast: false` — seeing all failures is more useful than cancelling early
- Use `include` for environment-specific config (e.g., different DB URLs per matrix entry)
- Use `exclude` sparingly — prefer explicit `include` for clarity

## Failure Notifications

Notify on deploy failures or critical CI breakage:

```yaml
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@485727b3e97e4f09be51e1a16e7401c3752c64a2  # v2.1.0
  with:
    webhook: ${{ secrets.SLACK_DEPLOY_WEBHOOK }}
    webhook-type: incoming-webhook
    payload: |
      {
        "text": ":red_circle: ${{ github.workflow }} failed on ${{ github.ref_name }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*${{ github.workflow }}* failed\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View run>"
            }
          }
        ]
      }
```

Rules:
- Use `if: failure()` — only notify on failure, not every run
- Deploy workflows: always notify on failure
- Test workflows: only notify on `main` branch failures (not PR failures)
- Include run link for quick access to logs

## `workflow_dispatch` and Manual Triggers

Pattern for ad-hoc deploys or rollbacks:

```yaml
on:
  workflow_dispatch:
    inputs:
      service:
        description: 'Service to deploy'
        required: true
        type: choice
        options: [api, deal-triage-frontend, deal-triage-worker]
      image_tag:
        description: 'Image tag (default: latest)'
        required: false
        default: 'latest'
        type: string
      confirm_rollback:
        description: 'Confirm rollback (type YES to proceed)'
        required: false
        type: string
```

## GitHub Environments and Approval Gates

Pattern for staging → production promotion:

```yaml
jobs:
  deploy-staging:
    environment: staging
    # ... deploys to staging

  deploy-production:
    needs: deploy-staging
    environment:
      name: production
      url: https://api.ezra.deals
    # GitHub environment protection rules enforce:
    # - Required reviewers
    # - Wait timer (optional)
    # - Deployment branches (main only)
```

Environment protection rules are configured in GitHub repo settings, not in YAML.

## Runner Environment

`ubuntu-latest` now points to **Ubuntu 24.04** (changed late 2024). Be aware:
- Some system packages differ from 22.04 — test workflows after upgrading
- If you need a specific Ubuntu version, pin explicitly: `runs-on: ubuntu-24.04` or `ubuntu-22.04`
- Custom runner images are now GA (March 2026) — use for pre-baked deps if startup time is critical
- OIDC tokens now include repository custom properties (March 2026) — useful for fine-grained IAM policies

## Performance Optimization

### Checkout Optimization

Shallow clone by default — full git history is rarely needed:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 1          # Shallow clone (default, but be explicit)
    persist-credentials: false
```

Use `fetch-depth: 0` only when you need git history (e.g., changelog generation, `dorny/paths-filter` on push events). For PRs, `paths-filter` works with `fetch-depth: 1`.

### Turbo `--affected` — only test changed packages

Instead of running all tests, use Turbo's affected filter to test only packages that changed:

```yaml
# PR test workflow — only test affected packages
- name: Test affected packages
  working-directory: frontend
  run: pnpm turbo run test --affected

# Main branch — test everything (safety net)
- name: Test all packages
  working-directory: frontend
  run: pnpm turbo run test
```

Rules:
- Use `--affected` on PR workflows for speed
- Always run full test suite on `main` pushes as a safety net
- `--affected` compares against the merge base automatically

### Parallel Test Sharding

Split large test suites across matrix jobs for faster feedback:

```yaml
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      # Backend — pytest-split for time-based sharding
      - name: Run tests (shard ${{ matrix.shard }}/4)
        working-directory: backend
        run: uv run pytest packages/ --splits 4 --group ${{ matrix.shard }}

      # Frontend — Vitest sharding
      - name: Run tests (shard ${{ matrix.shard }}/4)
        working-directory: frontend
        run: pnpm turbo run test -- --shard=${{ matrix.shard }}/4

      # E2E — Playwright sharding
      - name: Run E2E (shard ${{ matrix.shard }}/4)
        working-directory: frontend
        run: pnpm turbo run test:e2e --filter=@ezra/app -- --shard=${{ matrix.shard }}/4
```

Sharding is worth it when test suites exceed ~3 minutes. Below that, the job startup overhead negates the benefit.

### Job Structure Optimization

**Combine small steps, split heavy ones:**

```yaml
# BAD: separate jobs for lint + typecheck + test (3x checkout + install overhead)
jobs:
  lint:
    steps: [checkout, install, lint]
  typecheck:
    steps: [checkout, install, typecheck]
  test:
    steps: [checkout, install, test]

# GOOD: one job for fast checks, separate job for slow tests
jobs:
  checks:
    steps: [checkout, install, lint, typecheck, codegen-drift]  # ~1 min total
  test:
    steps: [checkout, install, test]  # ~3 min, benefits from full resources
```

Rules:
- Lint + typecheck + format: combine into one job (each is <30s)
- Tests: separate job (benefits from full runner resources)
- Deploy: always separate job with `needs:` dependency
- E2E: always separate job (heavy, needs service containers)

### Larger Runners

Use larger runners for Docker builds and E2E tests:

```yaml
jobs:
  # Standard: 2 vCPU, 7 GB RAM — fine for lint/test
  test:
    runs-on: ubuntu-latest

  # Large: 4 vCPU, 16 GB RAM — use for Docker builds, E2E
  deploy:
    runs-on: ubuntu-latest-4-cores  # GitHub-hosted larger runner

  # Or use labels for self-hosted
  build:
    runs-on: [self-hosted, linux, large]
```

Note: larger runners cost more per minute. Only use for jobs where build time savings offset the cost (Docker builds, E2E suites, Playwright with multiple browsers).

### Cache Warming

Pre-warm caches on `main` so PR workflows hit cache immediately:

```yaml
# Runs on main push — warms caches for PR workflows
name: Cache Warm
on:
  push:
    branches: [main]
jobs:
  warm:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4       # Warms uv cache
      - uses: pnpm/action-setup@v4
        with:
          package_json_file: frontend/package.json
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'
          cache-dependency-path: 'frontend/pnpm-lock.yaml'
      - run: uv sync --frozen
        working-directory: backend
      - run: pnpm install --frozen-lockfile
        working-directory: frontend
```

This is usually unnecessary — the regular `main` push workflows already warm caches. Only add a dedicated warm job if PRs frequently miss cache (e.g., after lockfile changes).

### Conditional Step Execution

Skip expensive steps when they can't produce different results:

```yaml
# Skip Playwright browser install if no E2E files changed
- name: Check for E2E changes
  id: e2e-check
  run: |
    if git diff --name-only origin/main...HEAD | grep -q 'tests/e2e/'; then
      echo "changed=true" >> "$GITHUB_OUTPUT"
    else
      echo "changed=false" >> "$GITHUB_OUTPUT"
    fi

- name: Install Playwright browsers
  if: steps.e2e-check.outputs.changed == 'true'
  run: pnpm --filter @ezra/app exec playwright install chromium --with-deps
```

## Reusable Workflows and Composite Actions

### Reusable ECS Deploy Workflow

Extract repeated deploy jobs (3 copies in `deploy.yml`) into a reusable workflow:

```yaml
# .github/workflows/reusable-deploy-ecs.yml
name: Deploy to ECS (reusable)
on:
  workflow_call:
    inputs:
      service-name:
        required: true
        type: string
      ecr-repo:
        required: true
        type: string
      dockerfile:
        required: true
        type: string
      build-context:
        required: true
        type: string
      build-args:
        required: false
        type: string
        default: ''

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: us-east-2
      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr
      - name: Build and push
        working-directory: ${{ inputs.build-context }}
        run: |
          docker build \
            -t ${{ steps.ecr.outputs.registry }}/${{ inputs.ecr-repo }}:${{ github.sha }} \
            -t ${{ steps.ecr.outputs.registry }}/${{ inputs.ecr-repo }}:latest \
            ${{ inputs.build-args }} \
            -f ${{ inputs.dockerfile }} .
          docker push ${{ steps.ecr.outputs.registry }}/${{ inputs.ecr-repo }} --all-tags
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster ${{ vars.ECS_CLUSTER }} \
            --service ${{ inputs.service-name }} \
            --force-new-deployment
```

### Composite Action for Shared Setup

```yaml
# .github/actions/setup-frontend/action.yml
name: Setup Frontend
description: Install pnpm, Node.js, and frontend dependencies
runs:
  using: composite
  steps:
    - uses: pnpm/action-setup@v4
      with:
        package_json_file: frontend/package.json
    - uses: actions/setup-node@v4
      with:
        node-version: '22'
        cache: 'pnpm'
        cache-dependency-path: 'frontend/pnpm-lock.yaml'
    - name: Install dependencies
      working-directory: frontend
      shell: bash
      run: pnpm install --frozen-lockfile
```

## Release Automation

Tag-based channel detection for alpha/beta/stable releases:

```yaml
on:
  push:
    tags: ['v*']

jobs:
  determine-version:
    runs-on: ubuntu-latest
    outputs:
      channel: ${{ steps.parse.outputs.channel }}
      version: ${{ steps.parse.outputs.version }}
    steps:
      - id: parse
        run: |
          TAG="${GITHUB_REF#refs/tags/v}"
          if [[ "$TAG" == *"-alpha"* ]]; then
            echo "channel=alpha" >> "$GITHUB_OUTPUT"
          elif [[ "$TAG" == *"-beta"* ]]; then
            echo "channel=beta" >> "$GITHUB_OUTPUT"
          else
            echo "channel=stable" >> "$GITHUB_OUTPUT"
          fi
          echo "version=$TAG" >> "$GITHUB_OUTPUT"

  deploy:
    needs: determine-version
    uses: ./.github/workflows/reusable-deploy-ecs.yml
    # Route to environment based on channel
```

## Debugging Workflows

### Commands

```bash
gh run view <id> --log-failed    # View failed step logs
gh run list --workflow=<name>    # List recent runs
gh run rerun <id> --failed       # Rerun only failed jobs
gh run watch <id>                # Watch a run in progress
```

### Common Failures in This Repo

| Failure | Cause | Fix |
|---------|-------|-----|
| `uv sync` fails | Lockfile out of sync | Run `uv lock` locally, commit `uv.lock` |
| `pnpm install --frozen-lockfile` fails | `pnpm-lock.yaml` out of sync | Run `pnpm install`, commit lockfile |
| Codegen drift check fails | API specs changed, generated code stale | Run `pnpm --filter @ezra/api-client generate`, commit |
| Postgres service unhealthy | Image version mismatch or slow start | Check `postgres:17`, increase `--health-retries` |
| `docker push` permission denied | OIDC role missing `ecr:PutImage` | Check IAM policy on deploy role |
| Terraform state lock | Another plan/apply running | Wait or `terraform force-unlock <id>` |
| Playwright timeout | Backend didn't start in time | Check `uv sync` output, port 18000 conflicts |

### Enable Debug Logging

Set `ACTIONS_STEP_DEBUG=true` as a repository secret for verbose step output.

### Local Testing with `act`

```bash
act -j test --container-architecture linux/amd64
```

Limitations: no OIDC support, service containers behave differently, secrets must be passed via `.secrets` file.

## Anti-Patterns

### Security

1. **Pinning third-party actions by tag only** — tags are mutable; pin by SHA for supply chain safety. Only official `actions/*` may use tags.
2. **Using `pull_request_target` with checkout of PR head** — gives fork PRs write access to your repo; use `pull_request` for code checkout
3. **Leaving `persist-credentials: true`** (default) — token persists in `.git/config` and can leak to subsequent steps; set `false` when git push isn't needed
4. **Hardcoding secrets in YAML** — fetch from AWS Secrets Manager at runtime; use `vars.*` only for non-sensitive config
5. **Missing `::add-mask::`** — always mask secret values before writing to `GITHUB_OUTPUT`

### Monorepo

6. **Forgetting shared deps in path filters** — `domains/**`, `pyproject.toml`, `uv.lock` must appear in EVERY backend filter group
7. **Using `paths:` when you need conditional jobs** — native `paths:` skips the entire workflow; use `dorny/paths-filter` for per-job conditionals
8. **Omitting `working-directory`** — every `run` step must specify `backend` or `frontend`

### CI Reliability

9. **Missing concurrency groups on deploy workflows** — parallel deploys cause race conditions; always set `concurrency` with `cancel-in-progress: false`
10. **Wrong Postgres version** — standard is 17; always use `postgres:17`
11. **Missing `--build-arg` for `NEXT_PUBLIC_*`** — Next.js inlines at build time; omitting produces empty values in production
12. **Missing `--frozen-lockfile` / `--frozen`** — CI must never modify lockfiles
13. **Missing `if: always()` on artifact uploads** — reports won't upload when tests fail
14. **Missing `timeout-minutes`** — stuck jobs consume runner minutes indefinitely
15. **Using Docker Compose in CI** — CI uses service containers and direct tool invocation; compose is for local dev only
16. **Running `terraform apply` on PR events** — apply only on protected branches; PRs should only run `plan`

## Done Checklist

Before completing a workflow authoring or debugging task:

### Security
- [ ] Third-party actions pinned by SHA (not just tag)
- [ ] `persist-credentials: false` on checkout (unless git push needed)
- [ ] `permissions` block is explicit and least-privilege
- [ ] Secrets fetched from Secrets Manager, not hardcoded
- [ ] Secret values masked with `::add-mask::` before output
- [ ] No `pull_request_target` with PR head checkout

### Monorepo
- [ ] Every `run` step has `working-directory`
- [ ] Path filters include all shared dependencies
- [ ] `NEXT_PUBLIC_*` passed as `--build-arg` in Docker builds

### Reliability
- [ ] `concurrency` group set (cancel-in-progress: false for deploys, true for tests)
- [ ] `timeout-minutes` set on all jobs
- [ ] Dependency installs use `--frozen-lockfile` or `--frozen`
- [ ] Artifact uploads use `if: always()`
- [ ] Deploy failures notify Slack
- [ ] Tested with `act` locally or verified via PR workflow run
