# 07 - GLOBAL ORCHESTRATION (HSBTech)

## Objective
Analyze the global system state from Linear to identify all work items that are ready for execution and report them to the Main Orchestrator.

---

## Core Principle

> The Global Orchestrator identifies WHAT can be done. The Main Orchestrator decides HOW it gets done (sequentially or in parallel).

Linear is the system state and memory.
The Global Orchestrator is the system-level decision engine.

---

## Scope

This skill is responsible for:

- Reading global project state from Linear
- Detecting current workflow phase
- Identifying all ready, non-dependent work items
- Providing a prioritized list of executable tasks to the Main Orchestrator
- Monitoring EPIC-level progress
- Detecting blocked workflows
- Coordinating backlog, implementation, PR, QA, and completion loops
- Signaling when an EPIC is ready for manual merge

This skill is NOT responsible for:

- Writing code
- Performing QA review
- Creating PRs directly
- Creating backlog items directly
- Updating Linear directly when a specialized skill should do it
- Merging PRs

---

## Mandatory Input

- Linear workspace/project state
- EPIC hierarchy
- Work item statuses
- QA statuses
- PR references
- Dependency graph
- Plan reference when backlog does not exist

If Linear state is unavailable → FAIL.

---

## System Layers

### Linear System of Record
Stores:
- State
- Memory
- Relationships
- PR links
- QA findings
- Decisions

### Global Orchestrator
Decides:
- What phase the system is in
- Which specialized workflow should run next
- Whether an EPIC is blocked, active, or ready for manual merge

### Work Item Orchestrator
Runs:
- Task/User Story/Subtask lifecycle
- Implementation → PR → QA → fix loop → done

### Skills
Execute specialized operations:
- Backlog Planning
- Implementation
- Git/PR Management
- QA Review
- Linear System of Record

---

## Global Workflow

Plan
  → Backlog Planning
  → Linear System of Record
  → Work Item Orchestration
  → Git/PR Management
  → QA Review
  → Fix loop if needed
  → EPIC ready for manual merge

---

## Task Identification Logic

The primary output of this agent is a list of ready work items. The logic below is used to determine the state of the system and find those items.

### Logic Step 1: Find Ready Work Items

**Conditions for a work item to be considered 'Ready'**:
- `status` is `todo`.
- All `dependencies` are resolved (i.e., linked tasks have a `status` of `done`).
- The item is not `blocked`.

**Action**:
- Scan all work items in the current project/milestone.
- Compile a list of all items that meet the 'Ready' criteria.
- Prioritize the list based on rules (e.g., priority field in Linear, creation date).

### Output
- **Primary Output**: A prioritized list of ready work item IDs. `[Task_ID_1, Task_ID_2, ...]`
- **Secondary Output**: System status flags (e.g., `is_backlog_empty`, `is_workflow_blocked`).

*The Main Orchestrator will consume this list and decide whether to execute them one by one (Cascade) or all at once (Parallel).*

---

### Case 2: Backlog Exists, Work Items Available

Conditions:
- EPIC exists
- There are todo or in_progress work items
- Dependencies allow execution

Action:
→ Call Work Item Orchestration Skill

---

### Case 3: Work Item Requires PR Creation

Conditions:
- Implementation completed
- Local changes exist
- No PR attached to Linear item

Action:
→ Call Git/PR Management Skill
→ Call Linear System of Record to attach PR reference

---

### Case 4: Work Item Ready for QA

Conditions:
- PR exists
- QA status = pending
- Work item status = in_review

Action:
→ Call QA Review Skill
→ Call Linear System of Record to persist QA result

---

### Case 5: QA Failed

Conditions:
- QA status = changes_required
- QA findings exist

Action:
→ Call Linear System of Record to create fix subtasks
→ Delegate fix subtasks to Work Item Orchestration

---

### Case 6: QA Approved

Conditions:
- QA status = approved

Action:
→ Call Linear System of Record to mark work item done
→ Re-evaluate dependent work items

---

### Case 7: EPIC Completed

Conditions:
- All related User Stories, Tasks, and Subtasks are done
- QA approved for all required PRs
- EPIC PR exists

Action:
→ Mark EPIC as ready for manual merge
→ Do not merge automatically

---

### Case 8: Blocked Workflow

Conditions:
- No executable work item found
- Pending blockers exist

Action:
→ Report blockers
→ Call Linear System of Record to persist blocked state

---

## Delegation Map

| System Condition | Delegated Component |
|---|---|
| Plan exists, no backlog | Backlog Planning |
| Backlog needs persistence | Linear System of Record |
| Work item ready | Work Item Orchestration |
| Code ready, no PR | Git/PR Management |
| PR ready, QA pending | QA Review |
| QA failed | Linear System of Record + Work Item Orchestration |
| EPIC complete | Linear System of Record |
| Blocked state | Linear System of Record |

---

## State Evaluation Order

The Global Orchestrator must evaluate state in this order:

1. Linear availability
2. Backlog existence
3. EPIC state
4. Blockers
5. Work item readiness
6. PR readiness
7. QA readiness
8. EPIC completion

---

## Quality Guidelines (Harness)

- Always read Linear before deciding
- Prefer deterministic decisions
- Never bypass the Work Item Orchestrator for item-level lifecycle
- Never bypass QA
- Never merge automatically
- Avoid duplicating state outside Linear
- Always persist important outcomes back to Linear through the Linear System of Record skill

---

## Anti-patterns

- Acting without reading Linear state
- Performing implementation directly
- Creating PRs directly inside global orchestration
- Running QA without PR context
- Ignoring failed QA findings
- Treating Linear as a passive tracker
- Automatically merging EPIC PRs

---

## Golden Rule

> Global Orchestration coordinates the system. Specialized skills execute the work.
