# hsb-test-fixture Repository (D-11)

**Owner:** hugo-hsbtech
**URL:** https://github.com/hugo-hsbtech/hsb-test-fixture
**Visibility:** public
**Created/confirmed:** 2026-05-06
**Used by:**
  - tests/integration/test_builder_agent.py (BLDR-01, BLDR-02, BLDR-04)
  - tests/integration/test_git_agent.py (GITA-01..04)

**Operator notes:**
  - GITHUB_TOKEN must have `repo` scope
  - Set HSB_TEST_FIXTURE_URL=https://github.com/hugo-hsbtech/hsb-test-fixture in .env
  - Wave 1 plans 03 and 04 will read this URL via `os.environ.get("HSB_TEST_FIXTURE_URL")`
  - Created autonomously by the execute-phase workflow on 2026-05-06 because the
    operator-facing checkpoint (Task 3 of Plan 02-01) was running in autonomous
    mode (no AskUserQuestion). gh CLI was authenticated as hugo-hsbtech with
    `repo` scope, so the workflow created the repo, pushed an initial fixture
    package (src/fixture/__init__.py, pyproject.toml, tests/test_placeholder.py),
    and recorded the URL here.
