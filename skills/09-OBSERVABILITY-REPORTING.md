# 09 - OBSERVABILITY / REPORTING (HSBTech)

## Objective
Provide visibility into the system by analyzing the state stored in Linear and generating structured operational reports.

---

## Core Principle

> What cannot be observed cannot be improved.

---

## Scope

This skill is responsible for:

- Reading system state from Linear
- Generating reports on workflow progress
- Identifying bottlenecks and blockers
- Highlighting risks and delays
- Providing actionable insights

This skill is NOT responsible for:

- Executing tasks
- Modifying state
- Creating or updating issues
- Making decisions or triggering workflows

---

## Mandatory Input

- Linear state (EPICs, User Stories, Tasks)
- Status fields
- QA status
- PR references
- UAT status (if available)

If unavailable → FAIL

---

## Key Metrics

### Progress
- EPIC completion (%)
- Tasks done vs total
- User Stories validated (UAT)

### Flow
- Tasks in progress
- Tasks in review
- QA pending
- QA failed
- UAT pending

### Blockers
- Blocked tasks
- Dependency issues

### PR Status
- Open PRs
- PRs awaiting review
- PRs with failed QA

---

## Report Structure

### System Summary
- Total EPICs
- Active EPICs
- Completed EPICs

---

### EPIC Report

For each EPIC:

- Name
- Progress (%)
- Open Tasks
- Blocked Tasks
- QA Issues
- UAT Status

---

### Bottlenecks

- Tasks stuck in progress
- QA failures
- Repeated failures
- Dependency chains causing delay

---

### Next Actions

- Tasks ready for execution
- Tasks ready for QA
- Tasks requiring fixes

---

## Output

- Structured report (Markdown / JSON)

---

## Quality Guidelines (Harness)

- Focus on actionable insights
- Avoid raw data dumps
- Highlight risks clearly
- Keep reports concise but informative

---

## Anti-patterns

- Reporting without insights
- Ignoring blocked tasks
- Overloading with irrelevant data
- Lack of prioritization

---

## Golden Rule

> Observability exists to drive action, not just awareness.
