---
phase: 01-foundation-and-linear-integration
plan: 02
subsystem: contracts
tags: [pydantic, validation, schema-drift, AGENT-CONTRACTS, FOUND-03]

requires:
  - phase: 01-01
    provides: src/hsb/contracts/__init__.py module dir; pyproject with pydantic>=2 and pytest dev dep
provides:
  - LinearOperation enum (6 members)
  - LinearInput, LinearEntity, LinearOutput pydantic models with extra=forbid + regex constraints + model_validator
  - RuntimeEnvelope, ErrorContract pydantic models mirroring AGENT-CONTRACTS.md
  - tests/conftest.py fixtures (valid_linear_output, failed_linear_output)
  - tests/test_contracts.py — 11 tests covering Reference Dataset scenarios 9 and 10 + edge cases
affects: [01-04, 01-05, all phase 2+ plans (template for per-agent contracts)]

tech-stack:
  added: []
  patterns:
    - "extra=forbid on every pydantic model — silent schema drift bypassed"
    - "regex Field(..., pattern=) constraints for cross-system identifiers (LIN-\\d+, https://linear.app/)"
    - "model_validator(mode='after') for cross-field invariants (failed result requires error)"
    - "parametrized adversarial tests as the FOUND-03 acceptance gate"

key-files:
  created:
    - src/hsb/contracts/linear.py
    - src/hsb/contracts/base.py
    - tests/conftest.py
    - tests/test_contracts.py
  modified: []

key-decisions:
  - "Added model_config = {'extra': 'forbid'} on LinearEntity in addition to the spec's 2 models — the plan action explicitly requires it on every model and the acceptance criterion accepts ≥ 2"
  - "D-04 honored: contracts live at src/hsb/contracts/linear.py; phase 2 will add backlog.py, qa.py, etc."

patterns-established:
  - "Pattern 1: pydantic v2 contract module template — copy this shape for each new agent contract"
  - "Pattern 2: parametrized adversarial test cases name each scenario with a case_id (uuid_id_rejected, extra_field_rejected, ...)"

requirements-completed:
  - FOUND-03

duration: 5min
completed: 2026-05-06
---

# Phase 01-02: Pydantic Contracts and Schema-Drift Detection Summary

**FOUND-03 delivered: every LinearOutput, LinearInput, LinearEntity, RuntimeEnvelope, and ErrorContract is now pydantic-validated against AGENT-CONTRACTS.md with extra=forbid, regex constraints on identifiers, and a model_validator for cross-field invariants — 11 parametrized tests prove the gates fire.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-06
- **Completed:** 2026-05-06
- **Tasks:** 2
- **Files modified:** 4 (all created)

## Accomplishments
- All 6 contract models from AGENT-CONTRACTS.md §2 + §Standard Runtime Envelope + §Error Contract are mirrored in pydantic v2
- `extra="forbid"` on every model — the schema-drift detection requirement
- Regex constraints reject UUID injection (`id` must match `^LIN-\d+$`) and wrong-domain URLs (`url` must match `^https://linear\.app/`)
- `failed_must_have_error` model_validator catches Repudiation failures (T-02-04)
- 11 tests pass: 2 happy paths + 5 parametrized adversarial cases + 4 edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement pydantic contracts in src/hsb/contracts/linear.py and src/hsb/contracts/base.py** - `b0b423e` (feat)
2. **Task 2: Write parametrized contract tests in tests/conftest.py and tests/test_contracts.py** - `2a84e7c` (test)

## Files Created/Modified

- `src/hsb/contracts/linear.py` — LinearOperation enum + LinearInput + LinearEntity + LinearOutput
- `src/hsb/contracts/base.py` — RuntimeEnvelope + ErrorContract (imports LinearOutput)
- `tests/conftest.py` — `valid_linear_output` and `failed_linear_output` fixtures
- `tests/test_contracts.py` — 11 tests covering FOUND-03

## Decisions Made

- Added `model_config = {"extra": "forbid"}` to `LinearEntity` (the plan's `<interfaces>` block did not include it on LinearEntity, but the action text explicitly states "Do NOT omit `model_config = {\"extra\": \"forbid\"}` on ANY model", and the acceptance criterion accepts ≥ 2). This protects LinearEntity from schema drift on the same axis as the parent models.

## Deviations from Plan

None — plan executed exactly as written. The single decision above is consistent with the plan's hard constraint ("Do NOT omit … on ANY model") and the `grep -c` acceptance criterion is satisfied (returns 3).

## Verification

- `python3 -c "from hsb.contracts.linear import LinearOperation, LinearInput, LinearEntity, LinearOutput; from hsb.contracts.base import RuntimeEnvelope, ErrorContract"` — exits 0
- `pytest tests/test_contracts.py -x -v` — 11 passed in 0.20s
- All 5 parametrized adversarial cases raise `ValidationError` for the correct reason (regex mismatch, extra=forbid, model_validator, Literal enforcement)

## Threats Mitigated

| Threat ID | Status | Verification |
|-----------|--------|--------------|
| T-02-01 (silent extra fields) | Mitigated | extra="forbid" on every model; `test_invalid_output_raises[extra_field_rejected]` |
| T-02-02 (raw UUID into id) | Mitigated | `pattern=r"^LIN-\d+$"`; `test_invalid_output_raises[uuid_id_rejected]` |
| T-02-03 (wrong-domain URL) | Mitigated | `pattern=r"^https://linear\.app/"`; `test_invalid_output_raises[wrong_url_domain_rejected]` |
| T-02-04 (failed result no error) | Mitigated | `failed_must_have_error` model_validator; `test_invalid_output_raises[failed_without_error_rejected]` |
| T-02-05 (offline schema drift detection) | Future-proofed | Pattern documented; downstream batch audit metric scheduled (Plan 04 + future ops) |

## Next Phase Readiness

- Plan 01-04 can now `from hsb.contracts.linear import LinearOutput, LinearInput` and use `LinearOutput.model_validate(text)` for the validation retry layer
- Plan 02-* can copy `src/hsb/contracts/linear.py` as the template for `src/hsb/contracts/backlog.py`, `qa.py`, `git.py`, `builder.py`

## Self-Check: PASSED
