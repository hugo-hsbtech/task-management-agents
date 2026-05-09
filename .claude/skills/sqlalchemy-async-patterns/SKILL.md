---
name: sqlalchemy-async-patterns
description: SQLAlchemy 2.0 async patterns for backend services, including typed Mapped models, AsyncSession usage, async_sessionmaker, eager loading, 2.0-style queries, session-per-request wiring, multi-tenant filtering, and connection-pool configuration.
---

# SQLAlchemy Async Patterns

Use this skill when building or changing backend persistence code with
SQLAlchemy 2.0's async APIs.

## First Reads

Read these files before changing ORM or session behavior:

- `backend/packages/domains/core/src/ezra_core/database.py`
- `backend/packages/apps/api/src/ezra_api/main.py`
- `backend/packages/apps/api/src/ezra_api/dependencies/auth.py`
- `backend/packages/domains/authentication/src/ezra_authentication/models.py`
- `backend/packages/domains/authentication/src/ezra_authentication/service.py`
- `backend/packages/domains/test-utils/src/ezra_test_utils/database.py`
- `docs/plans/database-and-local-infra-foundation.md`

## Core Rules

1. Use SQLAlchemy 2.0 style everywhere: typed `Mapped[...]`, `mapped_column()`, `select()`, `update()`, and `delete()`.
2. Use `AsyncSession` only. Do not introduce sync sessions or sync engines into FastAPI request paths.
3. Create sessions via `async_sessionmaker(..., expire_on_commit=False)` and inject them per request with FastAPI `Depends()`.
4. Prefer explicit eager loading over implicit lazy loads. Async code should not surprise you with hidden IO.
5. Keep query construction in services or repositories, not in route handlers.
6. Encode tenant or organization scoping in explicit predicates or repository helpers. Do not rely on hidden global filters.
7. Reuse the project's shared `Base` from `ezra_core.database` so Alembic can see all metadata.

## Model Declarations

Follow the current pattern in `backend/packages/domains/authentication/src/ezra_authentication/models.py`.

```python
import uuid
from datetime import datetime

from ezra_core.database import Base
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    members: Mapped[list["Membership"]] = relationship(back_populates="organization")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="members")
```

Guidelines:

- Type every mapped attribute with `Mapped[...]`.
- Use Python types that match real nullable behavior: `str | None`, `datetime | None`, and so on.
- Put indexes, uniqueness, and nullability on the column definition instead of relying on conventions.
- Use `StrEnum` for columns with a fixed set of valid values (status fields, type fields) instead of bare `str`. Example: `class TriageStatus(StrEnum): PENDING = "pending"` then `triage_status: Mapped[TriageStatus]`. This gives type safety, IDE autocompletion, and self-documenting code.
- Keep shared base classes in `ezra_core`, not per domain.

## Engine and Session Factory

This project currently centralizes this in `ezra_core.database`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_engine(database_url: str):
    return create_async_engine(database_url)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

Keep `expire_on_commit=False`. In async code, it prevents post-commit attribute access from triggering unexpected lazy loads after the transaction boundary.

When pool tuning is needed, extend `create_async_engine()` deliberately:

```python
engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)
```

Guidelines:

- Start with the shared helper in `ezra_core.database`.
- Add pool settings only when deployment behavior or load testing justifies them.
- Prefer `pool_pre_ping=True` when connections may go stale across long-lived processes.

## Session-Per-Request with FastAPI

Each app should expose a request-scoped session dependency sourced from
`app.state.session_factory`.

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

Rules:

- Never keep a global `AsyncSession`.
- Never share one session across concurrent requests or background tasks.
- Keep dependency wiring in the app package; keep ORM logic in domains.

## 2.0 Query Patterns

### Select

```python
from sqlalchemy import select

stmt = select(User).where(User.clerk_id == clerk_id, User.deleted_at.is_(None))
result = await session.execute(stmt)
user = result.scalar_one_or_none()
```

Use this style for reads. It matches the current authentication service.

### Insert / create

```python
user = User(clerk_id=clerk_id, email=email)
session.add(user)
await session.commit()
await session.refresh(user)
```

Use `refresh()` when you need database-assigned fields after commit.

### Update

For entity-in-hand updates:

```python
user.email = email
user.deleted_at = None
await session.commit()
await session.refresh(user)
```

For set-based updates:

```python
from sqlalchemy import update

stmt = (
    update(User)
    .where(User.organization_id == organization_id)
    .values(deleted_at=None)
)
await session.execute(stmt)
await session.commit()
```

### Delete

Prefer soft delete when the domain requires recoverability or auditability.

```python
from sqlalchemy import delete

stmt = delete(Invite).where(Invite.organization_id == organization_id)
await session.execute(stmt)
await session.commit()
```

## Upsert Pattern

The current auth service uses a dialect-agnostic select-then-update/insert flow:

```python
stmt = select(User).where(User.clerk_id == clerk_id)
result = await session.execute(stmt)
user = result.scalar_one_or_none()

if user is None:
    user = User(clerk_id=clerk_id, email=email)
    session.add(user)
else:
    user.email = email

await session.commit()
await session.refresh(user)
```

Prefer this when portability matters more than database-specific UPSERT syntax.

## Relationship Loading

In async code, relationship loading must be intentional.

Use `selectinload()` for collections:

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

stmt = (
    select(Organization)
    .options(selectinload(Organization.members))
    .where(Organization.id == organization_id)
)
organization = (await session.execute(stmt)).scalar_one()
```

Use `joinedload()` when loading one related object and row explosion is controlled:

```python
from sqlalchemy.orm import joinedload

stmt = (
    select(Invoice)
    .options(joinedload(Invoice.customer))
    .where(Invoice.id == invoice_id)
)
invoice = (await session.execute(stmt)).scalar_one()
```

Guidelines:

- Default to `selectinload()` for one-to-many relationships.
- Use `joinedload()` for compact one-to-one or many-to-one cases.
- Do not rely on lazy loading after the session has committed or closed.

## Async Gotchas

Watch for these failure modes:

- Accessing unloaded relationships after commit or after dependency teardown.
- Calling sync-only libraries inside ORM code without `run_in_threadpool()`.
- Reusing one `AsyncSession` across `asyncio.gather()` tasks.
- Forgetting to `await session.execute(...)`, `await session.commit()`, or `await session.refresh(...)`.
- Returning ORM objects to FastAPI without a response model that can serialize them predictably.

## Multi-Tenant Query Filtering

The current repo does not yet have a shared multi-tenant ORM helper, so keep tenant
scoping explicit.

Recommended pattern:

```python
from sqlalchemy import select


async def list_users_for_organization(
    session: AsyncSession,
    organization_id,
) -> list[User]:
    stmt = select(User).where(
        User.organization_id == organization_id,
        User.deleted_at.is_(None),
    )
    return list((await session.scalars(stmt)).all())
```

Rules:

- Pass `organization_id`, `workspace_id`, or `tenant_id` into the service method explicitly.
- Include the tenant predicate in every read and write statement that touches tenant-owned data.
- Prefer one well-named repository or service helper over copy-pasted filters across routes.

## Testing Patterns

For unit tests, use an async engine and `async_sessionmaker(..., expire_on_commit=False)`.
For integration tests, follow the savepoint pattern in
`backend/packages/domains/test-utils/src/ezra_test_utils/database.py`.

```python
session = AsyncSession(
    bind=conn,
    join_transaction_mode="create_savepoint",
    expire_on_commit=False,
)
```

This lets application code call `session.commit()` without breaking test isolation.

## Anti-Patterns

Do not:

- import a domain's private engine or create ad hoc engines in random modules
- mix sync `Session` APIs into FastAPI handlers
- rely on lazy loads to fetch related rows implicitly
- put tenant scope in hidden globals or thread locals
- keep long-lived ORM entities around after the request is over
- invent a repository abstraction if a small service function is enough

## Done Checklist

Before finishing SQLAlchemy work, verify:

- models use `Mapped[...]` and `mapped_column()`
- sessions come from FastAPI request dependencies
- queries use 2.0 style APIs
- eager loading is explicit where needed
- tenant filters are explicit
- tests still isolate DB state correctly
