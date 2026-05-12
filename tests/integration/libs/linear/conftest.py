"""Configuration for Linear integration tests.

Externalizes Linear API configuration from settings to environment variables,
making the tests independent of the settings module.
"""

import os

import pytest

from settings.linear import LinearSettings


def pytest_runtest_setup(item):
    """Skip integration tests unless HSB_RUN_INTEGRATION=1."""
    if os.getenv("HSB_RUN_INTEGRATION") != "1":
        pytest.skip("integration test skipped; set HSB_RUN_INTEGRATION=1 to run live")


@pytest.fixture()
def linear_config() -> LinearSettings:
    """Linear configuration loaded from .env via LinearSettings."""
    cfg = LinearSettings()

    if not cfg.api_key:
        pytest.skip("LINEAR_API_KEY is not configured")
    if not cfg.team_id:
        pytest.skip("LINEAR_TEAM_ID is not configured")
    if not cfg.project_id:
        pytest.skip("LINEAR_PROJECT_ID is not configured")

    return cfg


@pytest.fixture()
def api_key(linear_config: LinearSettings) -> str:
    return linear_config.api_key.get_secret_value()


@pytest.fixture()
def team_id(linear_config: LinearSettings) -> str:
    return linear_config.team_id


@pytest.fixture()
def project_id(linear_config: LinearSettings) -> str:
    return linear_config.project_id
