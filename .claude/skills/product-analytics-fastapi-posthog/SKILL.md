---
name: product-analytics-fastapi-posthog
description: FastAPI product analytics patterns using the PostHog Python SDK — lifespan initialization, event capture via Depends(), user identification, Starlette middleware for analytics context, batch events, and testing. FastAPI-specific PostHog product analytics patterns.
author: Carlos Melgoza
---

# Product Analytics — FastAPI + PostHog

FastAPI implementation patterns for capturing product analytics with the `posthog` Python SDK.

## When to Activate

- Adding event tracking in FastAPI route handlers or services
- Setting up user identification at sign-up or sign-in
- Building Starlette middleware to inject analytics context into requests
- Capturing server-side events from background tasks or webhooks
- Writing tests that involve analytics calls

## Installation

```bash
uv add posthog
```

## SDK Initialization via Lifespan

Initialize once at startup — never per-request.

```python
# yourservice/analytics.py
import posthog
from .settings import get_settings


def init_analytics() -> None:
    settings = get_settings()
    if not settings.posthog_api_key:
        return  # Disabled in environments without a key

    posthog.api_key = settings.posthog_api_key
    posthog.host = settings.posthog_host
```

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .analytics import init_analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_analytics()
    yield
    posthog.flush()  # Flush remaining events on shutdown
```

## Event Constants

```python
# yourservice/analytics/events.py
from dataclasses import dataclass


@dataclass(frozen=True)
class _Events:
    USER_SIGNED_UP:        str = "user_signed_up"
    PROJECT_CREATED:       str = "project_created"
    SUBSCRIPTION_UPGRADED: str = "subscription_upgraded"
    PAYMENT_FAILED:        str = "payment_failed"
    INVITE_SENT:           str = "invite_sent"
    DASHBOARD_VIEWED:      str = "dashboard_viewed"


Events = _Events()
```

## Settings

```python
# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"
```

## Core Capture Helper

```python
# yourservice/analytics/capture.py
from __future__ import annotations

import posthog
from fastapi import Request

from .events import Events  # noqa: F401 — re-export


def capture(distinct_id: str, event: str, properties: dict | None = None) -> None:
    """Capture an analytics event. Fails silently — never raises."""
    try:
        posthog.capture(distinct_id, event, properties or {})
    except Exception:
        pass  # analytics must never break the application


def capture_for_request(request: Request, event: str, properties: dict | None = None) -> None:
    """Capture an event for the current authenticated user from the request state."""
    user = getattr(request.state, "user", None)
    if not user:
        return
    distinct_id = getattr(request.state, "analytics_id", str(user.id))
    capture(distinct_id, event, properties)
```

## User Identification

Call `identify()` once at sign-up and sign-in with a stable database ID.

```python
# yourservice/analytics/identity.py
from __future__ import annotations

import posthog


def identify_user(user) -> None:
    """Set user profile properties in PostHog."""
    posthog.identify(
        str(user.id),
        properties={
            # $set: mutable — updated on every identify
            "email": user.email,
            "name": getattr(user, "full_name", ""),
            "plan_type": getattr(user, "plan", None),
        },
        set_once_properties={
            # $set_once: immutable — only written on first call
            "signed_up_at": user.created_at.isoformat(),
        },
    )


def identify_organization(org) -> None:
    """Set organization group properties."""
    posthog.group_identify(
        "organization",
        str(org.id),
        properties={
            "name": org.name,
            "plan": org.plan,
            "member_count": org.member_count,
            "created_at": org.created_at.isoformat(),
        },
    )
```

Call `identify_user()` in the sign-up and sign-in handlers, not on every request.

## Group Analytics (B2B)

```python
import posthog

# Use $groups in event properties to attribute events to an org
posthog.capture(
    str(user.id),
    Events.PROJECT_CREATED,
    properties={
        "project_id": str(project.id),
        "template_used": project.template or None,
        "$groups": {"organization": str(user.organization_id)},
    },
)
```

## Analytics Middleware

Injects `request.state.analytics_id` for zero-boilerplate tracking in handlers.

```python
# yourservice/analytics/middleware.py
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        user = getattr(request.state, "user", None)
        if user and getattr(user, "id", None):
            request.state.analytics_id = str(user.id)
        else:
            # Use a cookie-based anonymous ID (set by the frontend PostHog SDK)
            request.state.analytics_id = request.cookies.get("ph_distinct_id", "anonymous")

        return await call_next(request)
```

Register in `create_app()`:

```python
from .analytics.middleware import AnalyticsMiddleware

app.add_middleware(AnalyticsMiddleware)
```

## Analytics in Route Handlers

```python
# routers/projects.py
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from yourservice.analytics.capture import capture_for_request
from yourservice.analytics.events import Events
from ..database import get_session
from ..dependencies import get_current_user
from ..models.user import User
from ..schemas.project import ProjectCreate, ProjectRead
from ..services.project_service import ProjectService

router = APIRouter()


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    project = await ProjectService(session).create(payload, owner=current_user)

    capture_for_request(request, Events.PROJECT_CREATED, {
        "project_id": str(project.id),
        "template_used": payload.template,
    })

    return project
```

## High-Volume Events (Skip Person Profile)

For server-side events that don't need a person record (webhooks, background jobs, cron tasks), set `$process_person_profile` to `False` to reduce PostHog costs.

```python
posthog.capture(
    organization_id,
    "api_request_completed",
    {
        "endpoint": "/api/export",
        "duration_ms": 342,
        "$process_person_profile": False,
    },
)
```

## Batch Capture in Background Tasks

For background tasks that emit many events, use PostHog's built-in batching and flush explicitly at the end.

```python
# background_tasks.py
import posthog
from yourservice.analytics.events import Events


async def process_bulk_invites(invite_ids: list[str], sender_id: str, session) -> None:
    from yourservice.models import Invite
    from sqlalchemy import select

    result = await session.execute(select(Invite).where(Invite.id.in_(invite_ids)))
    invites = result.scalars().all()

    for invite in invites:
        posthog.capture(
            sender_id,
            Events.INVITE_SENT,
            {
                "invite_id": str(invite.id),
                "recipient_email_domain": invite.recipient_email.split("@")[1],
                "$groups": {"organization": str(invite.organization_id)},
            },
        )

    # Flush after the loop — sends all queued events in one batch
    posthog.flush()
```

## Testing

### Disable All Analytics by Default

```python
# conftest.py
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def disable_analytics():
    """Silence all PostHog calls in tests."""
    with (
        patch("posthog.capture"),
        patch("posthog.identify"),
        patch("posthog.group_identify"),
        patch("posthog.flush"),
    ):
        yield


@pytest.fixture
def captured_events():
    """Collect all captured events for assertion in a test."""
    events = []

    def _capture(distinct_id, event, properties=None):
        events.append({"distinct_id": distinct_id, "event": event, "properties": properties or {}})

    with patch("posthog.capture", side_effect=_capture):
        yield events
```

### Assert Events Were Captured

```python
# tests/test_projects.py
import pytest
from httpx import AsyncClient

from yourservice.analytics.events import Events


@pytest.mark.asyncio
async def test_project_created_event_captured(client: AsyncClient, auth_headers: dict, captured_events: list):
    await client.post("/projects/", json={"name": "My Project"}, headers=auth_headers)

    assert len(captured_events) == 1
    event = captured_events[0]
    assert event["event"] == Events.PROJECT_CREATED
    assert "project_id" in event["properties"]


@pytest.mark.asyncio
async def test_analytics_failure_does_not_break_request(client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch("posthog.capture", side_effect=Exception("PostHog down"))
    # Request must succeed even when analytics raises
    response = await client.post("/projects/", json={"name": "My Project"}, headers=auth_headers)
    assert response.status_code == 201
```

## Environment Variables

```bash
POSTHOG_API_KEY=phc_...
POSTHOG_HOST=https://app.posthog.com
```

**Remember**: PostHog's Python SDK queues events in memory and flushes asynchronously. In short-lived processes (Lambda, background tasks, CLI commands), always call `posthog.flush()` at the end — otherwise queued events are lost when the process exits. The `lifespan` shutdown hook handles this for the API process itself.

## See Also

- `product-analytics` — universal patterns: naming, identity lifecycle, governance rules
- `product-analytics-ts-posthog` — TypeScript + PostHog SDK for the frontend
- `feature-flags-fastapi-posthog` — PostHog feature flags for FastAPI
