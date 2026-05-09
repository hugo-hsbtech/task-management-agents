# GitHub PR Command Reference

Detailed `gh` CLI and API patterns for GitHub pull request operations.

> **REMINDER**: Always create reviews as drafts by omitting the `event` field.
> See [SKILL.md](./SKILL.md) for the full safety rules and event field reference.

## Table of Contents

- [Fetching PR Data](#fetching-pr-data)
- [Creating Reviews](#creating-reviews)
- [Responding to Reviews](#responding-to-reviews)
- [Thread Management](#thread-management)

## Fetching PR Data

### Get unresolved review threads (GraphQL)

Use inline values in the query to avoid encoding issues:

```bash
gh api graphql -f query='query { repository(owner: "OWNER", name: "REPO") { pullRequest(number: PR_NUMBER) { title url reviewThreads(first: 100) { nodes { isResolved comments(first: 10) { nodes { id databaseId path line body author { login } createdAt } } } } } } }'
```

Filter for unresolved threads with jq:

```bash
... | jq '{
  title: .data.repository.pullRequest.title,
  url: .data.repository.pullRequest.url,
  unresolved_threads: [.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)]
}'
```

**IMPORTANT**: Keep the GraphQL query on a single line to avoid shell parsing issues.

### Extract comment from discussion URL

- URL format: `pull/438#discussion_r2673798141`
- Comment database ID: Remove "r" prefix → `2673798141`
- Query: `gh api repos/OWNER/REPO/pulls/comments/2673798141`

### Get recent comments (sorted)

```bash
gh api repos/OWNER/REPO/pulls/PR/comments | jq 'sort_by(.created_at) | reverse | .[0:10]'
```

## Creating Reviews

### Create a pending review with inline comments

````bash
cat <<'JSONEOF' | gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews --method POST --input -
{
  "body": "Review summary here",
  "comments": [
    {
      "path": "path/to/file.py",
      "line": 42,
      "side": "RIGHT",
      "body": "Comment body here. Use ```suggestion\ncode here\n``` for suggested changes."
    }
  ]
}
JSONEOF
````

### Inline comment fields

- `path`: File path relative to repo root (required)
- `line`: Line number in the file (required for single-line comments)
- `side`: `"RIGHT"` for new code, `"LEFT"` for removed code (required)
- `body`: Comment text, supports markdown and ```suggestion blocks (required)
- `start_line` + `start_side`: For multi-line comments

## Responding to Reviews

### Reply to existing review comment

```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments \
  --method POST \
  -f body="Reply text" \
  -F in_reply_to=COMMENT_ID
```

### Submit a pending review

**Only do this after user confirmation**:

```bash
gh api repos/OWNER/REPO/pulls/PR_NUMBER/reviews/REVIEW_ID/events \
  --method POST \
  -f event="REQUEST_CHANGES"
```

Use `"COMMENT"`, `"APPROVE"`, or `"REQUEST_CHANGES"` for the event field.

## Thread Management

### Resolve review thread (GraphQL mutation)

```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "THREAD_ID"}) {
    thread {
      isResolved
    }
  }
}'
```
