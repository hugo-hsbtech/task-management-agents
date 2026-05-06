---
name: main-orchestrator
description: |
  Dispatch controller for the HSBTech agent hierarchy. Accepts cascade or parallel mode,
  calls Global Orchestrator, claims tasks via optimistic lock, and dispatches Work Item Orchestrators.
  Pure Python class — no LLM invocation during normal operation.
  Only invoke when: Main Orchestrator behavior needs to be understood, debugged, or traced.
  Do NOT invoke during conversation.
disable-model-invocation: true
allowed-tools: "mcp__linear__list_issues mcp__linear__get_issue mcp__linear__update_issue mcp__linear__create_comment"
arguments:
  - name: mode
    description: "Execution mode: cascade | parallel"
---

# 00 - MAIN ORCHESTRATOR (HSBTech)

## Objective
Act as the primary entry point for the entire agent system, determine the execution strategy (sequential or parallel), and dispatch work to the appropriate orchestrators.

---

## Core Principle

> The Main Orchestrator decides HOW to execute, not WHAT to execute.

---

## Responsibilities

- Interact with the user (or read configuration) to determine the execution mode.
- Invoke the `Global Orchestrator Agent` to get a list of all ready and non-dependent work items.
- Based on the selected mode, manage the invocation of `Work Item Orchestrator Agent` instances.
- In Parallel Mode, ensure each task is claimed in Linear before dispatching its orchestrator.
- Monitor all dispatched orchestrators and collect their outcomes.
- Persist the dispatch cycle result via the `Linear Agent`.

---

## Mandatory Input

- User selection or system configuration for execution mode (`cascade` or `parallel`).
- Access to `Global Orchestrator Agent`.
- Access to `Linear Agent` for state persistence.

If execution mode cannot be determined → FAIL and ask user.

---

## Execution Modes

### 1. Cascade Mode (Sequential)

- **Description**: Executes one task at a time, ensuring a deterministic and predictable workflow. This is the classic, default behavior.
- **Logic**:
  1. Request the list of ready work items from the `Global Orchestrator`.
  2. If the list is not empty, take the first item (based on priority provided by the `Global Orchestrator`).
  3. Invoke a single `Work Item Orchestrator Agent` for that item.
  4. Wait for its completion or a defined stopping point (e.g., PR creation).
  5. Repeat the cycle.

### 2. Parallel Mode

- **Description**: Executes all independent, ready tasks simultaneously to maximize throughput.
- **Logic**:
  1. Request the list of all ready work items from the `Global Orchestrator`.
  2. For each work item in the list, instantiate and invoke a separate `Work Item Orchestrator Agent` in parallel.
  3. The runtime environment is responsible for managing the parallel execution of these agent instances.
  4. Monitor the completion of all parallel agents.
  5. Repeat the cycle.

---

## Workflow

1.  **Start**.
2.  **Determine Execution Mode** (e.g., ask user: `Cascade` or `Parallel`?).
3.  **Invoke `Global Orchestrator Agent`** -> Receives `[WorkItem_A, WorkItem_B, ...]`.
4.  **If list is empty** -> Report system idle or blocked. Stop.
5.  **If Mode == `Cascade`**:
    - Take the first item from the prioritized list.
    - Invoke `Work Item Orchestrator(WorkItem_A)`.
    - Wait for completion.
    - Repeat cycle from step 3.
6.  **If Mode == `Parallel`**:
    - For each work item in the list:
      a. Claim task in Linear (set `status = in_progress`) before dispatching.
      b. Verify claim was successful (re-read Linear state).
      c. If claim fails (status already changed) -> skip this item.
    - Concurrently invoke all claimed orchestrators:
      - `Work Item Orchestrator(WorkItem_A)`
      - `Work Item Orchestrator(WorkItem_B)`
      - ...
    - Wait for all dispatched orchestrators to complete or reach a defined stopping point.
    - Repeat cycle from step 3.

---

## Output

- Dispatch summary: list of work items dispatched, their mode, and final status.
- Cycle report persisted to Linear via Linear Agent.

---

## Scope Boundaries

This skill is NOT responsible for:
- Deciding which tasks are ready (that is the Global Orchestrator's job).
- Implementing code.
- Creating PRs.
- Performing QA.
- Resolving merge conflicts.
- Merging PRs into main.

---

## Anti-patterns

- Dispatching a task without claiming it first in Parallel Mode.
- Dispatching the same task to two orchestrators.
- Skipping the Global Orchestrator and selecting tasks directly.
- Expanding scope of a task during dispatch.
- Starting a new cycle before all orchestrators from the previous cycle have reported back.

---

## Golden Rule

> This orchestrator starts the engine and sets the pace. The other agents drive.
