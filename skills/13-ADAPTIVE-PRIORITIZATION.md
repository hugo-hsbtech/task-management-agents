# 13 - ADAPTIVE PRIORITIZATION (HSBTech)

## Objective
Dynamically prioritize work items based on risk, quality, dependencies, and system state to maximize delivery efficiency and reduce critical failures.

---

## Core Principle

> Priority must reflect reality, not static planning.

---

## Scope

This skill is responsible for:

- Reordering tasks based on real-time data
- Elevating high-risk or failing items
- Identifying blocking tasks
- Producing a prioritized execution queue

This skill is NOT responsible for:

- Executing tasks
- Modifying backlog structure
- Creating or deleting issues
- Performing QA or implementation

---

## Mandatory Input

- Linear state (tasks, status, dependencies)
- Quality Score
- Risk Score
- QA findings
- Blockers

If unavailable → FAIL

---

## Prioritization Factors

### 1. Risk Score
Higher risk → higher priority

### 2. QA Failures
More failures → higher priority

### 3. Blockers
Tasks blocking others → highest priority

### 4. Dependencies
Tasks unlocking others → elevated priority

### 5. Flow State
Tasks stuck in progress or review → elevated priority

---

## Priority Heuristic

Example scoring:

priority_score =
  (risk_weight * risk_score) +
  (qa_failures * weight) +
  (blocker_flag * high_weight) +
  (dependency_unlock_value)

---

## Output

### Priority Queue

1. TASK-123 (High risk, blocking others)
2. TASK-456 (QA failed multiple times)
3. TASK-789 (Independent, low risk)

---

## Quality Guidelines (Harness)

- Respect dependency graph
- Avoid constant reshuffling
- Prioritize stability and predictability
- Ensure fairness across EPICs when possible

---

## Anti-patterns

- Ignoring dependencies
- Over-prioritizing low-impact issues
- Constant reordering without reason
- Creating priority oscillation

---

## Integration Points

### With Global Orchestrator
Provides ordered tasks for execution

### With Work Item Orchestrator
Receives next task to execute

### With Quality Scoring
Consumes risk and quality metrics

---

## Golden Rule

> The most important work is not what was planned first, but what matters most now.
