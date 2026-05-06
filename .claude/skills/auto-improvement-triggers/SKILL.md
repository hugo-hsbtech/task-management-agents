---
name: auto-improvement-triggers
description: Detect repeated QA failure patterns and produce improvement-trigger suggestions; never creates Linear items directly (RISK-04)
disable-model-invocation: true
allowed-tools:
---

# 14 - AUTO-IMPROVEMENT TRIGGERS (HSBTech)

## Objective
Automatically detect recurring issues, hotspots, and quality degradation patterns, and generate actionable improvement triggers to enhance system reliability and engineering quality over time.

---

## Core Principle

> Improvements should be triggered by patterns, not isolated events.

---

## Scope

This skill is responsible for:

- Detecting recurring QA failures
- Identifying code hotspots and fragile modules
- Monitoring rework patterns and quality degradation
- Generating improvement actions as new work items
- Classifying improvement types (refactor, test, architecture, etc.)

This skill is NOT responsible for:

- Implementing improvements
- Executing tasks
- Modifying existing code or PRs
- Performing QA or scoring directly

---

## Mandatory Input

- QA findings history
- Quality Scoring data
- Observability reports
- Knowledge Store
- Linear state (issues, relationships)

If unavailable → FAIL

---

## Detection Rules

### 1. Repeated QA Failures

Trigger when:
- Same type of failure occurs ≥ N times
- Same module involved in multiple QA failures

---

### 2. High Rework Index

Trigger when:
- Task has multiple rework cycles
- High number of fix subtasks

---

### 3. Hotspot Detection

Trigger when:
- Module/component appears frequently in failures
- High-risk score consistently

---

### 4. Quality Degradation

Trigger when:
- Quality score drops below threshold
- Multiple low-quality tasks within same EPIC/module

---

## Action Generation

For each trigger, generate a new work item:

### Format

Title:
[IMPROVEMENT] <action>

Description:
- Context
- Trigger condition
- Evidence
- Suggested scope
- Expected outcome

---

## Classification

Each improvement must be categorized:

- Refactoring
- Testing
- Architecture
- Performance
- Reliability

---

## Output

### Example

Trigger:
Repeated QA failures in module: payment_service

Action:
Create Task → [IMPROVEMENT] Refactor payment validation logic

Reason:
- 3 QA failures
- High rework index
- Known risk pattern

---

## Integration Points

### Linear System of Record
- Persist generated improvement tasks

### Adaptive Prioritization
- Increase priority of improvement tasks when risk is high

### Knowledge Storage
- Store detected patterns for future reference

### Global Orchestrator
- Decide when to execute improvements

---

## Quality Guidelines (Harness)

- Only trigger on patterns (not one-off events)
- Avoid generating excessive noise
- Ensure clear and actionable outputs
- Include evidence for every trigger
- Prefer fewer, high-quality improvement tasks

---

## Anti-patterns

- Triggering on isolated incidents
- Creating duplicate improvement tasks
- Overloading backlog with low-value improvements
- Ignoring severity/context of issues

---

## Golden Rule

> The system improves itself by learning from repeated failures, not reacting to noise.
