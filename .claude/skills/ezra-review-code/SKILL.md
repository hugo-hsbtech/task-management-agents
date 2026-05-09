---
name: ezra-review-code
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Perform FAANG-level code review analyzing necessity, correctness, and completeness of changes
disable-model-invocation: true
---

# FAANG-Level Code Review

Perform a rigorous code analysis and review of the specified changes. Evaluate whether the changes are **necessary**, **correct**, and **complete**.

## Arguments

- `$ARGUMENTS`: PR URL, branch name, commit SHA, or file path(s) to review

## Review Framework

### 1. Understand the Context

Before reviewing code, understand:

- What problem is being solved?
- What is the expected behavior change?
- Who are the stakeholders (users, other services, etc.)?

### 2. Necessity Analysis

Determine if the changes are **necessary**:

- [ ] Does this change solve a real problem or add genuine value?
- [ ] Is this the right layer/component to make this change?
- [ ] Could this be achieved with existing code or a simpler approach?
- [ ] Are there any unnecessary changes (formatting, refactoring) bundled in?
- [ ] Is every added line of code essential?

### 3. Correctness Analysis

Determine if the changes are **correct**:

**Functional Correctness**

- [ ] Does the code do what it claims to do?
- [ ] Are edge cases handled (null, empty, boundary values)?
- [ ] Is error handling appropriate and consistent?
- [ ] Are there any race conditions or concurrency issues?
- [ ] Is state managed correctly?

**Security**

- [ ] Input validation present where needed?
- [ ] No injection vulnerabilities (SQL, XSS, command)?
- [ ] Secrets/credentials handled properly?
- [ ] Authentication/authorization checked?
- [ ] No sensitive data exposure in logs or responses?

**Performance**

- [ ] No unnecessary database queries or N+1 problems?
- [ ] Appropriate use of caching?
- [ ] No blocking operations in hot paths?
- [ ] Memory usage reasonable?
- [ ] Algorithm complexity appropriate for expected data size?

**Reliability**

- [ ] Failures handled gracefully?
- [ ] Retries implemented where appropriate?
- [ ] Timeouts configured for external calls?
- [ ] No silent failures that could cause data inconsistency?

### 4. Completeness Analysis

Determine if the changes are **complete**:

- [ ] Does the implementation fully address the requirements?
- [ ] Are all code paths tested?
- [ ] Are tests meaningful (not just coverage padding)?
- [ ] Is documentation updated if needed (API docs, README)?
- [ ] Are database migrations included if schema changed?
- [ ] Are feature flags or rollback mechanisms in place for risky changes?
- [ ] Are monitoring/alerting considerations addressed?

### 5. Code Quality

Evaluate maintainability:

- [ ] Is the code readable and self-documenting?
- [ ] Are names descriptive and consistent with codebase conventions?
- [ ] Is complexity manageable (functions not too long, nesting not too deep)?
- [ ] Are abstractions at the right level?
- [ ] Is there unnecessary duplication?
- [ ] Does it follow existing patterns in the codebase?

## Output Format

Structure your review as:

```
## Summary
[1-2 sentence overview of what the changes do]

## Verdict: [APPROVE | REQUEST_CHANGES | NEEDS_DISCUSSION]

### Necessary: [YES | PARTIAL | NO]
[Brief explanation]

### Correct: [YES | PARTIAL | NO]
[Brief explanation with specific issues if any]

### Complete: [YES | PARTIAL | NO]
[Brief explanation of what's missing if anything]

## Critical Issues (blocking)
[List any issues that must be fixed before merge]

## Suggestions (non-blocking)
[List improvements that would be nice but aren't required]

## Questions
[List any clarifying questions for the author]
```

## Review Principles

1. **Be specific**: Point to exact lines/files. Use `file:line` format.
2. **Explain why**: Don't just say "this is wrong" - explain the impact.
3. **Suggest solutions**: When identifying problems, propose fixes when possible.
4. **Prioritize**: Distinguish blocking issues from nice-to-haves.
5. **Stay objective**: Focus on the code, not the author.
6. **Assume good intent**: The author may have context you don't.
7. **Be thorough but efficient**: Don't nitpick style if there are logic bugs.

## Review Tone for GitHub

When posting reviews to GitHub, write as a human colleague — not an AI with a classification system. The structured analysis (Output Format, severity levels) is for Claude Code's local display only.

- **Frame suggestions as questions**: "Is the intent..." or "Would you consider..." rather than "You should..."
- **No severity prefixes**: Don't label comments with `nit:`, `suggestion:`, `question (low):`, etc. Just say what you mean.
- **Explain why**: Link reasoning to concrete impacts (performance, maintainability, correctness)
- **Provide evidence**: Link to documentation, SDK source, or issues when making technical claims
- **Assume good intent**: The author likely has context you don't — pose alternatives as questions

**Good:**

```
Since `max_concurrent_activities` is per-worker, and both this and the workflow
semaphore are set to 40 — is the intent that a single workflow can use full capacity?
```

**Avoid:**

```
**question (low):** Since `max_concurrent_activities` is per-worker...
```

```
You should set the workflow semaphore lower than the worker limit to leave headroom.
```

## Severity Levels

Use these for internal analysis (Claude Code output). Do not include severity labels in GitHub-posted comments.

- **Critical**: Security vulnerabilities, data loss risks, breaking changes
- **High**: Bugs that will cause failures in production
- **Medium**: Performance issues, missing error handling, incomplete features
- **Low**: Code style, minor improvements, documentation gaps

## Before Posting to GitHub

**Pre-flight checklist** (verify all before posting):

- [ ] Review follows the Output Format specified above
- [ ] Using `gh api` patterns from `ezra-github-ops` reference guide
- [ ] Review will be created as DRAFT (user can submit after reviewing)
- [ ] File paths and line numbers are accurate
- [ ] Comments are written in plain conversational language (no severity prefixes)

If any item is unchecked, DO NOT POST THE REVIEW.

## Creating GitHub Reviews

When posting review findings to GitHub, use the `github-pr` skill for correct API patterns.

**CRITICAL**: Reviews MUST be created as drafts (omit the `event` field) so the user can review before submission.

**Important**: The Output Format above is your **internal analysis framework**. When posting to GitHub, write in a natural, conversational voice — see the "Review Content Guidelines" section in the `ezra-github-ops` skill for tone and inline comment guidance.

## Related Skills

- `/ezra-create-pr` — full PR preparation workflow that orchestrates this skill alongside lint, tests, docs, and PR creation
- `/ezra-github-ops` — low-level GitHub API operations for posting reviews
