---
name: ezra-triage-posthog-sessions
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Triage PostHog session recordings into Linear bug tickets with deduplication
---

# PostHog Session Triage Skill

Automates bug ticket creation from PostHog session reviews: parse observations, deduplicate against existing tickets, create/update Linear issues with proper labels and session links.

## For Developers

**When to use this:**

- After reviewing PostHog session recordings
- When you've identified multiple bugs across one or more sessions
- When you want to batch-create tickets instead of manually filing each one

**What you need:**

1. PostHog session URLs (format: `https://us.posthog.com/project/<id>/replay/<replay-id>`)
2. For each bug: timestamp where it occurs (MM:SS or HH:MM:SS)
3. Brief description of what went wrong

**What it does:**

1. Parses your observations and groups bugs by session
2. Checks existing Linear tickets tagged "PostHog Session Bugs" to avoid duplicates
3. Assigns priority automatically based on severity (crash = urgent, UI glitch = normal)
4. Creates structured tickets with session evidence tables and recording links
5. For duplicates, adds new session evidence as comments

**Review and approval:**

- Shows you the full plan (new tickets, updates, priorities) before executing
- You can modify priorities, skip issues, or reclassify duplicates
- Nothing posts to Linear until you explicitly approve

## Usage

**Command:**

```bash
/ezra-triage-posthog-sessions
```

**Input format:**

```
Posthog session link: <session-url-1>
- [ ] At minute MM:SS
    - [ ] Bug description here

Posthog session link: <session-url-2>
- [ ] At minute MM:SS
    - [ ] Another bug description
- [ ] At minute HH:MM:SS
    - [ ] Third bug description
```

**Example:**

```
Posthog session link: https://us.posthog.com/project/240576/replay/019c0625-6c74-7cf4-8b4c-2dca471490b8
- [ ] At minute 02:15
    - [ ] User clicks "Generate Report" but nothing happens, no loading state shown
- [ ] At minute 03:42
    - [ ] Deal name field allows special characters that break downstream PDF generation

Posthog session link: https://us.posthog.com/project/240576/replay/019c1103-0c60-78aa-a9ad-60ca4f01aea4
- [ ] At minute 05:10
    - [ ] "Save Draft" button remains enabled after save completes, no visual feedback
```

**Tip:** Copy session URLs directly from PostHog, then add your timestamped observations as you watch each recording.

## Workflow

### Step 0: Input Check

If `$ARGUMENTS` is empty, output the usage instructions above and exit. Wait for user to provide input.

### Step 1: Parse Input

Extract from `$ARGUMENTS`:

- Session URLs (all PostHog replay URLs in the format `https://us.posthog.com/project/<project-id>/replay/<replay-id>`)
- Per session: list of issues with timestamp and description

**Parse rules:**

- Blank lines separate sessions
- First line of each block = session URL
- Following lines starting with `-` = issues (must have `[HH:MM:SS]` timestamp)
- Ignore lines without timestamp format

Present parsed result:

```
Found <N> sessions with <M> total issues:

Session 1: <session-url-short>
- [00:02:15] <description>
- [00:03:42] <description>

Session 2: <session-url-short>
- [00:01:30] <description>

Proceed with triage? (y/n)
```

If parsing fails or format unclear, explain the expected format and exit. Never guess at malformed input.

### Step 2: Load Linear MCP Tools

Use `ToolSearch` with **`select:` syntax** (exact tool names) to load tools deterministically. Keyword search is unreliable for Linear tools. Batch in parallel:

- `select:mcp__claude_ai_Linear__list_issues`
- `select:mcp__claude_ai_Linear__create_issue`
- `select:mcp__claude_ai_Linear__create_comment`
- `select:mcp__claude_ai_Linear__list_issue_labels`
- `select:mcp__claude_ai_Linear__create_issue_label` (for first-run label bootstrapping)
- `select:mcp__claude_ai_Linear__get_team` (for team ID when creating labels)
- `select:mcp__claude_ai_Linear__get_issue`

### Step 3: Fetch Existing Tickets

**3a. Get or Create Label:**
Call `list_issue_labels(team: "Development")` and find "PostHog Session Bugs" label. Store its ID.

If label doesn't exist:

- Auto-create it: `create_issue_label(name: "PostHog Session Bugs", color: "#9b59b6", description: "Bug tickets auto-created from PostHog session reviews", teamId: <dev-team-id>)`
- To get the team ID, call `get_team(query: "Development")` first.
- Use the returned label ID.
- Inform user: "Created 'PostHog Session Bugs' label in Development team"

**3b. List Tickets:**
Call `list_issues` with:

- `team: "Development"`
- `label: "PostHog Session Bugs"` (use label ID from 3a)
- `includeArchived: false`
- `limit: 100`

If result exceeds tool output limits, the output will be saved to a temp file. Use `grep` or Python to search for matching descriptions rather than loading all into context.

**3c. Paginate if Needed:**
Check `hasNextPage` in response. If true, repeat call with `cursor` from response. Collect all pages.

**3d. Filter Out Closed:**
Client-side filter: exclude tickets where `state.name` is "Done", "Canceled", or "Duplicate".

**3e. Extract Ticket Data:**
For each remaining ticket, note:

- `id` (UUID)
- `identifier` (e.g., "DEV-123")
- `title`
- `description` (full markdown text - use for deduplication)
- `state.name` (current status)

Store as deduplication database.

### Step 4: Deduplicate

For each issue in parsed input:

**4a. Cross-Check Within Input Batch:**
First, check if multiple sessions in current input describe the same bug. Group these together (will become single ticket with multiple session evidence rows).

**4b. Check Against Existing Tickets:**
For each unique issue (after 4a grouping), compare against existing tickets using LLM judgment:

**Targeted search:** For each unique issue, extract 2-3 key terms from the description and call `list_issues` with `team: "Development"` and `query` using those terms. Merge any new results (not already in the Step 3 dedup database) before applying LLM comparison. This catches tickets that may not have the "PostHog Session Bugs" label but describe the same bug.

**Comparison criteria:**

- Same UI element/component affected
- Same symptoms/behavior
- Same user action sequence
- Similar error conditions

**Classification:**

- **DUPLICATE** - clearly the same bug (even if wording differs)
- **RELATED** - similar area but distinct issue (e.g., same form, different field bugs)
- **NEW** - no match found

**Ambiguous cases:**
If confidence < 80%, mark as "POTENTIAL_DUPLICATE" with note explaining uncertainty. Will present to user in Step 7.

**Output structure:**

```
Issue: <description>
Sessions: <session-id-short> @ <timestamp>, <session-id-short-2> @ <timestamp-2>
Dedup Result: DUPLICATE of DEV-123 | RELATED to DEV-456 | NEW | POTENTIAL_DUPLICATE of DEV-789 (reason)
```

### Step 5: Infer Priority

For each NEW issue, assign priority based on severity signals:

**Priority 1 (Urgent):**

- Application crash/freeze
- Data loss or corruption
- Security vulnerability
- Critical user path completely blocked
- Keywords: "crash", "error", "broken", "can't", "blocks", "data loss"

**Priority 2 (High):**

- Major feature not working as designed
- Incorrect data displayed
- Workflow disruption requiring workaround
- Keywords: "doesn't work", "wrong", "incorrect", "fails"

**Priority 3 (Normal):**

- UI glitches or visual bugs
- Minor usability friction
- Missing feedback (loading states, confirmations)
- Keywords: "no feedback", "unclear", "confusing", "slow"

**Priority 4 (Low):**

- Cosmetic issues
- Edge cases
- Nice-to-have improvements
- Keywords: "could", "should", "minor", "edge case"

Document 1-sentence justification for each priority assignment.

### Step 6: Build Action Plan

Compile full list:

**New Tickets:**

**Title conventions for NEW tickets:**

- Imperative mood, under 80 characters
- Describe the symptom/outcome, not the activity
- Good: "Fix missing loading state on Generate Report button"
- Bad: "Button bug" (too vague)

```
CREATE: <title>
Priority: <1-4> (<label>)
Justification: <1-sentence>
Sessions: <count> recordings linked
```

**Duplicate Updates:**

```
UPDATE: DEV-123 - <existing-title>
Action: Add comment with new session evidence
Sessions: <count> new recordings
```

**Related (No Action):**

```
RELATED: DEV-456 - <existing-title>
Note: Mentioned as related context, no automatic action
```

### Step 7: Present for Confirmation

Output action plan from Step 6 with full details:

**For each NEW ticket, show:**

- Title
- Priority (number + label)
- Priority justification
- Full description (using template below)
- Number of sessions linked

**For each DUPLICATE, show:**

- Existing ticket identifier and title
- Comment to be added (using template below)
- Number of new sessions

**For POTENTIAL_DUPLICATE, show:**

- Issue description
- Possibly matching ticket with reasoning
- Ask: "Treat as duplicate? Create new? Skip?"

**Prompt:**

```
Review the above plan. Options:
- Approve all: proceed with all creates/updates
- Modify: specify changes (e.g., "Change DEV-123 priority to 2", "Skip issue #3", "DEV-456 is actually a duplicate of DEV-789")
- Cancel: exit without changes

Your response:
```

**Wait for explicit user approval.** Do not proceed to Step 8 without confirmation.

Accept modifications:

- Priority changes
- Reclassifying NEW ↔ DUPLICATE
- Skipping specific issues
- Editing titles/descriptions

### Step 8: Execute

Upon confirmation, execute all approved actions:

**For NEW tickets:**

Call `create_issue` with:

```json
{
  "title": "<concise title>",
  "team": "Development",
  "description": "<formatted per template below>",
  "priority": <1-4>,
  "labels": ["PostHog Session Bugs"],
  "state": "Triage",
  "links": [
    {
      "url": "<session-url-1>",
      "title": "PostHog Session Recording"
    },
    {
      "url": "<session-url-2>",
      "title": "PostHog Session Recording"
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
- Report all failures in Step 9 summary

### Step 9: Report

Output summary:

```
✓ Created <N> new tickets:
  - DEV-XXX: <title> (Priority <N>)
  - DEV-YYY: <title> (Priority <N>)

✓ Updated <M> existing tickets with new evidence:
  - DEV-ZZZ: <title>

✗ Failed actions (if any):
  - Issue "<description>": <error-message>

Next steps:
- Review new tickets in Triage view
- Assign priorities/owners as needed
```

## Templates

### New Ticket Description

```markdown
## Bug Report (from PostHog Session Review)

### What Happens

<description of observed bug from input>

### Session Evidence

| Session                       | Timestamp  | Link                                  |
| ----------------------------- | ---------- | ------------------------------------- |
| <last-8-chars-of-replay-id>   | <HH:MM:SS> | [Watch recording](full-posthog-url)   |
| <last-8-chars-of-replay-id-2> | <HH:MM:SS> | [Watch recording](full-posthog-url-2) |

### Severity Assessment

<1-sentence justification for priority from Step 5>

### Additional Context

<any extra observations from the session review, environmental factors, user context>

---

_Auto-generated by `/ezra-triage-posthog-sessions`_
```

### Duplicate Comment

```markdown
## Additional Session Evidence

This bug was observed again in a PostHog session review:

| Session                     | Timestamp  | Link                                |
| --------------------------- | ---------- | ----------------------------------- |
| <last-8-chars-of-replay-id> | <HH:MM:SS> | [Watch recording](full-posthog-url) |

### Observation Notes

<new context from this sighting - any differences in symptoms, user behavior, environment>

---

_Added by `/ezra-triage-posthog-sessions`_
```

## Edge Cases

### Label Doesn't Exist

Step 3a handles: auto-create "PostHog Session Bugs" label in Development team. Requires `create_issue_label` and `get_team` tools.

### All Issues Are Duplicates

Step 8 handles: only execute comment creates, skip ticket creation. Report "0 new tickets created" in Step 9.

### Ambiguous Deduplication

Step 4b handles: mark as POTENTIAL_DUPLICATE, present to user in Step 7 for decision.

### Unparseable Input

Step 1 handles: explain expected format, exit. Never proceed with incomplete parsing.

### >250 Existing Tickets

Step 3c handles: paginate using `cursor` until `hasNextPage: false`.

### Multiple Sessions, Same Bug

Step 4a handles: group issues from different sessions into single ticket with multiple evidence rows.

### API Errors

Step 8 handles: catch per-ticket errors, log, continue. Report failures in Step 9.

### Empty Description Field

If existing ticket has null/empty `description`, treat as no match for deduplication (cannot compare).

### Session URL Formats

Only accept `https://us.posthog.com/project/<id>/replay/<id>`. Reject other domains/formats in Step 1.

## Notes

- Session ID abbreviation: use last 8 characters of replay UUID for readability in tables
- Deduplication uses `description` field from `list_issues` (no need for separate `get_issue` calls)
- Linear team "Development" has identifier prefix "DEV"
- Priority values: 1=Urgent, 2=High, 3=Normal, 4=Low (Linear numeric system)
- Always link session recordings via `links` array on `create_issue`, not just in description
- Triage state ensures tickets appear in default triage view for team review
