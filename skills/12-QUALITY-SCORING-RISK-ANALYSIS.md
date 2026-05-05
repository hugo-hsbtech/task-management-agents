# 12 - QUALITY SCORING & RISK ANALYSIS (HSBTech)

## Objective
Quantify engineering quality and delivery risk using real workflow data to guide prioritization and improve decision-making across the system.

---

## Core Principle

> What is measured can be improved. What is not measured becomes risk.

---

## Scope

This skill is responsible for:

- Calculating quality scores for Tasks, User Stories, and EPICs
- Assessing risk levels based on historical behavior
- Identifying bottlenecks and weak areas
- Producing actionable insights for prioritization and improvement

This skill is NOT responsible for:

- Executing tasks
- Updating Linear state
- Creating backlog items
- Performing QA or Implementation

---

## Mandatory Input

- Linear state (statuses, hierarchy, dependencies)
- QA findings history
- PR history
- UAT results (if available)
- Knowledge Store (optional but recommended)

If unavailable → FAIL

---

## Metrics

### 1. Quality Score (0–100)

Calculated based on:

- QA failures
- Number of fix subtasks
- Rework cycles
- Acceptance Criteria compliance
- UAT results

#### Heuristic

Start from 100 and subtract penalties:

- -10 per QA failure
- -5 per fix subtask
- -15 if UAT failed
- -5 per rework cycle

Minimum = 0

---

### 2. Risk Score

Categories:
- LOW
- MEDIUM
- HIGH

Based on:

- Historical QA failures
- Critical modules involved
- Repeated patterns (from Knowledge Store)
- Dependency complexity

---

### 3. Flow Efficiency

Measures time spent in:

- todo
- in_progress
- in_review

Identifies delays and bottlenecks.

---

### 4. Rework Index

- Number of times a task returned from QA
- Number of fix subtasks created

---

## Output

### Example Report

EPIC: <name>

Quality Score: 72/100  
Risk Score: HIGH  

Findings:
- 3 QA failures
- 5 fix subtasks
- Repeated issues in service layer

Insights:
- High rework rate
- QA bottleneck detected

Recommendations:
- Strengthen validation layer
- Improve test coverage
- Refactor high-risk module

---

## Aggregation Rules

- EPIC score = weighted average of its Tasks
- User Story score = average of related Tasks
- Tasks without QA/UAT → default neutral score (e.g., 85)

---

## Quality Guidelines (Harness)

- Prefer simple and explainable scoring
- Keep scoring consistent over time
- Highlight trends, not just snapshots
- Focus on actionable output

---

## Anti-patterns

- Overly complex scoring formulas
- Ignoring qualitative context
- Producing scores without explanation
- Treating score as absolute truth

---

## Integration Points

### With Global Orchestrator
- Prioritize high-risk EPICs or Tasks

### With Backlog Planning
- Improve decomposition quality

### With Knowledge Enrichment
- Feed recurring patterns and risks

---

## Golden Rule

> Scores guide decisions — they do not replace judgment.
