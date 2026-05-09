---
name: ezra-scaffold-app
description: Scaffold a new frontend or backend app in the Ezra platform monorepo. Use when creating a new Next.js frontend app or FastAPI backend app, when user says "add app", "new app", "scaffold app", "create app", or "new service". Handles all registration points — workspace, Docker Compose, Dockerfile, CI/CD, infrastructure stubs.
---

# ezra-scaffold-app

Scaffolds a new app (frontend or backend) in the Ezra platform monorepo, creating all required files and registering the app across all integration points.

## Input Format

```
/ezra-scaffold-app backend billing --port 8002
/ezra-scaffold-app frontend billing --port 3003
/ezra-scaffold-app backend billing --port 8002 --type worker
```

**Parameters:**
- `side` (required): `backend` or `frontend`
- `name` (required): app name in kebab-case (e.g., `billing`, `risk-engine`)
- `--port` (required): the port the app listens on
- `--type` (backend only, optional): `api` (default) or `worker` (Temporal worker, no HTTP)
- `--no-auth` (backend only, optional): skip authentication setup. **By default, all backend API apps include Clerk JWT authentication.** Only omit auth when explicitly instructed by the user.
- `--auth` (frontend only, optional): `clerk` to include Clerk auth setup, omitted for no auth
- `--backend-port` (frontend only, optional): the backend API port this frontend talks to (default: 8000)

## Authentication Default

**All backend API apps that expose data from the database MUST include authentication by default.** This means:
- The `ezra-authentication` domain package is included as a dependency
- Clerk JWT verification is wired into the lifespan
- A `require_auth` dependency is created for protecting routes
- The `/healthz` endpoint is the only unauthenticated route

Only skip authentication if the user explicitly requests it (e.g., `--no-auth` or "this app doesn't need auth").

## Naming Conventions

Derive all names from the `name` parameter:

| Derived Name | Pattern | Example (`name=deal-triage`) |
|---|---|---|
| Package name (backend) | `ezra-{name}` | `ezra-deal-triage` |
| Python module | `ezra_{name_underscored}` | `ezra_deal_triage` |
| Package name (frontend) | `@ezra/{name}` | `@ezra/deal-triage` |
| Docker Compose service | `{name}` / `{name}-dev` | `deal-triage` / `deal-triage-dev` |
| Docker volume (backend) | `{name_underscored}_venv` | `deal_triage_venv` |
| Docker volume (frontend) | `{name_underscored}_node_modules` | `deal_triage_node_modules` |
| Terraform app dir | `infrastructure/apps/{name}/` | `infrastructure/apps/deal-triage/` |
| CI filter name | `{name}` or `{name}-frontend` | `deal-triage-frontend` |

---

## Backend App (type: api)

### Step 1: Create Directory Structure

```
backend/packages/apps/{name}/
  src/ezra_{name_underscored}/
    __init__.py
    main.py
  tests/
    __init__.py
    conftest.py
    fixtures/
      __init__.py
      factories.py
    test_healthz.py
  Dockerfile
  pyproject.toml
```

### Step 2: Create Files

#### `pyproject.toml`

```toml
[project]
name = "ezra-{name}"
version = "0.0.1"
description = "The Ezra {TitleCase name} service."
requires-python = ">=3.12"
dependencies = [
    "ezra-authentication",
    "ezra-core",
    "fastapi[standard]==0.115.12",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Pin the same FastAPI version as `backend/packages/apps/api/pyproject.toml`. Add domain dependencies as needed.

#### `src/ezra_{name_underscored}/__init__.py`

Empty file.

#### `src/ezra_{name_underscored}/main.py`

**Default (with authentication):**

```python
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from ezra_authentication.exceptions import ClerkAPIUnavailableError, InvalidTokenError, JWKSUnavailableError
from ezra_authentication.infrastructure import ClerkClient
from ezra_authentication.models import User
from ezra_authentication.service import get_or_sync_user
from ezra_core.settings import CORSSettings, DatabaseSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_settings = DatabaseSettings()
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(db_settings.url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.clerk = ClerkClient()
    yield
    await engine.dispose()


app = FastAPI(title="Ezra {TitleCase name}", lifespan=lifespan)

cors = CORSSettings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_auth(request: Request) -> User:
    clerk: ClerkClient = request.app.state.clerk
    session_factory = request.app.state.session_factory
    token = (request.headers.get("Authorization") or "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    try:
        claims = await clerk.verify_token(token)
    except (InvalidTokenError, JWKSUnavailableError):
        raise HTTPException(status_code=401, detail="Invalid token")
    except ClerkAPIUnavailableError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    async with session_factory() as session:
        return await get_or_sync_user(session, clerk, claims["sub"])


@app.get("/healthz", operation_id="getHealthz")
async def healthz():
    return {"status": "ok", "service": "{name}"}
```

All routes that expose data should use `user: User = Depends(require_auth)`. The `/healthz` endpoint remains unauthenticated. Follow `backend/packages/apps/api/src/ezra_api/dependencies/auth.py` for the full auth pattern if more complex auth flows are needed.

**With `--no-auth` (only when explicitly requested):**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ezra_core.settings import CORSSettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Ezra {TitleCase name}", lifespan=lifespan)

cors = CORSSettings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", operation_id="getHealthz")
async def healthz():
    return {"status": "ok", "service": "{name}"}
```

#### `Dockerfile`

Follow the exact pattern from `backend/packages/apps/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages packages

RUN uv sync --frozen --no-dev --package ezra-{name}

EXPOSE {port}

CMD ["uv", "run", "--no-dev", "--package", "ezra-{name}", "fastapi", "run", "--host", "0.0.0.0", "--port", "{port}", "packages/apps/{name}/src/ezra_{name_underscored}/main.py"]
```

#### `tests/conftest.py`

```python
pytest_plugins = ["ezra_test_utils.fixtures"]
```

#### `tests/fixtures/factories.py`

Empty file with no content.

#### `tests/test_healthz.py`

```python
from httpx import ASGITransport, AsyncClient

from ezra_{name_underscored}.main import app


async def test_healthz_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "{name}"}
```

### Step 3: Register in Backend Workspace

**`backend/pyproject.toml`** — add to both places:

1. Under `[project] dependencies`: add `"ezra-{name}"`
2. Under `[tool.uv.workspace] members`: add `"packages/apps/{name}"`

### Step 4: Add Docker Compose Services

**`backend/compose.yml`** — add prod + dev services:

```yaml
  {name}:
    <<: *api-common
    profiles: [prod]
    build:
      context: .
      dockerfile: packages/apps/{name}/Dockerfile
    ports:
      - "{port}:{port}"

  {name}-dev:
    <<: *api-common
    profiles: [dev]
    image: ghcr.io/astral-sh/uv:python3.12-bookworm-slim
    working_dir: /app
    ports:
      - "{port}:{port}"
    volumes:
      - .:/app
      - {name_underscored}_venv:/app/.venv
    command: >
      bash -c "uv sync --frozen --package ezra-{name} &&
      uv run --package ezra-{name} fastapi dev --host 0.0.0.0 --port {port} packages/apps/{name}/src/ezra_{name_underscored}/main.py"
```

Add `{name_underscored}_venv:` to the `volumes:` section at the bottom.

**Note:** If the new app does NOT need all the same dependencies as `api-common` (postgres, redis, temporal, terraform-init), create a custom `depends_on` block instead of using `<<: *api-common`. Use `*api-common` only when the app genuinely needs all those infrastructure services.

### Step 5: Sync and Verify

```bash
docker compose --profile dev exec api-dev uv sync
docker compose --profile dev exec api-dev uv run pytest packages/apps/{name}/tests/ -v
```

---

## Backend App (type: worker)

Same as `type: api` but with these differences:

- **No `main.py` with FastAPI** — instead create `worker.py` with Temporal worker setup
- **No Dockerfile** (unless it needs independent deployment — ask user)
- **No healthz test** — no HTTP endpoints
- **No CORS middleware**
- **`pyproject.toml` dependencies**: `temporalio` instead of `fastapi[standard]`
- **Docker Compose service**: uses `python -m ezra_{name_underscored}.worker` instead of `fastapi dev`

---

## Frontend App

### Step 1: Create Directory Structure

```
frontend/apps/{name}/
  src/
    app/
      layout.tsx
      page.tsx
      globals.css
    components/
    hooks/
  tests/
    unit/
    integration/
  public/
  Dockerfile
  package.json
  next.config.ts
  tsconfig.json
  eslint.config.mjs
  postcss.config.mjs
```

### Step 2: Create Files

#### `package.json`

```json
{
  "name": "@ezra/{name}",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack --port {port}",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "check-types": "tsc --noEmit"
  },
  "dependencies": {
    "@ezra/api-client": "workspace:*",
    "@ezra/design-system": "workspace:*",
    "@radix-ui/themes": "3.3.0",
    "@tanstack/react-query": "5.91.2",
    "next": "16.1.6",
    "react": "19.2.4",
    "react-dom": "19.2.4"
  },
  "devDependencies": {
    "@ezra/eslint-config": "workspace:*",
    "@ezra/typescript-config": "workspace:*",
    "@tailwindcss/postcss": "4.2.1",
    "@types/react": "19.2.14",
    "@types/react-dom": "19.2.3",
    "eslint": "9.39.4",
    "tailwindcss": "4.2.1",
    "typescript": "5.9.3"
  }
}
```

**CRITICAL**: Check `frontend/apps/app/package.json` for current pinned versions before writing. Never use `^` or `~`.

If `--auth clerk` is specified, also add to dependencies:
```json
    "@clerk/nextjs": "7.0.7"
```

#### `next.config.ts`

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@ezra/design-system", "@ezra/api-client"],
};

export default nextConfig;
```

#### `tsconfig.json`

```json
{
  "extends": "@ezra/typescript-config/nextjs.json",
  "compilerOptions": {
    "incremental": true,
    "paths": {
      "@/*": ["./src/*"],
      "@tests/*": ["./tests/*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts"
  ],
  "exclude": ["node_modules", "playwright-report", "test-results", "playwright.config.ts"]
}
```

#### `eslint.config.mjs`

Check `frontend/apps/app/eslint.config.mjs` for the current pattern and replicate it.

#### `postcss.config.mjs`

Check `frontend/apps/app/postcss.config.mjs` for the current pattern and replicate it.

#### `src/app/globals.css`

```css
@import "@ezra/design-system/styles";

@source "../../../../packages/design-system/src/**/*.{ts,tsx}";
```

#### `src/app/layout.tsx`

**Without Clerk auth:**

```tsx
import type { Metadata } from "next";
import { Geologica, Roboto_Mono } from "next/font/google";
import { QueryProvider } from "@ezra/api-client/providers/queryProvider";
import { Theme } from "@radix-ui/themes";
import "./globals.css";

const geologica = Geologica({ variable: "--font-geologica", subsets: ["latin"] });
const robotoMono = Roboto_Mono({ variable: "--font-roboto-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Ezra {TitleCase name}",
  description: "Ezra {TitleCase name}",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geologica.variable} ${robotoMono.variable} antialiased`}>
        <QueryProvider>
          <Theme>{children}</Theme>
        </QueryProvider>
      </body>
    </html>
  );
}
```

**With Clerk auth** (`--auth clerk`):

Wrap with `<ClerkProvider>` and add `<ClerkTokenSyncProvider>` inside `<QueryProvider>` — follow the exact pattern from `frontend/apps/deal-triage/src/app/layout.tsx`. Also create `src/middleware.ts` with Clerk middleware.

#### `src/app/page.tsx`

```tsx
export default function HomePage() {
  return (
    <main>
      <h1>Ezra {TitleCase name}</h1>
    </main>
  );
}
```

#### `Dockerfile`

Follow the exact multi-stage pattern from `frontend/apps/deal-triage/Dockerfile`, replacing:
- `@ezra/deal-triage` with `@ezra/{name}`
- `apps/deal-triage` with `apps/{name}`
- Port `3001` with `{port}`
- Add/remove `ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` based on `--auth`

```dockerfile
FROM node:20-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@10.19.0 --activate
RUN pnpm add -g turbo

FROM base AS pruner
WORKDIR /app
COPY . .
RUN turbo prune @ezra/{name} --docker

FROM base AS deps
WORKDIR /app
COPY --from=pruner /app/out/json/ ./
RUN pnpm install --frozen-lockfile

FROM deps AS builder
COPY --from=pruner /app/out/full/ ./
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
RUN turbo run build --filter=@ezra/{name}

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/{name}/.next/standalone ./
COPY --from=builder /app/apps/{name}/.next/static ./apps/{name}/.next/static
USER nextjs
EXPOSE {port}
ENV PORT={port}
ENV HOSTNAME="0.0.0.0"
CMD ["node", "apps/{name}/server.js"]
```

**CRITICAL**: Check `frontend/apps/deal-triage/Dockerfile` for current pnpm version before writing.

### Step 3: Add Docker Compose Services

**`frontend/compose.yml`** — add prod + dev services:

```yaml
  {name}:
    <<: *frontend-common
    profiles: [prod]
    build:
      context: .
      dockerfile: apps/{name}/Dockerfile
    ports:
      - "{port}:{port}"
    depends_on:
      - api

  {name}-dev:
    <<: [*frontend-common, *frontend-dev]
    profiles: [dev]
    ports:
      - "{port}:{port}"
    volumes:
      - .:/app
      - {name_underscored}_node_modules:/app/node_modules
    command: >
      bash -c "pnpm install --frozen-lockfile &&
      pnpm turbo run dev --filter=@ezra/{name}"
    depends_on:
      - api-dev
```

Add `{name_underscored}_node_modules:` to the `volumes:` section at the bottom.

### Step 4: Install and Verify

```bash
cd frontend && pnpm install
pnpm --filter @ezra/{name} check-types
pnpm --filter @ezra/{name} dev
```

Visit `http://localhost:{port}` to verify the app loads.

---

## Post-Scaffold: Registration Points Checklist

After scaffolding, inform the user about these additional registration points that require manual setup (do NOT auto-create these — they depend on deployment decisions):

### Infrastructure (when ready to deploy)

Create `infrastructure/apps/{name}/` with:
- `main.tf` — calls `../../modules/backend-ecs` or `../../modules/frontend-ecs`
- `variables.tf` — standard variables (see `infrastructure/apps/deal-triage/variables.tf` as template)
- `outputs.tf` — export service URL, ARNs as needed

Register in `infrastructure/aws/main.tf` as a new module.

### CI/CD (when ready to deploy)

**`.github/workflows/deploy.yml`** — add:

1. **Change detection filter** in `detect-changes` job:
   - Backend: `{name}: ['backend/packages/apps/{name}/**', 'backend/packages/domains/**', ...]`
   - Frontend: `{name}-frontend: ['frontend/apps/{name}/**', 'frontend/packages/**', ...]`

2. **Build step** in `build-backend` or `build-frontend` job
3. **Deploy job** — new `deploy-{name}` or `deploy-{name}-frontend` job

### Testing (after implementing features)

Run the test scaffolding skills:
- Backend: `/ezra-scaffold-backend-tests packages/apps/{name}`
- Frontend: `/ezra-scaffold-frontend-app-tests {name} --frontend-port {port}`

### API Codegen (if frontend talks to a new backend service)

Follow `frontend/CLAUDE.md` "Adding a new backend service" section:
1. Add entry to `orval.config.ts`
2. Create mutator in `src/mutators/{name}.ts`
3. Add subpath exports to `@ezra/api-client/package.json`
4. Add spec URL to `scripts/fetchSpecs.mjs`

### Port Map

Update `CLAUDE.md` port map table and `docs/ARCHITECTURE.md` service map.

---

## What This Skill Does

- Creates all app source files (entry point, config, Dockerfile)
- Registers in workspace (pyproject.toml or pnpm-workspace auto-discovery)
- Adds Docker Compose services (dev + prod profiles)
- Creates basic test structure
- Verifies the app starts

## What This Skill Does NOT Do

- Does not create infrastructure Terraform modules (deployment-time concern)
- Does not modify CI/CD workflows (deployment-time concern)
- Does not set up API codegen / Orval config (separate workflow)
- Does not create domain packages (use the manual process in `backend/packages/CLAUDE.md`)
- Does not write feature code beyond the healthz endpoint / home page
