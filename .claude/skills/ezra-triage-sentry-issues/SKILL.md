---
name: ezra-triage-sentry-issues
description: Triage Sentry error issues into Linear bug tickets with deduplication
---

# Sentry Issue Triage Skill

Automates bug ticket creation from Sentry error monitoring: discover recent issues by time window or provide specific URLs, deduplicate against existing Linear tickets tagged "Sentry Bugs", infer priority from impact metrics, and create/update Linear issues with stacktraces and evidence.

## For Developers

**When to use this:**

- Periodic triage of recent production errors (daily, weekly)
- After a deploy to check for new errors
- When you've spotted specific Sentry issues that need tracking

**What you need:**

1. Nothing — defaults to discovering unresolved errors from the last 24 hours
2. Or: a time window (`last hour`, `last 24h`, `last week`)
3. Or: specific Sentry issue URLs (`https://ezra-climate.sentry.io/issues/<id>/`)

**What it does:**

1. Fetches full issue details, stacktraces, and impact metrics from Sentry
2. Checks existing Linear tickets tagged "Sentry Bugs" to avoid duplicates
3. Assigns priority based on severity level, event frequency, and user impact
4. Creates structured tickets with error evidence and Sentry links
5. For duplicates, adds updated occurrence data as comments

**Review and approval:**

- Shows you the full plan (new tickets, updates, priorities) before executing
- You can modify priorities, skip issues, or reclassify duplicates
- Nothing posts to Linear until you explicitly approve

## Usage

**Discovery mode (default):**

```bash
/ezra-triage-sentry-issues                  # last 24h (default)
/ezra-triage-sentry-issues last hour
/ezra-triage-sentry-issues last 24h
/ezra-triage-sentry-issues last week
```

**Specific URLs:**

```bash
/ezra-triage-sentry-issues https://ezra-climate.sentry.io/issues/12345/
/ezra-triage-sentry-issues https://ezra-climate.sentry.io/issues/12345/ https://ezra-climate.sentry.io/issues/67890/
```

**With Seer AI analysis (slower, more detailed — works with either mode):**

```bash
/ezra-triage-sentry-issues last 24h --enrich
/ezra-triage-sentry-issues --enrich https://ezra-climate.sentry.io/issues/12345/
```

## Workflow

### Step 0: Parse Input & Determine Mode

Extract from `$ARGUMENTS`:

- `--enrich` flag (boolean) — strip from arguments
- Sentry issue URLs matching `https://ezra-climate.sentry.io/issues/<id>/` (also accept `https://sentry.io/organizations/ezra-climate/issues/<id>/`)
- Time window keywords: `last hour`, `last 24h`, `last week`
- Environment filters: quoted strings near "environment" keyword (e.g., `with "prod" or "production" environment tag`, `in the "dev" and "development" environments`). Extract environment names and build a Sentry filter: `environment:[env1,env2]` for use in Step 3a.

**Mode determination:**

- If URLs found → **URL mode** (skip discovery step)
- If time window found → **Discovery mode** with that window
- If no args or only `--enrich` → **Discovery mode** defaulting to `last 24h`

### Step 1: Load MCP Tools

Use `ToolSearch` with **`select:` syntax** (exact tool names) to load tools deterministically. Keyword search is unreliable for Linear tools. Batch in parallel:

**Sentry tools:**

- `select:mcp__sentry__whoami`
- `select:mcp__sentry__search_issues` (for discovery mode)
- `select:mcp__sentry__get_issue_details`
- `select:mcp__sentry__get_issue_tag_values`
- `select:mcp__sentry__analyze_issue_with_seer` (only if `--enrich`)

**Linear tools:**

- `select:mcp__claude_ai_Linear__list_issues`
- `select:mcp__claude_ai_Linear__create_issue`
- `select:mcp__claude_ai_Linear__create_comment`
- `select:mcp__claude_ai_Linear__list_issue_labels`
- `select:mcp__claude_ai_Linear__create_issue_label` (for first-run label bootstrapping)
- `select:mcp__claude_ai_Linear__get_team` (for team ID when creating labels)

### Step 2: Verify Authentication

Call `whoami()` to confirm Sentry MCP access. If fails, inform user and exit.

### Step 3: Discover or Resolve Issues

**Discovery mode:**

**3a. Search Sentry:**
Call `search_issues` with:
- `organizationSlug: "ezra-climate"`
- `naturalLanguageQuery: "is:unresolved"` plus any filters from Step 0 (e.g., `"is:unresolved environment:[prod,production]"`)
- `limit: 50`

**Multi-value filters:** Use bracket list notation for multiple values of the same field:
- `environment:[dev,development]` — matches either environment
- `environment:[prod,production]` — matches either environment
- `browser:[Chrome,Firefox]` — matches either browser
- Boolean `OR`/`AND` operators are **NOT supported** in Sentry search queries.

Then filter client-side by `lastSeen` timestamp against the requested time window:
- `last hour`: `lastSeen` within 1 hour of now
- `last 24h`: `lastSeen` within 24 hours of now
- `last week`: `lastSeen` within 7 days of now

**3b. Present Issue List:**
Display a numbered table for user selection. **Issue IDs MUST be markdown links** to the Sentry issue URL (from `permalink` or constructed as `https://ezra-climate.sentry.io/issues/<ID>/`) so users can click through to investigate before selecting.

```
Found <N> unresolved issues from <time-window>:

 #  | Project | Issue ID | Level   | Events | Users | Last Seen  | Title
----|---------|----------|---------|--------|-------|------------|------
 1  | APP     | [3F](https://ezra-climate.sentry.io/issues/CUSTOMER-APP-3F/) | error   | 1,204  | 89    | 2h ago     | TypeError: Cannot read properties of undefined
 2  | API     | [42](https://ezra-climate.sentry.io/issues/EZRA-API-42/) | error   | 342    | 15    | 5h ago     | ReferenceError: x is not defined
...

Select issues to triage (e.g., "1,3,5" or "1-5" or "all"), or "cancel" to exit:
```

**3c. User Selection:**
Wait for user to select which issues to triage. Parse their selection (comma-separated numbers, ranges, or "all"). If "cancel", exit gracefully.

**URL mode:**

Skip 3a-3c. Extract issue IDs directly from provided URLs.

**3d. Fetch Issue Details:**
For each selected issue, call `get_issue_details(issueUrl: <url>)` to fetch:

- `title` (error message)
- `type` (error type)
- `metadata` (error value, function name)
- `permalink` (Sentry URL)
- `status` (resolved, unresolved, ignored)
- `level` (fatal, error, warning, info)
- `count` (total event count)
- `userCount` (affected users)
- `firstSeen` (ISO timestamp)
- `lastSeen` (ISO timestamp)
- `culprit` (component/function path)
- Stacktrace frames from latest event

**Rate Limiting:**
Sentry API limits requests to 5/second. When fetching details for multiple issues:
- Batch `get_issue_details` calls in groups of 4 (leaving headroom)
- Similarly batch `get_issue_tag_values` calls
- Do NOT fire all detail requests in parallel

**3e. Fetch Tag Distributions (optional):**
Skip this step by default — issue details already include environment/browser tags from the latest event. Only fetch full tag distributions if `--detailed` flag is provided or if fewer than 5 issues are being triaged.

When fetching, call `get_issue_tag_values` for:

- `environment` — production vs staging distribution
- `browser` — browser breakdown
- `release` — which versions are affected

**3f. Optional Seer Analysis:**
If `--enrich` flag set, call `analyze_issue_with_seer(issueUrl: <url>)` for each issue:

- Returns root cause hypothesis and suggested code fixes
- Takes ~5-10s per issue
- If Seer fails for an issue, continue without it and note in output

**3g. Skip Resolved/Ignored Issues:**
Filter out issues where `status == "resolved"` or `status == "ignored"`. Inform user: "Skipping <N> resolved/ignored issues."

**3h. Store Issue Data:**
For each remaining issue, compile:

```
{
  id, title, type, level, count, userCount,
  firstSeen, lastSeen, culprit, permalink,
  stacktrace (top 3 frames),
  environments, browsers, releases,
  seerAnalysis (if enriched)
}
```

### Step 4: Fetch Existing Linear Tickets

**4a. Get or Create Label:**
Call `list_issue_labels(team: "Development", name: "Sentry Bugs")` to find the label. Store its ID.

If label doesn't exist:

- Auto-create it: `create_issue_label(name: "Sentry Bugs", color: "#eb5757", description: "Bug tickets auto-created from Sentry error monitoring", teamId: <dev-team-id>)`
- Use the returned label ID
- Inform user: "Created 'Sentry Bugs' label in Development team"

To get the team ID, call `get_team(query: "Development")` first.

**4b. List Tickets:**
Call `list_issues` with:

- `team: "Development"`
- `label: "Sentry Bugs"` (use label ID from 4a)
- `includeArchived: false`
- `limit: 100` (reduced to avoid exceeding tool output limits)

If result exceeds tool output limits, the output will be saved to a temp file. Use `grep` or Python to search for matching error types/messages rather than loading all descriptions into context.

**Shortcut — Sentry External Issue Links:** Before querying Linear, check each Sentry issue's details for "External Issue Links" — if a Linear ticket is already linked, that's an authoritative duplicate signal that doesn't require description matching.

**4c. Paginate if Needed:**
Check `hasNextPage` in response. If true, repeat call with `cursor` from response. Collect all pages.

**4d. Filter Out Closed:**
Client-side filter: exclude tickets where `state.name` is "Done", "Canceled", or "Duplicate".

**4e. Extract Ticket Data:**
For each remaining ticket, note:

- `id` (UUID)
- `identifier` (e.g., "DEV-123")
- `title`
- `description` (full markdown text — use for deduplication)
- `state.name` (current status)

Store as deduplication database.

### Step 5: Deduplicate

For each Sentry issue from Step 3:

**5a. Cross-Check Within Input Batch:**
Check if multiple URLs in current input describe the same underlying error. Group these together (will become single ticket with multiple issue references).

**5b. Check Against Existing Tickets:**
For each unique issue (after 5a grouping), compare against existing tickets using LLM judgment:

**Comparison criteria:**

- Same error type (e.g., both "TypeError")
- Same or similar error message
- Same culprit/file path
- Overlapping stacktrace frames

**Classification:**

- **DUPLICATE** — clearly the same error (even if wording differs)
- **RELATED** — similar component but distinct error (e.g., same file, different exception)
- **NEW** — no match found

**Ambiguous cases:**
If confidence < 80%, mark as "POTENTIAL_DUPLICATE" with note explaining uncertainty. Will present to user in Step 7.

**Output structure:**

```
Issue: [<error-type>] <error-message>
Impact: <count> events, <userCount> users
Dedup Result: DUPLICATE of DEV-123 | RELATED to DEV-456 | NEW | POTENTIAL_DUPLICATE of DEV-789 (reason)
```

### Step 6: Infer Priority

For each NEW issue, assign priority based on Sentry metrics:

**Priority 1 (Urgent):**

- `level == "fatal"` OR
- `level == "error"` AND (`count / days_active > 100` OR `userCount > 50`)
- Keywords in title: "crash", "cannot load", "timeout", "failed to fetch"

**Priority 2 (High):**

- `level == "error"` AND (`count / days_active > 10` OR `userCount > 10`)
- Keywords: "uncaught", "unhandled", "exception"

**Priority 3 (Normal):**

- `level == "warning"` OR
- `level == "error"` AND low frequency (`count / days_active < 10`)
- Keywords: "deprecated", "validation", "missing"

**Priority 4 (Low):**

- `level == "info"` OR
- Single occurrence (`count == 1`) OR
- Dormant (`lastSeen` > 30 days ago with no recent activity)

**Special case:** If `--enrich` was used and Seer analysis indicates security or data-loss risk, override to Priority 1.

Document 1-sentence justification for each priority assignment.

### Step 7: Build Action Plan

Compile full list:

**New Tickets:**

```
CREATE: [<error-type>] <short-title>
Priority: <1-4> (<label>)
Justification: <1-sentence>
Impact: <count> events, <userCount> users
Environments: <env-list>
```

**Duplicate Updates:**

```
UPDATE: DEV-123 — <existing-title>
Action: Add comment with updated occurrence data
Recent Activity: Last seen <timestamp>, <count> total events
```

**Related (No Action):**

```
RELATED: DEV-456 — <existing-title>
Note: Similar component, different error. Mentioned as context only.
```

### Step 8: Present for Confirmation

Output action plan from Step 7 with full details:

**For each NEW ticket, show:**

- Full title
- Priority (number + label) with justification
- Impact metrics (events, users, date range)
- Stacktrace preview (first 3 frames)
- Environment/browser/release distributions
- Sentry permalink
- Seer analysis summary (if enriched)

**For each DUPLICATE, show:**

- Existing ticket identifier and title
- Comment to be added (using template below)
- Updated metrics

**For POTENTIAL_DUPLICATE, show:**

- Issue description and metrics
- Possibly matching ticket with confidence reasoning
- Ask: "Treat as duplicate? Create new? Skip?"

**Prompt:**

```
Review the above plan. Options:
- Approve all: proceed with all creates/updates
- Modify: specify changes (e.g., "Change issue #2 priority to 1", "Skip issue #3", "Treat issue #4 as duplicate of DEV-789")
- Cancel: exit without changes

Your response:
```

**Wait for explicit user approval.** Do not proceed to Step 9 without confirmation.

Accept modifications:

- Priority changes
- Reclassifying NEW ↔ DUPLICATE
- Skipping specific issues
- Editing titles

### Step 9: Execute

Upon confirmation, execute all approved actions:

**For NEW tickets:**

Call `create_issue` with:

```json
{
  "title": "[<error-type>] <concise-message>",
  "team": "Development",
  "description": "<formatted per template below>",
  "priority": <1-4>,
  "labels": ["Sentry Bugs"],
  "state": "Triage",
  "links": [
    {
      "url": "<sentry-permalink>",
      "title": "Sentry Issue"
    }
  ]
}
```

**For DUPLICATE updates:**

Call `create_comment` with:

```json
{
  "issueId": "<existing-ticket-id>",
  "body": "<formatted per duplicate template below>"
}
```

**Error handling:**

- If a single ticket create/update fails, log error and continue with remaining
- Report all failures in Step 10 summary

### Step 10: Report

Output summary:

```
✓ Created <N> new tickets:
  - DEV-XXX: [TypeError] <title> (Priority <N>)
  - DEV-YYY: [ReferenceError] <title> (Priority <N>)

✓ Updated <M> existing tickets with new occurrence data:
  - DEV-ZZZ: <title>

✗ Failed actions (if any):
  - Issue <id> ("[title]"): <error-message>

Next steps:
- Review new tickets in Triage view
- Assign owners and adjust priorities as needed
```

## Templates

### New Ticket Description

```markdown
## Bug Report (from Sentry Issue)

### Error Summary

**Type:** <error-type>
**Message:** <error-message>

### Impact

- **Event Count:** <count> occurrences
- **Affected Users:** <userCount> unique users
- **First Seen:** <firstSeen>
- **Last Seen:** <lastSeen>
- **Frequency:** ~<events-per-day> events/day

### Environment Distribution

| Environment | Percentage |
| ----------- | ---------- |
| <env-name>  | <percent>% |

### Stack Trace (Most Recent Event)
```

<stacktrace-frame-1>
<stacktrace-frame-2>
<stacktrace-frame-3>
... (<N> more frames)
```

### Additional Context

**Browser Distribution:**

- <browser-1>: <percent>%
- <browser-2>: <percent>%

**Release Versions:**

- <version-1>: <percent>%
- <version-2>: <percent>%

**Component:** `<culprit>`

<If enriched:>
### Seer AI Analysis

**Root Cause:**
<seer-root-cause>

**Suggested Fix:**
<seer-code-fix>
</If enriched>

### Priority Justification

<1-sentence explanation from Step 6>

---

_Auto-generated by `/ezra-triage-sentry-issues` · [View in Sentry](permalink)_

````

### Duplicate Comment

```markdown
## Updated Occurrence Data

This error is still occurring. Latest metrics:

- **Total Events:** <count> (+<delta> since ticket created)
- **Affected Users:** <userCount>
- **Latest Occurrence:** <lastSeen>
- **Current Frequency:** ~<events-per-day> events/day

### Environment Changes
<If distribution changed:>
- **Newly Affected:** <new-envs>
- **Distribution Shift:** <describe-change>

<If no change:>
No significant environment distribution changes.

### Stack Trace (Latest Event)
````

<stacktrace-frame-1>
<stacktrace-frame-2>
<stacktrace-frame-3>
```

<If enriched:>
### Seer AI Analysis
<seer-analysis>
</If enriched>

---

_Updated by `/ezra-triage-sentry-issues` · [View in Sentry](permalink)_

```

## Edge Cases

### Label Doesn't Exist
Step 4a handles: auto-create "Sentry Bugs" label in Development team. Requires `create_issue_label` and `get_team` tools.

### All Issues Are Duplicates
Step 9 handles: only execute comment creates, skip ticket creation. Report "0 new tickets created" in Step 10.

### Ambiguous Deduplication
Step 5b handles: mark as POTENTIAL_DUPLICATE, present to user in Step 8 for decision.

### Search Returns No Results
Step 3a handles: "No unresolved issues found in <time-window>. Try a wider window (e.g., `last week`)."

### Search Returns Too Many Results
Step 3a handles: show first 50 results, suggest narrowing the time window.

### User Selects None
Step 3c handles: if user types "cancel" or selects no issues, exit gracefully.

### Unparseable Input
Step 0 handles: explain expected format with examples, exit. Never proceed with incomplete parsing.

### >250 Existing Tickets
Step 4c handles: paginate using `cursor` until `hasNextPage: false`.

### Empty Stacktrace
If issue has no stacktrace (e.g., captured message without exception), use title and culprit for deduplication. Note in ticket: "No stacktrace available."

### Seer Analysis Unavailable
If `--enrich` flag set but Seer fails for an issue, continue without analysis. Note in ticket: "Seer analysis unavailable."

### Dormant Issues Resurfacing
If `firstSeen` > 90 days ago but `lastSeen` within 7 days, note in ticket: "Issue resurfaced after dormant period."

### Multiple Sentry Issues, Same Root Cause
Step 5a handles: group issues from input that match the same error into a single ticket referencing all Sentry issue IDs.

### API Errors
Step 9 handles: catch per-ticket errors, log, continue. Report failures in Step 10.

### Resolved/Ignored Issues
Step 3e handles: skip and inform user. Do not create tickets for resolved or ignored issues.

### Invalid URL Format
Step 1 handles: reject URLs not matching expected pattern. Show expected format.

## Notes

- Sentry issue IDs are numeric (e.g., `12345`), extracted from URL path
- Organization slug: `ezra-climate`
- Supports both frontend (`javascript-nextjs`) and backend (`temporal-worker`) projects — auto-detected from issue metadata
- Event count vs user count: event count can be much higher (one user triggering error repeatedly)
- Frequency calculation: `count / max(1, days between firstSeen and now)` to normalize
- Linear team "Development" has identifier prefix "DEV"
- Priority values: 1=Urgent, 2=High, 3=Normal, 4=Low (Linear numeric system)
- Always link Sentry issue via `links` array on `create_issue`, not just in description
- Triage state ensures tickets appear in default triage view for team review
- Enrichment with Seer is opt-in (`--enrich`) due to latency — recommend for critical issues only
- Deduplication uses `description` field from `list_issues` (no need for separate `get_issue` calls unless description is truncated)
```
