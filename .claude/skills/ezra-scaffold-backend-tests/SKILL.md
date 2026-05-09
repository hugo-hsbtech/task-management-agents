---
name: ezra-scaffold-backend-tests
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Scaffold pytest testing infrastructure for a new backend package. Use when creating a new app in backend/packages/apps/ or a new domain in backend/packages/domains/, when user says "add tests to", "scaffold tests for", "setup testing for" a backend package, or when a new package needs conftest.py, factories, and smoke tests. Also use when retrofitting tests onto an existing package that has no tests yet.
---

# ezra-scaffold-backend-tests

Scaffolds the complete pytest testing infrastructure for a new backend package, following `docs/development-guides/testing-standards.md`.

## Input Format

```
/ezra-scaffold-backend-tests packages/apps/billing
/ezra-scaffold-backend-tests packages/domains/notifications
```

**Parameter:** relative path from `backend/` to the package directory.

## Step 1: Detect Package Type

- **App** (`packages/apps/*`): deployable FastAPI service — gets health smoke test
- **Domain** (`packages/domains/*`): shared business logic — no health test

Derive names from path:
- Path: `packages/apps/billing` → package name: `ezra-billing`, module: `ezra_billing`, service: `billing`
- Path: `packages/domains/notifications` → package name: `ezra-notifications`, module: `ezra_notifications`

## Step 2: Create Directory Structure

```bash
mkdir -p backend/{package_path}/tests/{unit,integration,fixtures}
touch backend/{package_path}/tests/__init__.py
touch backend/{package_path}/tests/unit/__init__.py
touch backend/{package_path}/tests/integration/__init__.py
touch backend/{package_path}/tests/fixtures/__init__.py
```

## Step 3: Create Files

### `tests/conftest.py`

```python
"""Test configuration for {package_name}."""

pytest_plugins = ["ezra_test_utils.fixtures"]

# Uncomment for integration tests with real Postgres:
# from ezra_test_utils.database import db_engine, db_session, run_migrations  # noqa: F401
```

### `tests/fixtures/factories.py`

```python
"""Test data factories for {package_name}.

Usage:
    from tests.fixtures.factories import SomeModelFactory

    def test_something(mock_db_session):
        item = SomeModelFactory()
        # ...

See docs/development-guides/testing-standards.md for factory patterns.
"""
```

### `tests/test_healthz.py` (apps ONLY)

Only create for app packages (`packages/apps/*`):

```python
"""Smoke test for {module_name} health endpoint."""

from httpx import ASGITransport, AsyncClient

from {module_name}.main import app


async def test_healthz_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "{service_name}"}
```

Replace `{module_name}` with the Python module name (e.g., `ezra_billing`).
Replace `{service_name}` with the service identifier (e.g., `billing`).

## Step 4: Update Coverage Config

Add the new module to `backend/pyproject.toml` coverage sources:

```toml
[tool.coverage.run]
source = [
    "ezra_api",
    "ezra_example",
    "ezra_core",
    "ezra_authentication",
    "{module_name}",  # ADD THIS
]
```

## Step 5: Verify

```bash
# Test discovery
cd backend && uv run pytest {package_path}/tests/ --collect-only

# Run smoke test (apps only)
cd backend && uv run pytest {package_path}/tests/ -v
```

## What This Skill Does NOT Do

- Does not create the package itself (pyproject.toml, src/, etc.)
- Does not add dependencies (test deps are in root dev group)
- Does not create CI workflows (backend-tests.yml covers all packages)
- Does not write feature tests (use `/ezra-generate-backend-tests`)

## Examples

**Example 1:** Scaffolding tests for a new API app
```
User: /ezra-scaffold-backend-tests packages/apps/billing
Result: tests/__init__.py, tests/conftest.py, tests/fixtures/, tests/test_healthz.py
        Coverage config updated with ezra_billing
```

**Example 2:** Scaffolding tests for a new domain package
```
User: /ezra-scaffold-backend-tests packages/domains/notifications
Result: tests/__init__.py, tests/conftest.py, tests/fixtures/
        No health test (domain packages don't have HTTP endpoints)
```

## Troubleshooting

**Tests not discovered:**
- Ensure `__init__.py` exists in `tests/` and `tests/fixtures/`
- Root pyproject.toml uses `--import-mode=importlib` which requires `__init__.py`

**`mock_db_session` fixture not found:**
- Check `conftest.py` has `pytest_plugins = ["ezra_test_utils.fixtures"]`
- Run `cd backend && uv sync` to ensure `ezra-test-utils` is installed

**Health test import error:**
- Verify the package's `src/{module_name}/main.py` exists and exports a FastAPI `app`

## Key Conventions

- All async tests run automatically (`asyncio_mode = "auto"` in root pyproject.toml)
- Integration tests: mark with `@pytest.mark.integration`
- Factories inherit from `BaseModelFactory` (provides UUID `id` field)
- `mock_db_session` for unit tests, `db_session` for integration
- `--import-mode=importlib` requires `__init__.py` in test directories
- Test naming: `test_<function>_<condition>_<expected_result>`
