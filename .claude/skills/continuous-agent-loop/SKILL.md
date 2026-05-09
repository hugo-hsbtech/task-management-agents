---
name: continuous-agent-loop
description: Patterns for continuous autonomous agent loops with quality gates, evals, and recovery controls.
origin: ECC
---

# Continuous Agent Loop

Patterns for running Claude Code in autonomous loops with quality gates and recovery controls.

## Loop Selection Flow

```text
Start
  |
  +-- Need strict CI/PR control? -- yes --> continuous-pr
  |
  +-- Need RFC decomposition? -- yes --> rfc-dag
  |
  +-- Need exploratory parallel generation? -- yes --> infinite
  |
  +-- default --> sequential
```

## Combined Pattern

Recommended production stack:
1. quality gates (`/quality-gate`)
2. eval loop (`eval-harness`)

## Failure Modes

- loop churn without measurable progress
- repeated retries with same root cause
- merge queue stalls
- cost drift from unbounded escalation

## Recovery

- freeze loop
- run `/harness-audit`
- reduce scope to failing unit
- replay with explicit acceptance criteria
