---
name: knowledge-context-enrichment
description: Retrieve relevant Knowledge Store entries before Builder execution and produce an enrichment report
disable-model-invocation: true
allowed-tools: Read Glob Grep
---

# 10 - KNOWLEDGE / CONTEXT ENRICHMENT (HSBTech)

## Objective
Enhance work items (EPICs, User Stories, Tasks, PRs, QA findings) with actionable technical and contextual insights to improve engineering decisions without altering system state directly.

---

## Core Principle

> Enrichment informs decisions; it does not execute or mutate state.

---

## Scope

This skill is responsible for:

- Enriching Tasks before implementation
- Enriching QA with risk-focused insights
- Enriching PRs with architectural/contextual checks
- Surfacing patterns from historical data (QA findings, PR history)
- Suggesting improvements in backlog structure (non-invasive)

This skill is NOT responsible for:

- Implementing code
- Performing QA decisions (approve/block)
- Creating PRs
- Updating Linear directly
- Orchestrating workflow

---

## Mandatory Input

- Linear context (EPIC / User Story / Task)
- Codebase (read-only)
- PR diffs (when available)
- QA findings history (when available)
- Plan reference (/docs/<plan>.md)

If unavailable → FAIL

---

## Enrichment Phases

### 1. Pre-Implementation Enrichment

#### Goals
- Reduce ambiguity
- Anticipate risks
- Suggest minimal implementation path

#### Output

- Impacted files/modules (likely)
- Suggested approach (high-level)
- Potential pitfalls
- Dependencies to watch
- Edge cases to consider

---

### 2. PR Enrichment

#### Goals
- Improve code quality before/alongside QA
- Detect architectural drift

#### Output

- Architecture alignment checks
- Consistency with patterns
- Potential simplifications
- Performance considerations (if relevant)

---

### 3. QA Enrichment

#### Goals
- Guide QA attention to high-risk areas
- Reduce blind spots

#### Output

- Risk hotspots
- Likely failure scenarios
- Historical similar issues (if any)

---

### 4. Backlog Enrichment (Advisory)

#### Goals
- Improve structure quality
- Detect complexity issues

#### Output

- Suggest task splits (if oversized)
- Suggest User Story creation (if value detected)
- Flag ambiguous descriptions

---

## Output Format

### Enrichment Report

#### Context
- Work Item ID
- Type: Task | User Story | EPIC

#### Insights

##### 1. Suggested Approach
<high-level guidance>

##### 2. Impact Analysis
- Files/Modules:
- Components:

##### 3. Risks
- Risk 1
- Risk 2

##### 4. Edge Cases
- Case 1
- Case 2

##### 5. Recommendations
- Recommendation 1
- Recommendation 2

---

## Quality Guidelines (Harness)

- Keep insights actionable
- Avoid speculation without basis
- Prefer concrete references (files, patterns)
- Focus on high-impact guidance
- Avoid noise

---

## Anti-patterns

- Generic advice ("improve code quality")
- Over-analysis without actionability
- Replacing QA responsibilities
- Duplicating orchestration logic

---

## Integration Points

- Before Implementation (recommended)
- Before QA Review (recommended)
- During backlog review (optional)

---

## Golden Rule

> Provide high-signal insights that improve decisions without taking control away from the execution pipeline.
