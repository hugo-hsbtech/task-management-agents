# Phase 1 — Human Setup Guide

This is a one-time setup. After completing it, the integration tests in `tests/test_integration.py` will run against a live Linear workspace.

## Step 1 — Get an Anthropic API key

1. Visit https://platform.claude.com
2. Settings → API Keys → Create new key
3. Copy the key (starts with `sk-ant-...`)
4. Add to `.env` (NOT `.env.example`):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
The `.env` file is gitignored. Do NOT commit it.

## Step 2 — Complete Linear OAuth (one-time interactive)

The Linear MCP server (`mcp.linear.app`) uses OAuth 2.1. The first call opens a browser tab; the token is cached at `~/.mcp-remote/`.

From a browser-available environment:
```bash
source .venv/bin/activate
python -c "import asyncio; from hsb.agents.linear_agent import run_linear_agent; asyncio.run(run_linear_agent('List Linear teams. Return JSON: {\"operation\":\"read\",\"result\":\"success\",\"linear_entities\":[],\"error\":null}'))"
```

A browser tab opens → log into Linear → grant access → close tab. The Python call completes and prints the agent's tool calls. Subsequent calls reuse the cached token.

## Step 3 — Find your Linear team ID

Linear → Settings → Workspace → Teams → click your team. The URL contains the team ID. Set it for tests:
```bash
export LINEAR_TEST_TEAM_ID=<your-team-id>
```

## Step 4 — Create a sandbox test issue

In Linear, create a single test issue you don't mind being mutated repeatedly. Note its ID (`LIN-XXX`):
```bash
export LINEAR_TEST_ISSUE_ID=LIN-XXX
```

## Step 5 — Run integration tests

```bash
source .venv/bin/activate
pytest tests/test_integration.py -x -m integration -v
```

Expected: all 9 tests pass (1 FOUND-01 connection test, 4 LINR-01 hierarchy tests covering EPIC / User Story / Task / Subtask, 2 LINR-02 update tests for status and custom fields, 1 LINR-03 comment test, 1 LINR-04 PR link test).

## Step 5b — Manual UI verification of LINR-02 custom fields

After `test_update_issue_custom_fields` passes, open `LINEAR_TEST_ISSUE_ID` in the Linear web UI (https://linear.app/.../issue/LIN-XXX). Visually confirm at least one of the following is present (whichever mechanism the agent selected per RESEARCH.md OQ1 resolution):
- A native custom field labeled `qa_status` showing `approved` (best case)
- A Linear label `qa_status:approved` on the issue (label fallback)
- A comment containing `<!-- qa_status: approved -->` or `qa_status=approved` (structured-comment fallback)

Repeat for `uat_status: approved` and `assigned_orchestrator: phase-1-test`. This step closes the loop on LINR-02 — the integration test verifies the agent did not error, this manual step verifies the data actually landed where humans can read it.

## Troubleshooting

- **Browser doesn't open / OAuth blocks indefinitely:** You're on a headless box. Either run Step 2 on your laptop first (the cached token at `~/.mcp-remote/` is reusable) or set `LINEAR_API_KEY` in `.env` (deferred per D-01)
- **`hsb --help` works but `pytest tests/test_integration.py` skips everything:** Check that the env vars are exported in the same shell as your pytest run
- **`mcp__claude_ai_Linear__*` tool not found errors:** This is Pitfall 1 — wrong prefix. Verify `.mcp.json` has lowercase `"linear"` key (Plan 01 acceptance criterion)
