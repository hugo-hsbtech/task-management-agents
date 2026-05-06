---
name: git-pr-management
description: |
  Creates branches and PRs from local code changes. Handles REBASE_STACK for sibling task PRs.
  Only invoke when: an operator explicitly requests branch/PR creation for a completed implementation.
  Do NOT invoke during conversation or code review.
disable-model-invocation: true
allowed-tools:
  - Bash(gh pr create *)
  - Bash(gh pr list *)
  - Bash(gh pr view *)
  - Bash(gh pr diff *)
  - Bash(git checkout *)
  - Bash(git push --force-with-lease *)
  - Bash(git rebase *)
  - Bash(git log *)
  - Bash(git fetch *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git status *)
arguments:
  - name: work_item_id
    description: "Linear work item ID (e.g. LIN-123)"
  - name: epic_id
    description: "Parent EPIC ID (e.g. LIN-100) — determines PR base branch"
  - name: implementation_output
    description: "Path to JSON file containing BuilderOutput contract"
---

# 04 - GIT / PR MANAGEMENT (HSBTech)

## Objective
Transform local code changes into structured, traceable, and correctly chained Pull Requests, following a stacked PR strategy aligned with EPIC-driven delivery.

---

## Scope

This skill is responsible for:
- Creating branches
- Organizing commits
- Creating Pull Requests
- Defining correct PR base (stacking)
- Maintaining dependency alignment between PRs
- Preparing EPIC-level PR (without merging)

This skill is NOT responsible for:
- Implementing code
- Performing QA review
- Selecting tasks
- Merging PRs
- Updating Linear

---

## Mandatory Input

- Linear Issue (Task)
- Related EPIC
- Task dependencies
- Local code changes (from Implementation)
- Existing PR context (if any)

If any input is missing → FAIL

---

## Core Principle

> Each task results in one small, well-scoped PR, correctly chained.

---

## Branch Strategy

### Naming
feature/<linear-id>-<slug>

---

## PR Strategy

### Naming
[<linear-id>] <short description>

---

## Stacked PR Model

EPIC branch
   ↓
Task 1 → PR-1 (base: epic)
Task 2 → PR-2 (base: PR-1)
Task 3 → PR-3 (base: PR-2)

---

## Base Branch Decision Logic

### Case 1: First task of EPIC
base = epic branch

### Case 2: Task depends on another
base = previous task PR

### Case 3: Independent task
base = epic branch

---

## Parallel Execution: Branch Isolation Rules

When multiple Work Item Orchestrators are running concurrently, each must:

- Create its branch from the **current state of the EPIC branch** at the time of claiming the task.
- Never checkout, read, or write to a branch owned by another concurrent orchestrator.
- Never assume the working tree is clean — always create a fresh branch from the EPIC branch reference.
- Register its branch name in Linear (as part of `in_progress` metadata) before performing any commits.

This ensures that two parallel tasks targeting independent files can produce two independent PRs with no cross-contamination, even when running in the same repository.

### Conflict Responsibility

Conflict resolution is a **human responsibility** at EPIC PR merge time.

No agent attempts to resolve merge conflicts automatically.
If a conflict is detected during PR creation, the Git Agent must:
- Report the conflict in Linear as a blocker comment.
- Set the task status to `blocked`.
- Escalate to human.

---

## Execution Steps

1. Create branch
2. Apply changes from implementation
3. Create commits
4. Determine correct base branch
5. Create Pull Request
6. Attach metadata:
   - Link to Linear issue
   - Description
   - Context
   - Notes for QA

---

## Output

- Branch created
- Commits pushed
- Pull Request created

---

## Quality Guidelines (Harness)

- One task = one PR
- Keep PRs small
- Maintain clean commit history
- Use clear commit messages
- Ensure correct base branch

---

## Anti-patterns

- Large PRs
- Incorrect base branch
- Multiple tasks in one PR
- Direct merge to main
- Ignoring dependencies

---

## Merge Policy

- Merge is ALWAYS manual
- Merge occurs ONLY through EPIC PR
- This skill must NEVER merge

---

## Golden Rule

> Correct PR chaining is mandatory for system integrity.
