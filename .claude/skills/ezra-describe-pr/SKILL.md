---
name: ezra-describe-pr
description: Generate PR descriptions from branch changes for creating or updating pull requests
---

# Generate PR Description

Generate a fact-dense PR description from the current branch's changes, suitable for creating or updating a pull request.

## Steps to follow:

1. **Read the PR description template:**
   - Read `docs/_templates/pr-description-template.md` to understand the format
   - Summary is required; Context and Test plan are optional

2. **Gather branch information:**
   - Get current branch: `git branch --show-current`
   - Check if a PR already exists: `gh pr view --json url,number,title,state,baseRefName 2>/dev/null`
   - Get the base branch (default to `main` if no PR exists)
   - Get commit history: `git log main..HEAD --oneline`
   - Get the full diff: `git diff main...HEAD`
   - If you get an error about no default remote repository, instruct the user to run `gh repo set-default`

3. **Analyze the changes thoroughly:** (think deeply about the code changes, their architectural implications, and potential impacts)
   - Read through the entire diff carefully
   - For context, read any files that are referenced but not shown in the diff
   - Understand the purpose and impact of each change
   - Identify whether Context or Test plan sections are warranted

4. **Generate the description:**
   - Write a Summary that tells the reader what they don't already know
   - Include Context only when the "why" isn't obvious from the summary
   - Include Test plan only when changes are verifiable (skip for docs-only, config changes)
   - Omit optional sections entirely rather than leaving them empty

5. **Present the description to the user:**
   - Show the full generated description
   - Ask whether to create a new PR or update the existing one (if one exists)
   - Suggest a PR title based on the changes

6. **Create or update the PR:**
   - New PR: `gh pr create --title "..." --body "..."`
   - Existing PR: see Macroscope handling below, then update
   - Confirm the result and share the PR URL

## Macroscope bot handling

PRs in this repo have a Macroscope bot that auto-generates summaries between HTML comment markers (`<!-- Macroscope's pull request summary starts here -->` ... `<!-- ends here -->`). When updating an existing PR:

1. **Read the current body** first: `gh pr view {number} --json body -q '.body'`
2. **Prepend your description** above the Macroscope markers, separated by `---`
3. **Write the full body to a temp file** (`/tmp/pr-body.md`) — the Macroscope HTML comments contain characters that break shell quoting
4. **Use the REST API** to update — `gh pr edit` fails with a Projects Classic GraphQL error:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number} -X PATCH -f body="$(cat /tmp/pr-body.md)" --jq '.html_url'
   ```
5. **Verify** the update: `gh pr view {number} --json body -q '.body' | head -5`

## Writing style:

- **Fact-dense brevity.** Every sentence should contain information the reader doesn't already have.
- Don't summarize changes back to the author — they wrote them.
- Don't pad with transition phrases, compliments, or filler.
- Write like a human, not a bot. No robotic enumeration.
- Dense bullet points or a single paragraph are both fine — match the complexity of the changes.
- A docs-only PR might need one sentence. A complex feature might need a paragraph and bullets.