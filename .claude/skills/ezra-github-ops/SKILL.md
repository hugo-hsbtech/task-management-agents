---
name: ezra-github-ops
description: GitHub PR operations via gh CLI. Use when creating reviews, replying to comments, or fetching PR data. CRITICAL - Always create reviews as drafts by omitting the event field.
allowed-tools: Bash
---

# GitHub PR Operations

Comprehensive reference for GitHub pull request operations using the `gh` CLI and API.

For detailed command patterns and syntax, see [Command Reference](./COMMANDS.md).

## CRITICAL: Always Create Draft Reviews

When creating a new PR review with inline comments, **ALWAYS create it as a pending/draft review first**.

**DO NOT** include an `event` field when creating the review. Omitting `event` creates a **pending review** (draft state) that the user can review and submit from the GitHub UI.

### Event field values

**CRITICAL**: Only include `event` field when user explicitly requests submission.

| Value               | Behavior                                   | When to Use                   |
| ------------------- | ------------------------------------------ | ----------------------------- |
| Omit field          | Creates draft/pending review               | **DEFAULT - Always use this** |
| `"PENDING"`         | Creates draft/pending review               | Same as omitting              |
| `"COMMENT"`         | **Submits immediately** as comment         | Only if explicitly requested  |
| `"APPROVE"`         | **Submits immediately** as approval        | Only if explicitly requested  |
| `"REQUEST_CHANGES"` | **Submits immediately** requesting changes | Only if explicitly requested  |

## Review Content Guidelines

When authoring PR reviews, follow these principles for tone and content:

### Voice and Tone

- **Write as the reviewer, not as an AI**: Use natural, conversational language — not checklist reports or robotic phrasing
  - Good: "Looks good — all files moved, imports updated, CI green."
  - Avoid: "## Verdict: APPROVE\n\n### Necessary: YES\n### Correct: YES"

- **Keep it conversational**: Frame observations as you would in a normal code review
  - Good: "I see mono-ezra#11 covers the testing-standards doc — just noting the monorepo root CLAUDE.md:19 still says 'co-located'."
  - Avoid: "Per the analysis performed, it has been determined that..."

### Inline Comments

**Only post inline comments for actionable items** — things the author should change, consider, or respond to.

**Write in plain language** — no severity prefixes, no bold labels. The comment should read like something a colleague typed, not a categorized finding.

**Do NOT post:**

- Affirmative comments ("good catch", "verified this works", "looks correct")
- Observations with no action needed
- Praise or agreement

**If there are no actionable items**, a body-only approval is the correct review. That's not "just a comment" — it's a clean approval.

### Internal vs. External Output

The `ezra-review-code` skill's Output Format (Necessary/Correct/Complete structure) is an **internal analysis framework** for your reasoning. Do NOT copy it verbatim into a GitHub review. Summarize your findings in natural language instead.

## Best Practices

1. **Always create drafts first** - Let users review before submission
2. **Use suggestion blocks** - Format code suggestions with ```suggestion blocks
3. **Be specific** - Include file paths and line numbers in review summaries
4. **Verify queries** - Test GraphQL queries on a single line
5. **Handle errors gracefully** - Check API responses before assuming success
