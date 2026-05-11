"""Integration-test fixture URLs, IDs, and opt-in flags.

Tests construct this and skip when fields are unset (current pattern via
`_require_*` helpers). No env_prefix — each field uses `validation_alias`
because the env vars don't share a single stem.

Env vars: HSB_TEST_FIXTURE_URL, HSB_TEST_FIXTURE_PATH, HSB_LIVE_CODEX,
TEST_WORK_ITEM_ID, LINEAR_TEST_ISSUE_ID.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class TestFixtureSettings(BaseSettings):
    """Integration-test fixture configuration. All fields optional."""

    fixture_url: str | None = Field(
        default=None,
        validation_alias="HSB_TEST_FIXTURE_URL",
    )
    fixture_path: Path | None = Field(
        default=None,
        validation_alias="HSB_TEST_FIXTURE_PATH",
    )
    live_codex: bool = Field(
        default=False,
        validation_alias="HSB_LIVE_CODEX",
    )
    test_work_item_id: str | None = Field(
        default=None,
        validation_alias="TEST_WORK_ITEM_ID",
    )
    linear_test_issue_id: str | None = Field(
        default=None,
        validation_alias="LINEAR_TEST_ISSUE_ID",
    )
