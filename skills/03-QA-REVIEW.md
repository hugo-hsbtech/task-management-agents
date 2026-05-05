# 03 - QA REVIEW (HSBTech)

## Objective
Analyze implemented code changes to validate correctness, quality, and alignment with requirements, producing a deeply actionable QA Findings Report.

---

## Scope

This skill is responsible for:
- Reviewing code changes (diff)
- Validating against Linear issue and acceptance criteria
- Identifying defects, risks, and improvement areas
- Producing structured and actionable findings

This skill is NOT responsible for:
- Implementing fixes
- Creating PRs
- Updating Linear
- Managing branches or workflow

---

## Mandatory Input

- Code diff / changes
- Linear Issue (ID + description)
- Related EPIC context
- Implementation Notes

If any input is missing → FAIL

---

## Core Principle

> Every issue found must be described with enough detail to enable independent correction.

---

## Review Dimensions

1. Functional Correctness
2. Acceptance Criteria Compliance
3. Code Quality (clarity, simplicity, maintainability)
4. Architecture Alignment
5. Side Effects / Regression Risk
6. Edge Cases
7. Test Coverage (when applicable)

---

## Output: QA Findings Report

### Global Status
- Approved
- Changes Required

---

## Findings Structure

Each finding must follow this format:

### Finding <n>: <title>

Severity: Critical | High | Medium | Low  
Category: Functional | Architecture | Code Quality | Test | Security | Regression  
Status: Blocking | Non-blocking  

#### Problem
<clear description>

#### Evidence
- File: <path>
- Component: <function/class/module>
- Location: <line/block if possible>
- Related Requirement: <Linear issue / acceptance criteria>

#### Expected Behavior
<what should happen>

#### Actual Behavior
<what happens or risk>

#### Suggested Fix
<detailed guidance>

#### Suggested Subtask
Title: [FIX] <clear action>
Description:
- Context
- Scope
- Acceptance Criteria
- Validation Steps

#### PR Targeting Guidance
Target: <original task PR>

---

## Quality Guidelines (Harness)

- Findings must be specific, not generic
- Avoid vague statements like "improve code"
- Always include evidence
- Always include actionable fix guidance
- Prefer multiple small findings over one vague block

---

## Severity Guidelines

- Critical: breaks functionality or system integrity
- High: major risk or incorrect behavior
- Medium: quality or maintainability issue
- Low: minor improvement

---

## Anti-patterns

- Superficial review
- Missing evidence
- Non-actionable feedback
- Overly generic suggestions
- Approving incomplete implementations

---

## Golden Rule

> QA does not suggest — QA instructs precise corrections.
