---
name: uat-validation
description: Validate User Stories against acceptance criteria from user-acceptance perspective; produces scenario pass/fail per AC; never reviews low-level code or creates PRs (UATA-04)
disable-model-invocation: true
allowed-tools: Read Glob Grep Bash
---

# 08 - UAT VALIDATION (HSBTech)

## Objective
Validate that implemented features (User Stories) deliver correct functional value from a real-world perspective through structured User Acceptance Testing (UAT).

---

## Core Principle

> Code correctness is not enough — the delivered behavior must solve the intended user problem.

---

## Scope

This skill is responsible for:

- Validating User Stories at functional level
- Executing or simulating UAT scenarios
- Confirming alignment with expected user behavior
- Identifying functional gaps not caught by QA
- Producing actionable validation reports

This skill is NOT responsible for:

- Implementing code
- Performing low-level QA (unit/technical)
- Creating PRs
- Updating backlog structure (except via findings)

---

## Mandatory Input

- User Story (Linear)
- Acceptance Criteria
- Related EPIC context
- QA-approved implementation (PR merged or ready)

If missing → FAIL

---

## Validation Dimensions

1. Functional Behavior
2. User Intent Satisfaction
3. Acceptance Criteria Coverage
4. Edge Case Usability
5. Real-world Scenario Fit

---

## Validation Process

### 1. Interpret User Story
- Understand persona, intent, and expected outcome

### 2. Define Scenarios
- Happy path
- Edge cases
- Negative scenarios

### 3. Execute Validation
- Simulate or reason through behavior
- Compare expected vs actual outcomes

---

## Output: UAT Report

### Global Status
- Approved
- Changes Required

---

### Scenario <n>: <description>

#### Expected Behavior
<what should happen>

#### Actual Behavior
<what happens>

#### Result
Pass | Fail

---

## Findings (if any)

### Finding <n>: <title>

#### Problem
<functional issue>

#### Impact
<user/business impact>

#### Suggested Fix
<clear direction>

#### Suggested Subtask
Title: [UAT-FIX] <action>
Description:
- Context
- Scope
- Acceptance Criteria
- Validation Steps

---

## Quality Guidelines (Harness)

- Focus on user value, not code
- Validate against real usage
- Avoid purely theoretical validation
- Ensure scenarios are concrete and testable

---

## Anti-patterns

- Validating code instead of behavior
- Ignoring user intent
- Superficial “looks good” validation
- Missing edge cases

---

## Golden Rule

> If a user cannot rely on the feature, it is not complete — regardless of code quality.
