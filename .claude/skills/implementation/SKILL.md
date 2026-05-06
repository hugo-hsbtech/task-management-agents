---
name: implementation
description: |
  Implements a Linear work item by making code changes, running local validations, and
  producing an implementation output contract. Does NOT create branches, commit, or write to Linear.
  Only invoke when: an operator explicitly requests implementation of a specific Linear issue.
  Do NOT invoke during conversation or code review.
disable-model-invocation: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(pytest *)
  - Bash(ruff *)
  - Bash(mypy *)
  - Bash(python *)
arguments:
  - name: work_item_id
    description: "Linear work item ID to implement (e.g. LIN-123)"
  - name: plan_source
    description: "Path to the plan.md that generated this work item"
---

# 02 - IMPLEMENTATION (HSBTech)

## Objective
Execute a Linear issue by implementing the required code changes with discipline, clarity, and minimal scope, without managing external workflow operations.

---

## Scope

This skill is responsible for:
- Understanding the assigned Linear issue
- Interpreting technical and functional requirements
- Implementing code changes
- Running local validations
- Preparing implementation notes for downstream processes

This skill is NOT responsible for:
- Creating or managing branches
- Creating Pull Requests
- Updating Linear status
- Deciding execution order
- Managing PR base or merge strategy

---

## Mandatory Input

- Linear Issue (ID + full description)
- Related EPIC context
- Plan reference (/docs/<plan>.md)
- Codebase access

If any of these are missing → FAIL

---

## Core Principle

> Execute only what is defined. Do not expand scope.

---

## Execution Process

### 1. Understand the Issue
- Read full description
- Identify:
  - objective
  - acceptance criteria
  - dependencies
- Map impacted areas of the codebase

---

### 2. Define Implementation Approach
- Identify minimal change required
- Avoid unnecessary refactoring
- Respect existing architecture

---

### 3. Implement Code
- Modify only relevant files
- Keep changes isolated
- Follow code standards

---

### 4. Local Validation

Must execute when applicable:
- Build / run project
- Unit tests
- Lint / type checks

If validation fails → FIX before proceeding

---

### 5. Prepare Implementation Notes

Output must include:

- Summary of changes
- Files modified
- Key decisions
- Assumptions made
- Any risks or limitations
- Notes for QA

---

## Output

- Code changes (local state)
- Implementation Notes (structured)

---

## Quality Guidelines (Harness)

### Code Scope
- Keep changes minimal and focused

### Complexity
- If implementation becomes large:
  → issue was poorly defined or should be split

### Consistency
- Follow existing patterns

### Safety
- Avoid breaking unrelated functionality

---

## Anti-patterns

- Implementing beyond scope
- Mixing multiple issues in one implementation
- Large, unfocused changes
- Skipping local validation
- Introducing new patterns without need

---

## Golden Rule

> This skill executes. It does not orchestrate.
