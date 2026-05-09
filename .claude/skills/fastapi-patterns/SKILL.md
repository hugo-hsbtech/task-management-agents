---
name: fastapi-patterns
description: Use when building or modifying FastAPI services, adding new endpoints, or creating new backend apps. Covers Depends-based dependency injection, router composition, lifespan wiring, Pydantic v2 schemas, async handlers, middleware, HTTPException handling, background tasks, and OpenAPI customization for Orval-compatible APIs.
---

# FastAPI Patterns

Use this skill when working on backend services built with FastAPI.

## When to Use

- adding or modifying FastAPI endpoints
- creating a new backend app under `backend/packages/apps/`
- wiring request dependencies, lifespan resources, or middleware
- defining Pydantic request and response schemas
- shaping OpenAPI output for Orval-generated frontend clients

## First Reads

Read these files before making framework-level changes:

- `backend/CLAUDE.md`
- `backend/packages/apps/api/src/ezra_api/main.py`
- `backend/packages/apps/document-investigation/src/ezra_document_investigation/main.py`
- `backend/packages/domains/core/src/ezra_core/database.py`
- `backend/packages/domains/core/src/ezra_core/settings.py`
- `docs/plans/database-and-local-infra-foundation.md`

## Core Rules

1. Build async-first request handlers. Do not introduce sync database or network calls into route handlers.
2. Keep FastAPI apps thin. Routing, request parsing, and HTTP error mapping live in the app package; domain logic lives in domain packages.
3. Use explicit dependency injection with `Depends()` instead of module-level singletons or hidden globals.
4. Put long-lived resources on `app.state` during lifespan startup and clean them up on shutdown.
5. Keep Pydantic request/response schemas separate from SQLAlchemy models.
6. Raise `HTTPException` for request-facing failures; reserve bare exceptions for truly unexpected faults.
7. Set explicit `operation_id` and `response_model` values on routes so OpenAPI stays stable for Orval codegen.
8. Prefer predictable OpenAPI output and typed responses over ad hoc dictionaries.

## App Shape

Apps are independently deployable FastAPI services under `backend/packages/apps/`.
Each app should expose a `GET /healthz` endpoint and wire shared infrastructure through lifespan.

Minimal app shape:

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ezra_core.database import create_engine, create_session_factory
from ezra_core.settings import DatabaseSettings

db_settings = DatabaseSettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_engine(db_settings.url)
    app.state.session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


app = FastAPI(title="Ezra API", version="0.0.1", lifespan=lifespan)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.session_factory() as session:
        yield session
```

## Dependency Injection Patterns

Use dependencies for request-scoped state, auth, and shared infrastructure.

Simple dependency:

```python
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.session_factory() as session:
        yield session


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    ...
```

Sub-dependency pattern:

```python
from fastapi import Depends, Header, HTTPException, status


async def get_request_id(x_request_id: str | None = Header(default=None)) -> str:
    return x_request_id or "generated-at-edge"


async def get_current_actor(
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_session),
):
    actor = await load_actor_from_request(request_id, session)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return actor
```

Guidelines:

- Prefer small, composable dependencies over one giant "context" dependency.
- Put app-agnostic dependency helpers in a shared domain package only when more than one app uses them.
- Yield resources when cleanup matters; return plain values for pure helpers.

## Router Organization

Use routers to group related endpoints and mount them from app entrypoints.

```python
from fastapi import APIRouter, FastAPI

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}")
async def get_user(...):
    ...


app = FastAPI(...)
app.include_router(router)
```

Rules:

- Keep app entrypoints focused on app construction, middleware, and router inclusion.
- Group endpoints by bounded context, not by HTTP verb.
- Prefer explicit `prefix` and `tags` so generated docs stay navigable.
- Mount sub-apps only when they have a distinct lifecycle or external surface area.

## Lifespan Events

Use FastAPI lifespan instead of ad hoc startup globals.

Good uses for lifespan:

- create and dispose database engines
- initialize shared clients
- preload configuration that must exist before serving traffic

Avoid in lifespan:

- business-domain data backfills
- long blocking startup jobs
- per-request objects

When adding a resource, follow the same pattern used in `backend/packages/apps/api/src/ezra_api/main.py`:

1. Build the resource in lifespan startup.
2. Store it on `app.state`.
3. Expose it through a dependency.
4. Dispose or close it on shutdown.

## Pydantic v2 Schemas

Use Pydantic schemas for external contracts and typed internal DTOs.

```python
from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None = None


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3)
    display_name: str | None = Field(default=None, max_length=120)
```

Guidelines:

- Use `from_attributes=True` when serializing from ORM entities.
- Keep request and response models distinct when write and read shapes diverge.
- Use field constraints and validators for input rules, not handwritten route checks.
- Do not reuse SQLAlchemy model classes as FastAPI response models.
- Use `StrEnum` for fields with a fixed set of valid values (status, type) in both Pydantic schemas and SQLAlchemy models. Pydantic auto-validates enum membership; Orval generates a TypeScript union type from the enum values.

## Async Endpoint Patterns

Route handlers should orchestrate async dependencies and delegate business logic.

```python
@router.post(
    "/users",
    operation_id="createUser",
    response_model=UserResponse,
    status_code=201,
)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    user = await user_service.create_user(session=session, payload=payload)
    return UserResponse.model_validate(user)
```

Guidelines:

- Await every async IO boundary explicitly.
- Return typed models or clearly shaped dictionaries.
- Keep route handlers small; move branching business logic into domain services.
- When multiple queries are required, consider whether the service should batch or eager-load related data.
- Avoid returning raw dicts from endpoints that should feed generated clients.

## Middleware

Register middleware at app construction time.
The current apps already conditionally add CORS middleware based on `CORSSettings`.

```python
from fastapi.middleware.cors import CORSMiddleware

if cors_settings.origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

Guidelines:

- Use middleware for cross-cutting request/response behavior such as CORS, auth context, logging, or tracing.
- Use dependencies when logic is endpoint-scoped rather than truly global.
- Keep middleware side effects minimal and observable.

## Error Handling

Use `HTTPException` for expected request failures.

```python
from fastapi import HTTPException, status


if user is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

Rules:

- Map domain "not found", auth, and validation failures to specific status codes.
- Do not leak raw infrastructure exceptions to clients.
- If many endpoints share the same exception mapping, add a focused exception handler rather than copy-pasting.
- Keep `detail` messages stable and user-facing.

## Background Tasks

Use `BackgroundTasks` only for small, post-response follow-up work that can be safely lost on process restart.

```python
from fastapi import BackgroundTasks


@router.post("/imports")
async def start_import(
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    background_tasks.add_task(kick_off_small_follow_up)
    return {"status": "queued"}
```

Do not use `BackgroundTasks` for durable workflows, long-running jobs, or cross-service orchestration. Those belong in a real worker or job system.

## OpenAPI Customization

Prefer declarative metadata first:

```python
app = FastAPI(
    title="Ezra API",
    version="0.0.1",
    summary="Core Ezra API surface",
)
```

Endpoint-level metadata:

```python
@router.get(
    "/users/{user_id}",
    operation_id="getUserById",
    response_model=UserResponse,
    summary="Fetch a user",
    responses={404: {"description": "User not found"}},
)
async def get_user(...):
    ...
```

Guidelines:

- Keep titles, tags, summaries, `operation_id`, and `response_model` values accurate so generated docs remain useful.
- Every route should set an explicit camelCase `operation_id` to control Orval hook and client names.
- Every route should declare a `response_model` backed by Pydantic schemas so generated frontend types stay specific.
- Only override the OpenAPI schema generator when simpler metadata cannot express the requirement.
- If a frontend or client generator depends on the spec, treat breaking schema changes as product changes.

## Anti-Patterns

Do not:

- port monolithic framework patterns like global settings modules, implicit app registries, or fat view classes
- open database engines at import time without lifespan cleanup
- hide auth or tenant context in thread locals
- mix ORM entities directly into request and response schemas
- put heavy business logic or query construction directly in route handlers
- use background tasks as a substitute for a worker system

## Done Checklist

Before finishing FastAPI work, verify:

- the app still starts via `fastapi dev`
- new dependencies are explicit and typed
- request/response schemas are Pydantic v2 models where appropriate
- middleware is registered centrally
- errors map cleanly to HTTP responses
- OpenAPI metadata remains accurate
