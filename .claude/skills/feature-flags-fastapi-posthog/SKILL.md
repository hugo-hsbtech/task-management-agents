---
name: feature-flags-fastapi-posthog
description: FastAPI feature flag patterns using the PostHog Python SDK — lifespan initialization, Depends()-based evaluation, middleware for pre-loading, local evaluation, and testing. FastAPI-specific PostHog feature flag patterns.
author: Carlos Melgoza
---

# Feature Flags — FastAPI + PostHog

FastAPI implementation patterns for evaluating PostHog feature flags on the server using the `posthog` Python SDK.

## When to Activate

- Adding feature flag evaluation in FastAPI route handlers or services
- Setting up the PostHog Python SDK in a FastAPI service
- Writing tests that involve feature flags
- Building a Starlette middleware to pre-load flag context
- Auditing or cleaning up flags via a CLI command

## Installation

```bash
uv add posthog
```

## SDK Initialization via Lifespan

Initialize once at startup via `lifespan` — never per-request.

```python
# yourservice/posthog_client.py
import posthog
from .settings import get_settings


def init_posthog() -> None:
    settings = get_settings()
    if not settings.posthog_api_key:
        return  # Disabled in environments without a key

    posthog.api_key = settings.posthog_api_key
    posthog.host = settings.posthog_host

    # Local evaluation avoids a network round-trip per flag check.
    # Requires POSTHOG_PERSONAL_API_KEY.
    if settings.posthog_personal_api_key:
        posthog.personal_api_key = settings.posthog_personal_api_key
```

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .posthog_client import init_posthog


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_posthog()
    yield
```

## Settings

```python
# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    posthog_api_key: str = ""
    posthog_personal_api_key: str = ""  # phx_... for local evaluation
    posthog_host: str = "https://app.posthog.com"
```

## Typed Flag Constants

```python
# yourservice/flags.py
from dataclasses import dataclass


@dataclass(frozen=True)
class _Flags:
    NEW_CHECKOUT: str = "new-checkout-flow"
    BILLING_V2: str = "billing-v2-enabled"
    AI_AUTOCOMPLETE: str = "ai-autocomplete-beta"


Flags = _Flags()
```

## Core Evaluation Helpers

```python
# yourservice/feature_flags.py
from __future__ import annotations

import posthog
from fastapi import Request

from .flags import Flags  # noqa: F401 — re-export


def _distinct_id_from_request(request: Request) -> str:
    """Extract distinct ID from the request. Authenticated users use their ID; others use session."""
    user = getattr(request.state, "user", None)
    if user and getattr(user, "id", None):
        return str(user.id)
    # Fall back to a session cookie or generated ID
    return request.cookies.get("ph_distinct_id", "anonymous")


def _person_properties(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        return {}
    return {
        "email": getattr(user, "email", None),
        "plan": getattr(user, "plan", None),
    }


def is_enabled(flag_key: str, request: Request) -> bool:
    """Evaluate a boolean feature flag for the current request. Returns False on any error."""
    try:
        result = posthog.feature_enabled(
            flag_key,
            _distinct_id_from_request(request),
            person_properties=_person_properties(request),
        )
        return bool(result)
    except Exception:
        return False  # fail safe — always default off


def get_flag_value(flag_key: str, request: Request) -> str | bool | None:
    """Evaluate a multivariate flag. Returns the variant key or None."""
    try:
        return posthog.get_feature_flag(
            flag_key,
            _distinct_id_from_request(request),
            person_properties=_person_properties(request),
        )
    except Exception:
        return None
```

## Middleware — Pre-Load Flags Once Per Request

Evaluates all flags once and attaches them to `request.state.flags`. Route handlers read from `request.state.flags` without making additional SDK calls.

```python
# yourservice/middleware.py
from __future__ import annotations

import posthog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .feature_flags import _distinct_id_from_request, _person_properties
from .flags import Flags

_PRELOAD_FLAGS: list[str] = [v for v in vars(Flags).values() if isinstance(v, str)]


class FeatureFlagsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.flags = self._evaluate_all(request)
        return await call_next(request)

    @staticmethod
    def _evaluate_all(request: Request) -> dict[str, bool]:
        distinct_id = _distinct_id_from_request(request)
        person_props = _person_properties(request)
        try:
            all_flags = posthog.get_all_flags(distinct_id, person_properties=person_props)
            return {key: bool(all_flags.get(key, False)) for key in _PRELOAD_FLAGS}
        except Exception:
            return {key: False for key in _PRELOAD_FLAGS}
```

Register in `create_app()`:

```python
from .middleware import FeatureFlagsMiddleware

app.add_middleware(FeatureFlagsMiddleware)
```

Usage in route handlers:

```python
from fastapi import Request
from .flags import Flags


@router.get("/checkout/")
async def checkout(request: Request):
    if request.state.flags.get(Flags.NEW_CHECKOUT):
        return {"version": "new"}
    return {"version": "old"}
```

## Dependency-Based Evaluation (Alternative to Middleware)

For routes where you only need one or two flags, use a `Depends()` instead of pre-loading all flags:

```python
# dependencies.py
from fastapi import Depends, Request
from .feature_flags import is_enabled
from .flags import Flags


def new_checkout_enabled(request: Request) -> bool:
    return is_enabled(Flags.NEW_CHECKOUT, request)


# Route usage
@router.get("/checkout/")
async def checkout(use_new_checkout: bool = Depends(new_checkout_enabled)):
    return {"version": "new" if use_new_checkout else "old"}
```

## Group (B2B Org) Targeting

```python
import posthog

posthog.feature_enabled(
    Flags.BILLING_V2,
    distinct_id=str(user.id),
    groups={"organization": str(user.organization_id)},
    group_properties={
        "organization": {
            "plan": user.organization.plan,
            "size": user.organization.member_count,
        }
    },
)
```

## Local Evaluation

Local evaluation runs flag logic in-process from a cached copy of your flag rules. No network call per evaluation — rules are refreshed every 30 seconds.

Requires `POSTHOG_PERSONAL_API_KEY` (a Personal API Key, **not** the project key).

```python
# Confirmed in init_posthog() above:
posthog.personal_api_key = settings.posthog_personal_api_key
# With this set, feature_enabled() and get_feature_flag() use local evaluation automatically.
```

**Always enable local evaluation in production.** Without it, every `feature_enabled()` call makes a synchronous HTTP request.

## Typer CLI — Flag Audit Command

Useful for periodic staleness checks or pre-deploy verification.

```python
# cli.py
import posthog
import typer

from .flags import Flags
from .settings import get_settings

app = typer.Typer()

CODE_FLAGS = {v for v in vars(Flags).values() if isinstance(v, str)}


@app.command()
def audit_flags():
    """Audit PostHog feature flags against code references."""
    settings = get_settings()
    client = posthog.Client(api_key=settings.posthog_api_key)
    response = client._call_decide()

    remote_flags = {f["key"] for f in response.get("featureFlags", [])}
    in_code_not_posthog = CODE_FLAGS - remote_flags
    in_posthog_not_code = remote_flags - CODE_FLAGS

    if in_code_not_posthog:
        typer.secho(f"Flags in code but missing from PostHog: {in_code_not_posthog}", fg=typer.colors.RED)
    if in_posthog_not_code:
        typer.secho(f"Cleanup candidates (in PostHog but not in code): {in_posthog_not_code}", fg=typer.colors.YELLOW)
    if not in_code_not_posthog and not in_posthog_not_code:
        typer.secho("All flags are in sync.", fg=typer.colors.GREEN)
```

Run as:

```bash
uv run python -m yourservice.cli audit-flags
```

## Testing

### Default Fixture — All Flags Off

```python
# conftest.py
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def disable_feature_flags():
    """All flags off by default in tests. Use enable_flag to opt in."""
    with (
        patch("posthog.feature_enabled", return_value=False),
        patch("posthog.get_feature_flag", return_value=False),
        patch("posthog.get_all_flags", return_value={}),
    ):
        yield


@pytest.fixture
def enable_flag():
    """Enable a specific flag for one test."""
    def _enable(flag_key: str, value: bool | str = True):
        return patch("posthog.feature_enabled", side_effect=lambda k, *a, **kw: value if k == flag_key else False)
    return _enable
```

### Test Both Branches

```python
# tests/test_checkout.py
import pytest
from httpx import AsyncClient
from .flags import Flags


@pytest.mark.asyncio
async def test_new_checkout_when_flag_on(client: AsyncClient, enable_flag):
    with enable_flag(Flags.NEW_CHECKOUT):
        response = await client.get("/checkout/")
    assert response.json()["version"] == "new"


@pytest.mark.asyncio
async def test_old_checkout_when_flag_off(client: AsyncClient):
    # disable_feature_flags autouse fixture — flag is already off
    response = await client.get("/checkout/")
    assert response.json()["version"] == "old"


@pytest.mark.asyncio
async def test_checkout_safe_when_posthog_unreachable(client: AsyncClient, mocker):
    mocker.patch("posthog.feature_enabled", side_effect=Exception("timeout"))
    response = await client.get("/checkout/")
    # Must not 500 — fail safe renders old checkout
    assert response.status_code == 200
```

### Test Middleware Directly

```python
def test_flags_middleware_sets_state(mocker):
    mocker.patch("posthog.get_all_flags", return_value={"new-checkout-flow": True})

    from starlette.testclient import TestClient
    from yourservice.main import app

    with TestClient(app) as client:
        resp = client.get("/checkout/")
    assert resp.status_code == 200
```

## Environment Variables

```bash
POSTHOG_API_KEY=phc_...                   # Project API key
POSTHOG_PERSONAL_API_KEY=phx_...          # For local evaluation (strongly recommended)
POSTHOG_HOST=https://app.posthog.com      # Or your self-hosted URL
```

**Remember**: Set `POSTHOG_PERSONAL_API_KEY` and enable local evaluation in production. Without it, every `feature_enabled()` call hits the PostHog API synchronously — one network failure will take down flag evaluation for every request.

## See Also

- `feature-flags` — universal patterns: naming, types, lifecycle, hygiene rules
- `feature-flags-posthog` — PostHog API: create, target, discover, archive flags
