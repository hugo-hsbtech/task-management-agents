---
name: linear-system-of-record
description: |
  Manages Linear work items as the operational state engine for the HSBTech delivery pipeline.
  Only invoke when: an explicit Linear operation is requested (create, update, comment, link PR).
  Do NOT invoke for read-only reporting or conversational queries about project status.
disable-model-invocation: true
allowed-tools:
  - mcp__linear__create_issue
  - mcp__linear__update_issue
  - mcp__linear__get_issue
  - mcp__linear__list_issues
  - mcp__linear__create_comment
  - mcp__linear__list_projects
  - mcp__linear__list_teams
arguments:
  - name: operation
    description: "The Linear operation to perform: create | update | read | link | comment | create_subtasks"
  - name: payload
    description: "JSON payload for the operation (matches LinearInput contract)"
---
# 05 - LINEAR SYSTEM OF RECORD (HSBTech)

## Objective
Establish Linear as the single source of truth and operational state engine for the entire system, managing workflow state, traceability, and memory across all agents.

---

## Core Principle

> No relevant system state exists outside Linear.

Linear is the brain, memory, and coordination layer of the system.

---

## Scope

This skill is responsible for:

- Managing system state
- Reading and writing workflow data
- Maintaining relationships between EPICs, User Stories, and Tasks
- Recording PRs, QA results, and execution history
- Creating subtasks from QA findings
- Enabling orchestration decisions

This skill is NOT responsible for:

- Planning backlog
- Implementing code
- Performing QA analysis
- Creating PRs
- Deciding execution strategy (but enables it)

---

## Mandatory Input

- Linear workspace access (via MCP)
- Issue structure (EPIC, User Story, Task)
- Plan reference (/docs/<plan>.md)

If unavailable → FAIL

---

## State Model

Each issue must track:

- Status: todo | in_progress | blocked | in_review | done
- PR Links
- QA Status: pending | approved | changes_required
- Dependencies
- Parent relationships (EPIC / User Story)
- Comments (history, decisions, findings)

---

## Responsibilities

### 1. State Management

- Update issue status
- Track lifecycle transitions
- Record execution progress

---

### 2. Relationship Integrity

- Maintain hierarchy:
  EPIC → User Story → Task → Subtask

- Ensure no orphan issues
- Maintain dependency graph

---

### 3. Memory Layer

- Store:
  - Implementation notes
  - QA findings
  - Decisions
  - PR references

---

### 4. QA Integration (Critical)

- Parse QA findings
- Create subtasks for each finding

Each subtask must include:
- Title
- Description
- Acceptance Criteria
- Validation Steps

---

### 5. PR Tracking

- Attach PR links to issues
- Maintain mapping:
  Task ↔ PR
  EPIC ↔ Final PR

---

## Read Operations

- Fetch next available task
- Identify unblocked tasks
- Retrieve issue context
- Map dependency resolution

---

## Write Operations

- Update status
- Add comments
- Link PRs
- Create subtasks
- Record QA outcomes
- Flag blockers

---

## Workflow Loop

Linear (state)
  → Orchestrator decision
  → Implementation execution
  → PR creation
  → QA review
  → Findings stored in Linear
  → Subtasks created
  → Loop continues

---

## Quality Guidelines (Harness)

- Always keep status updated
- Avoid stale tasks
- Ensure complete traceability
- Maintain clean hierarchy
- Ensure QA findings are actionable and persisted

---

## Anti-patterns

- State outside Linear
- Missing relationships
- Inconsistent statuses
- Untracked PRs
- Ignoring QA findings
- Manual memory outside system

---

## Golden Rule

> Linear is not a reflection of the system — it is the system.
