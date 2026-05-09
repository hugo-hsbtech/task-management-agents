---
name: ezra-create-linear-ticket
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Create well-structured Linear tickets via MCP following Ezra's hierarchy (Initiative > Project > Issue > Sub-Issue). Use when creating tickets, filing bugs, breaking down features, or converting Slack threads into Linear issues. Triggers on "create ticket", "file issue", "linear ticket", "track this".
---

# Create Linear Ticket

You are tasked with creating a Linear ticket based on conversation context, a Slack thread, or user-provided requirements. All tickets must follow Ezra's Linear hierarchy: Initiative > Project > Issue > Sub-Issue.

## Important

- **Always query teams via API** — never guess or ask the user to type one
- **Always get user approval** before creating the ticket
- **Include file paths** in the Solution section when the fix is code-related
- **Don't over-describe** — the ticket should be scannable, not exhaustive
- **Enforce the hierarchy** — every issue belongs to a project, every project belongs to an initiative. Flag deviations explicitly.
- **Default new tickets to Triage status** — unless the user gives clear timing context (e.g., "we're starting this next week" → To-Do). See Quick Reference table.
- **AI-adjusted timelines** — when estimating effort, factor in that the team uses AI tools (Claude Code, copilots) for research and implementation. Work that would traditionally take 3 days may take 1 with AI assistance. Reflect this in scoping and timeline suggestions.

## Process

### 1. Gather context

- Review the conversation history to understand what ticket is needed
- If the user provided a Slack thread, plan document, or other source material, extract the key details
- Identify: what's the problem, what's the proposed solution, and how to verify the fix

### 2. Load Linear MCP tools

Use ToolSearch with `select:` to load the required tools:
- `select:mcp__claude_ai_Linear__list_teams` — to discover valid team names
- `select:mcp__claude_ai_Linear__list_projects` — to discover projects for the selected team
- `select:mcp__claude_ai_Linear__list_initiatives` — to discover strategic initiatives
- `select:mcp__claude_ai_Linear__list_issues` — for deduplication search
- `select:mcp__claude_ai_Linear__save_issue` — to create the ticket
- `select:mcp__claude_ai_Linear__save_comment` — to update duplicates
- `select:mcp__claude_ai_Linear__list_issue_labels` — for cross-cutting concern labels

### 3. Discover the team

Query `list_teams` and present options to the user via AskUserQuestion rather than asking them to type a team name freeform.

### 4. Select an initiative

Query `list_initiatives` and identify which strategic theme the work falls under. Note: `list_initiatives` returns workspace-wide results (no team filter). If the list is large, narrow by relevance to the ticket topic and present only the top 3-5 matches.

1. Review the returned initiatives and identify any that are relevant based on name and description.
2. Present options to the user via AskUserQuestion:
   - List relevant initiatives with the most relevant first, marked "(Recommended)".
   - Include a "None / no initiative" option — but warn that this is non-standard per team conventions.
3. If no initiative fits, suggest the user create one in Linear or assign to a catch-all like "Platform Health."

### 5. Select a project

Query `list_projects` filtered to the selected team (`team` parameter) and excluding archived projects. If an initiative was selected, prioritize projects under that initiative.

1. Review the returned projects and identify any that are relevant to the ticket's topic based on project name and description.
2. Present options to the user via AskUserQuestion:
   - If relevant projects were found, list them as options with the most relevant first, marked "(Recommended)".
   - Include a "None / no project" option — but warn that every issue should belong to a project per team conventions.
   - The user can also select "Other" to type a project name manually (including one that doesn't exist yet).
3. If the user provides a project name that doesn't exist, note it in the draft — the user will need to create the project in Linear before (or after) the ticket is created.
4. **Two-week rule:** if the described work sounds like it would exceed 2 weeks (accounting for AI-assisted development speed), suggest breaking it into sequential projects rather than one large project. For work that fits within one project/issue but has multiple implementation steps, see Step 8 (sub-issue breakdown).

### 6. Check for existing tickets (deduplication)

Before drafting, search Linear for potential duplicates:

1. Extract 2-3 key terms from the problem description
2. Call `list_issues` with `team` set to the selected team and `query` using those key terms
3. Compare results using LLM judgment — look for same component, same symptoms, or same root cause
4. Classify each match:
   - **DUPLICATE** — clearly the same issue. Present the existing ticket to the user and ask whether to skip, add a comment with new context, or create anyway.
   - **RELATED** — similar area but distinct problem. Mention it when presenting the draft so the user can link them if desired.
   - **NO MATCH** — proceed to drafting.

If a duplicate is confirmed, call `save_comment` on the existing ticket with any new context from this request, then report the existing ticket identifier and stop.

### 7. Draft the ticket

**Title conventions:**
- Imperative mood, under 80 characters
- Describe the outcome, not the activity
- Good: "Consolidate health check to test DB connectivity"
- Bad: "Update health check endpoint" (too vague)

**Priority mapping:**
| Value | Label  | When to use                                    |
|-------|--------|------------------------------------------------|
| 1     | Urgent | Production is down or severely degraded        |
| 2     | High   | Should fix soon, impacts users or deployments  |
| 3     | Medium | Next sprint, standard work                     |
| 4     | Low    | Backlog, nice-to-have                          |

**Labels — cross-cutting concerns:**

Prompt for labels when relevant. Labels are for concerns that span multiple initiatives or projects. Good labels:
- Work type: `bug`, `tech-debt`, `spike`
- Regulatory: `compliance`, `security`
- External: `blocked-external`

Do NOT use labels that duplicate what the initiative/project hierarchy already conveys.

**Status:** Default to **Triage** for new tickets. Override when the user provides clear timing context — see Quick Reference table below. The product team owns reviewing and moving Triage tickets into the workflow.

**Description template:**
```markdown
## Problem

[What's broken or missing. Include enough context for someone unfamiliar with the issue. Reference specific incidents if applicable.]

## Solution

[Concrete steps with file paths. Be specific about what code changes are needed.]

## Verification

[How to confirm the fix works — commands to run, endpoints to test, etc.]
```

### 8. Assess sub-issue breakdown

If the described work has multiple distinct implementation steps:

1. Identify natural sub-tasks (each should be a concrete, independently completable step within the parent issue).
2. Propose them to the user: "This looks like it has N implementation steps. Want me to create sub-issues for each?"
3. Sub-issues are for breaking down steps **within** an issue — not for tracking separate features (those should be their own issues).
4. If the user agrees, include the proposed sub-issues in the approval summary (Step 9). Do not create them yet.

### 9. Present to user for approval

Before creating the ticket, show the user:
- Title
- Team
- Initiative
- Project (or "None" with a warning)
- Priority
- Labels (if any)
- Status (Triage)
- Full description
- Proposed sub-issues (if any)

Ask: "I'll create this ticket. Shall I proceed?"

### 10. Create and report

- Call `save_issue` with the approved details (include `project` and `initiative` if selected, set status to Triage)
- If sub-issues were approved, create each one linked to the parent
- Return the ticket URL and identifier (e.g., "Created DEV-2091")
- If sub-issues were created, list them with their identifiers

## Quick Reference

Use this to determine the right status and action based on what the user describes:

| Scenario                              | What to Do                                                      |
|---------------------------------------|-----------------------------------------------------------------|
| New idea or piece of work             | Create an issue, set status to **Triage**                       |
| Planned but not starting soon         | Set status to **Backlog**; assign priority if known             |
| Starting within the next two weeks    | Set status to **To-Do**; must have a priority                   |
| Something is blocking progress        | Set status to **Blocked**; add a comment explaining why         |
| Work is done and being reviewed       | Set status to **In Review**                                     |
| Work is complete                      | Set status to **Done**                                          |
| Work is no longer relevant            | Set status to **Cancelled**; add a brief note                   |

When unsure, default to **Triage** — let the product team decide where it goes.

## Examples

**Simple bug report:**
User: "The health check endpoint returns 200 even when the DB is down"
Result: Single issue under the relevant project, labeled `bug`, priority High, Triage status.

**Multi-step feature:**
User: "We need to add email ingestion — inbound and outbound"
Result: Parent issue "Add email ingestion" with sub-issues "Implement inbound email ingestion" and "Implement outbound email ingestion."

**Large effort:**
User: "We need to rebuild the entire auth system"
Result: Skill flags this exceeds 2 weeks, suggests breaking into sequential projects (e.g., "Auth: Token Migration", "Auth: Session Management Rewrite").

## Troubleshooting

- **No matching initiative:** suggest the user create one in Linear or use a catch-all. Don't silently skip.
- **No matching project:** same — suggest creation. Every issue should have a project.
- **Duplicate found:** always present to the user. Never silently skip or silently create anyway.
- **Tool not found:** re-run ToolSearch with the exact `select:` query. MCP tools must be loaded before use.
