# RUNTIME EXECUTION (HSBTech)

## Objective
Define how the HSBTech agent system operates in practice by executing one deterministic workflow action at a time based on the current state stored in Linear.

---

## Core Principle

> The system does not execute features directly. It executes state transitions.

---

## Execution Model

Every runtime cycle follows the same pattern:

```txt
State → Decision → Single Action → Persist → Repeat
```

---

## Runtime Loop

```txt
while true:
  1. Read current state from Linear
  2. Run Global Orchestrator
  3. Decide the next action
  4. Execute exactly one action
  5. Persist the result
  6. Repeat
```

---

## Golden Rule

> One cycle must execute one and only one action **per Work Item Orchestrator**.

This avoids:
- hidden side effects
- runaway automation
- untraceable decisions
- oversized agent executions

> In Parallel Mode, the Main Orchestrator dispatches multiple Work Item Orchestrators concurrently. Each orchestrator independently follows the one-action-per-cycle rule for its own work item. Parallelism lives at the dispatch level, not within a single orchestrator.

---

# Runtime Modes

## 1. Manual Assisted Mode

A human triggers the next step manually.

Example:

```txt
run next step
```

Recommended for:
- initial MVP
- debugging
- validating agent behavior
- high-control workflows

---

## 2. CLI Loop Mode

A local CLI runs the orchestration loop.

Example:

```bash
python run_loop.py
```

Recommended for:
- semi-automated execution
- controlled local development
- early production-like tests

---

## 3. Event-driven Mode

External events trigger runtime cycles.

Examples:
- Linear issue changed
- PR opened
- QA review completed
- UAT completed

Recommended for:
- mature automation
- production-like workflow
- async multi-agent execution

---

# Action Types

Each runtime cycle must resolve to one action type.

## BACKLOG_CREATE
Create EPICs, User Stories, Tasks, and Subtasks from a documented plan.

Agent:
- Backlog Agent

Skills:
- Backlog Planning
- Linear System of Record

---

## PRIORITIZE
Generate a prioritized queue of available work items.

Agent:
- Risk Agent

Skills:
- Adaptive Prioritization
- Quality Scoring & Risk Analysis

---

## TASK_EXECUTE
Implement a selected Task/Subtask/User Story-level work item.

Agent:
- Builder Agent

Skills:
- Implementation

---

## PR_CREATE
Create branch, commit changes, and open PR.

Agent:
- Git Agent

Skills:
- Git / PR Management

---

## QA_REVIEW
Review implementation PR and produce QA status/findings.

Agent:
- QA Agent

Skills:
- QA Review

---

## FIX_CREATE
Create fix subtasks from QA or UAT findings.

Agent:
- Linear Agent

Skills:
- Linear System of Record

---

## UAT_VALIDATE
Validate User Story behavior from user acceptance perspective.

Agent:
- UAT Agent

Skills:
- UAT Validation

---

## KNOWLEDGE_ENRICH
Generate contextual guidance for implementation, QA, or planning.

Agent:
- Intelligence Agent

Skills:
- Knowledge / Context Enrichment

---

## KNOWLEDGE_STORE
Persist reusable long-term knowledge.

Agent:
- Intelligence Agent

Skills:
- Knowledge Storage

---

## REPORT_GENERATE
Generate operational visibility report.

Agent:
- Global Orchestrator Agent or Risk Agent

Skills:
- Observability / Reporting

---

## IMPROVEMENT_TRIGGER
Detect recurring issues and suggest improvement tasks.

Agent:
- Risk Agent

Skills:
- Auto-Improvement Triggers

---

# Work Item Granularity

The system should operate on the smallest meaningful work item.

Preferred execution order:

```txt
Subtask → Task → User Story → EPIC
```

Rules:
- EPICs are coordination and delivery containers.
- User Stories represent user-value validation.
- Tasks are technical execution units.
- Subtasks are fix or micro-execution units.

---

# State Transitions

## Backlog Creation

```txt
plan_detected
  → backlog_generated
  → backlog_persisted
```

---

## Work Item Execution

```txt
todo
  → in_progress
  → implementation_completed
  → pr_created
  → in_review
  → qa_pending
  → qa_approved
  → done
```

---

## QA Failure Loop

```txt
in_review
  → qa_changes_required
  → fix_subtasks_created
  → blocked
  → fix_subtask_todo
  → fix_subtask_done
  → qa_pending
```

---

## UAT Flow

```txt
qa_approved
  → uat_pending
  → uat_approved
  → user_story_done
```

or

```txt
qa_approved
  → uat_pending
  → uat_changes_required
  → uat_fix_subtasks_created
```

---

## EPIC Completion

```txt
all_child_items_done
  → epic_ready_for_manual_merge
```

No automatic merge is allowed.

---

# Decision Rules

## 1. Always Read Linear First
No action may be decided without fresh Linear state.

---

## 2. Respect Dependencies
A work item is executable only when all blocking dependencies are resolved.

---

## 3. Never Skip QA
Any PR must pass QA before the related work item can be completed.

---

## 4. UAT Applies to User Stories
User Stories require UAT when they represent functional user-visible value.

---

## 5. Fixes Target the Original PR
Fix PRs must target the original task PR or the appropriate stacked PR.

---

## 6. No Hidden Durable State
All durable state must be stored in:
- Linear for operational state
- Knowledge Storage for reusable intelligence

---

# Runtime Decision Output

The Global Orchestrator should return a decision envelope.

```json
{
  "action_type": "TASK_EXECUTE",
  "agent": "Builder Agent",
  "reason": "Task LIN-123 is unblocked and ready for implementation",
  "input": {
    "work_item_id": "LIN-123"
  },
  "expected_output": "Implementation output contract"
}
```

---

# Runtime Result Output

Each action returns a result envelope.

```json
{
  "action_type": "TASK_EXECUTE",
  "status": "success",
  "work_item_id": "LIN-123",
  "output": {},
  "next_recommended_action": "PR_CREATE"
}
```

---

# Persistence Rules

## After BACKLOG_CREATE
Persist:
- EPICs
- User Stories
- Tasks
- Subtasks
- Traceability to plan

---

## After TASK_EXECUTE
Persist:
- implementation summary
- files changed
- validation results
- implementation notes

---

## After PR_CREATE
Persist:
- PR URL
- branch
- base branch
- PR status

---

## After QA_REVIEW
Persist:
- QA status
- QA findings
- suggested fix subtasks

---

## After FIX_CREATE
Persist:
- new subtasks
- parent linkage
- PR targeting guidance

---

## After UAT_VALIDATE
Persist:
- UAT status
- scenario results
- UAT findings

---

## After KNOWLEDGE_STORE
Persist:
- knowledge entry location
- reference from related Linear issue when relevant

---

# Operational Safety

## Maximum Actions Per Cycle
Always one **per Work Item Orchestrator instance**.
In Parallel Mode, the Main Orchestrator may dispatch N orchestrators simultaneously, where N equals the number of non-dependent ready tasks.

## Maximum Fix Subtasks Per QA Report
Recommended default:
```txt
max_fix_subtasks = 5
```

## Maximum Improvement Tasks Per Cycle
Recommended default:
```txt
max_improvement_tasks = 3
```

## Manual Approval Required For
- EPIC PR merge
- large refactors
- architectural changes
- destructive operations
- dependency upgrades with broad impact

---

# Parallel Execution Loop

When the Main Orchestrator operates in Parallel Mode, the runtime loop changes shape:

```txt
1. Read current state from Linear
2. Run Global Orchestrator → returns list [Task_A, Task_B, Task_C, ...]
3. For each task in list (concurrently):
   a. Claim task in Linear (set status = in_progress)
   b. Dispatch dedicated Work Item Orchestrator
   c. Each orchestrator runs its own: State → Decision → Single Action → Persist → Repeat
4. Monitor all orchestrators until completion
5. Re-read Linear state
6. Repeat
```

## Parallel Mode Rules

- Each Work Item Orchestrator is isolated — it owns exactly one task.
- No two orchestrators may claim the same task (claiming is atomic via Linear).
- Each orchestrator creates its own branch from the EPIC branch.
- Orchestrators do not share working tree state.
- Each orchestrator persists its own result to Linear independently.
- The Main Orchestrator waits for all dispatched orchestrators before starting a new dispatch cycle.

---

# Anti-patterns

- Executing an entire EPIC in one cycle
- Running multiple agents without persisting intermediate state
- Creating PRs before implementation summary exists
- Running QA without PR/diff context
- Creating fix subtasks without evidence
- Storing operational state outside Linear
- Automatically merging into main
- Ignoring failed validation

---

# MVP Execution Recommendation

Start with Manual Assisted Mode.

Minimal command set:

```txt
run next step
show current state
show next action
run action <ACTION_TYPE>
generate report
```

Then evolve to CLI Loop Mode.

Finally, move to Event-driven Mode when stable.

---

# Minimal Runtime Flow for MVP

```txt
1. Human provides plan file
2. run next step → BACKLOG_CREATE
3. run next step → PRIORITIZE
4. run next step → TASK_EXECUTE
5. run next step → PR_CREATE
6. run next step → QA_REVIEW
7. run next step → FIX_CREATE or mark done
8. Repeat
```

---

# Golden Rule

> Make every action small, observable, reversible, and persisted.
