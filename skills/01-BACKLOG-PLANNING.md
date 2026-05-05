# 01 - BACKLOG PLANNING (HSBTech)

## Objective
Transform a documented plan into a structured backlog organized by EPICs, ensuring traceability, flexibility, and high-quality execution flow.

---

## Mandatory Input
- Plan file path: /docs/<plan>.md

If not provided → FAIL.

---

## Core Principle
Everything starts from EPICs.

---

## Structure

### EPIC (Required)
- Represents a deliverable feature
- Has final PR (manual merge)

### User Story (Optional, Recommended)
Use when:
- There is business value
- There is UAT/manual validation

### Task (Flexible)
- Can belong to User Story OR directly to EPIC
- Must NEVER be orphan

---

## Relationship Model

EPIC
 ├── User Story
 │     └── Tasks (0..N)
 │
 └── Tasks (0..N)

---

## Work Types

### Functional
EPIC → User Story → Tasks

### Technical Simple
EPIC → Task

### Technical Complex
EPIC → Task (macro) → Subtasks

---

## Heuristics (Harness)

### User Story
- If it can be validated by a human → should be a User Story

### Task
- Must be smallest executable unit
- Should generate small PR

### Task without User Story
Allowed ONLY if:
- Simple
- Internal
- Technical

If complex → wrong classification

### User Story without Tasks
Allowed if trivial

If not trivial → should be decomposed

---

## Golden Rule
Structure must reflect the type of work, not enforce a rigid format.

---

## Traceability
All items must reference:

Plan Source: /docs/<plan>.md

---

## PR Strategy

- EPIC → main PR (manual merge)
- Tasks → stacked PRs

---

## Quality Gate

- All items linked to EPIC
- No orphan tasks
- User Stories have UAT (when applicable)
- Tasks are small OR explicitly macro
- Structure is coherent

---

## Anti-patterns

- Forcing User Stories everywhere
- Large Tasks without subdivision
- Orphan Tasks
- User Stories without validation (when needed)
- Mixing technical complexity improperly
