---
name: task-orchestration
description: |
  Work Item Orchestrator — drives a single task from todo to done through the full lifecycle
  (Linear read → Builder → Git → QA → fix loop → done).
  Only invoke when: operator triggers run-next-step on a specific work item.
  Side effects: updates Linear state, calls Builder/Git/QA agents.
  Do NOT invoke during conversation or without an explicit work item trigger.
disable-model-invocation: true
allowed-tools: "mcp__agents__run_builder mcp__agents__run_git mcp__agents__run_qa mcp__agents__run_linear_op mcp__linear__get_issue mcp__linear__update_issue mcp__linear__create_comment mcp__linear__list_issues"
arguments:
  - name: work_item_id
    description: "Linear work item ID to orchestrate (e.g. LIN-42)"
---
# 06 - TASK ORCHESTRATION (HSBTech)

## Objective
Drive a single, pre-selected work item (Task, User Story, etc.) through its entire lifecycle, from implementation to completion, by invoking the necessary specialized skills.

---

## Core Principle

> Decisions are driven entirely by the current state in Linear.

---

## Scope

This skill is responsible for:

- Receiving a single work item from a higher-level orchestrator
- Managing the item's state transitions (e.g., `todo` → `in_progress` → `in_review` → `done`)
- Delegating execution to appropriate skills
- Managing task lifecycle transitions
- Ensuring continuous workflow progression

This skill is NOT responsible for:

- Implementing code
- Performing QA analysis
- Creating PRs
- Managing backlog structure

---

## Mandatory Input

- Access to Linear state (via MCP)
- Full issue hierarchy (EPIC, User Story, Task)
- Task statuses
- Dependency graph
- QA status
- PR references

If unavailable → FAIL

---

## State Model (Required Fields)

Each task must expose:

- status: todo | in_progress | blocked | in_review | done
- qa_status: pending | approved | changes_required
- dependencies: list
- pr_link (optional)

---

## Claim Rule

Before performing any work, the Work Item Orchestrator **must** atomically claim the task:

```txt
1. Read task status from Linear
2. If status != todo → ABORT (another orchestrator already claimed it)
3. Set status = in_progress in Linear (atomic write)
4. Re-read to confirm status = in_progress and assigned to this orchestrator
5. Only then proceed to execution
```

This prevents two concurrent orchestrators from working on the same task in Parallel Mode.

---

## Core Loop

while True:
  read state from Linear
  decide next action
  execute corresponding skill
  update state

---

## Decision Logic

### Case 1: Ready for Implementation

Conditions:
- status = in_progress (already claimed, see Claim Rule above)
- dependencies resolved
- not blocked

Action:
→ call Implementation Skill

---

### Case 2: Ready for QA

Conditions:
- status = in_review
- qa_status = pending

Action:
→ call QA Review Skill

---

### Case 3: QA Failed

Conditions:
- qa_status = changes_required

Action:
→ call Linear System of Record
→ create subtasks from QA findings
→ set status = blocked

---

### Case 4: QA Approved

Conditions:
- qa_status = approved

Action:
→ set status = done
→ unblock dependent tasks

---

### Case 5: EPIC Completion

Conditions:
- all tasks = done

Action:
→ mark EPIC ready for final PR merge (manual)

---

*(Note: Task selection is handled by the `Main Orchestrator` and `Global Orchestrator`. This agent only executes the lifecycle of the task it is given.)*

---

## Delegation Map

| Situation | Skill |
|----------|------|
| New task | Implementation |
| Code ready | QA Review |
| QA failed | Linear System of Record |
| QA passed | State update |

---

## Quality Guidelines (Harness)

- Never execute blocked tasks
- Never skip QA
- Always respect dependency graph
- Keep workflow moving (no idle tasks)
- Prefer deterministic decisions over randomness

---

## Anti-patterns

- Ignoring dependencies
- Re-running completed tasks
- Skipping QA phase
- Leaving tasks stuck indefinitely
- Executing tasks out of order

---

## Golden Rule

> Orchestration decides — it never executes.
