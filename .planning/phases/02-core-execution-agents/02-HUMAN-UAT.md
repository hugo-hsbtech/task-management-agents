---
status: partial
phase: 02-core-execution-agents
source: [02-VERIFICATION.md]
started: 2026-05-06T16:50:00.000Z
updated: 2026-05-06T16:50:00.000Z
---

## Current Test

[awaiting human testing — operator must run 4 integration suites with live Linear MCP + GitHub access]

## Tests

### 1. Backlog Agent integration suite (BKPK-01..05)
expected: 5 integration tests pass against a real Linear test workspace; second run produces 0 new EPICs (idempotency)
result: [pending]

### 2. Builder Agent integration suite (BLDR-01, BLDR-02, BLDR-04)
expected: 3 integration tests pass against hsb-test-fixture; test_capability_boundary asserts git HEAD unchanged after Builder run
result: [pending]

### 3. Git Agent integration suite (GITA-01..04)
expected: 4 integration tests pass against hsb-test-fixture; PR base is epic/LIN-... (not main); branch + title match regex
result: [pending]

### 4. QA Agent integration suite (QAAG-01, QAAG-05)
expected: 2 integration tests pass; sentinel file unmodified after agent run (QAAG-05 runtime check); QAOutput cycle count increments 0->1
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
