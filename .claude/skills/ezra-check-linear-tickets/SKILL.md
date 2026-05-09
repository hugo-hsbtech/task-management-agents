---
name: ezra-check-linear-tickets
description: Check active Linear tickets with comprehensive status overview
---

# Check Linear Tickets

Review your active Linear tickets with a comprehensive, grouped status overview that catches tickets other queries miss.

## Process

### 1. Load Linear MCP tools

Use ToolSearch with `select:` to load:

- `select:mcp__claude_ai_Linear__list_issues`
- `select:mcp__claude_ai_Linear__get_user`

### 2. Query broadly

Run two parallel queries — **never use a state filter**, as that misses Triage, Backlog, and other non-"started" statuses:

1. **Assigned tickets:** `list_issues(assignee: "me", includeArchived: false, limit: 100)`
2. **Created-by-me tickets:** `list_issues(query: "", limit: 50, includeArchived: false)` — then filter results client-side to match the user's `createdBy` email (use `get_user(query: "me")` to get the email)

> **Why no state filter?** Linear's `state: started` only returns In Progress and In Review. Triage, Backlog, Todo, and Upcoming are all excluded. Always filter client-side.

### 3. Client-side filter

From the combined results:

- **Exclude:** Done, Canceled, Duplicate statuses
- **Deduplicate:** Merge the two queries by issue ID

### 4. Group by status

Present tickets grouped by status in this priority order:

1. **In Progress**
2. **In Review**
3. **Triage** (may need status update)
4. **Todo**
5. **Backlog**
6. **Upcoming**

Within each group, sort by priority (Urgent → High → Normal → Low).

### 5. Output format

Display a summary table per status group:

```
### In Progress (2)
| Ticket   | Title                              | Priority | Project        |
|----------|------------------------------------|----------|----------------|
| DEV-2149 | Build Supabase-to-S3 Migration     | Medium   | Infrastructure |
| DEV-2100 | Fix health check endpoint          | High     | —              |
```

### 6. Surface anomalies

After the main table, call out anything that may need attention:

- **Unassigned tickets you created** — tickets from the created-by query that have no assignee
- **Triage tickets** — may need a status update or assignment
- **High/Urgent priority tickets not In Progress** — may be blocked or forgotten

Format anomalies as a short callout section:

```
### Needs Attention
- **DEV-2150** is in Triage with no assignee (you created it)
- **DEV-2091** is High priority but still in Todo
```

If there are no anomalies, skip this section.

## Important

- **Never use `state` filter in queries** — always fetch broadly and filter client-side
- **Always check created-by tickets** — catches unassigned tickets the user forgot about
- **Keep output scannable** — tables, not prose
