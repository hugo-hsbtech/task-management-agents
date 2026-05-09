---
name: ezra-commit
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Create git commits and relevant branches with user approval and no Claude attribution
---

# Commit Changes

You are tasked with organizing and committing the changes made during this session.

## Process:

1. **Assess the current branch:**
   - Run `git branch --show-current` to check where you are
   - Run `git status` and `git diff` to understand all changes
   - Review the conversation history to understand what was accomplished
   - Determine whether changes span multiple scopes of work (e.g. a feature + a refactor, or changes to unrelated systems)

2. **Suggest branches if needed:**
   - If on `main` with changes, suggest creating a branch
   - If changes span multiple scopes, suggest splitting them across separate branches
   - Present suggested branch names and which files go on each
   - Ask the user for approval before creating any branches

3. **Think about what changed:**
   - Consider whether changes should be one commit or multiple logical commits
   - Identify which files belong together

4. **Plan your commit(s):**
   - Draft clear, descriptive commit messages
   - Use imperative mood in commit messages
   - Focus on why the changes were made, not just what

5. **Present your plan to the user:**
   - List the files you plan to add for each commit
   - Show the commit message(s) you'll use
   - Ask: "I plan to create [N] commit(s) with these changes. Shall I proceed?"

6. **Execute upon confirmation:**
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages
   - Show the result with `git log --oneline -n [number]`

## Multi-Commit Workflow

When creating multiple commits from already-staged changes:

**CRITICAL**: Do not combine staging and committing in single bash commands.

**Process:**

1. Unstage everything: `git reset` (no flags - safe, keeps working directory changes)
2. For each commit:
   - Stage specific files: `git add <files>`
   - Show status: `git status`
   - **Wait for user verification**
   - Create commit: `git commit -m "message"`

**Why this matters:**

- Git staging is additive - `git add` adds to existing staged files
- Users need to verify what's being committed
- Complex operations are error-prone without checkpoints

**Amending:**

- `git commit --amend` only modifies HEAD
- To modify earlier commits, reset and redo the sequence

## Branch Naming

Follow the conventions used in this repo:

- **Type-based:** `feat/short-description`, `fix/short-description`, `chore/short-description`, `docs/short-description`
- **User-scoped:** `username/short-description` (e.g. `tyler/add-linear-ticket-skill`)
- Use lowercase, hyphen-separated words
- Keep names short but descriptive of the scope

## Multi-Branch Workflow

When changes need to be split across branches (e.g. on `main` with unrelated scopes):

1. **Stash everything:** `git stash --include-untracked`
2. **For each scope:**
   - Create and switch to branch: `git checkout -b <branch-name>`
   - Selectively restore files: `git stash pop` then stage only relevant files
   - Or use `git checkout stash -- <files>` to pull specific files
   - Commit the scoped changes
   - Switch back: `git checkout main`
   - Re-stash remaining changes if needed: `git stash`
3. **Present the full plan** (branch names, files per branch, commit messages) to the user **before executing**
4. After all branches are created, show the result with `git branch` and `git log --oneline` on each

**CRITICAL**: Always get user approval before creating branches or moving changes between them.

## Important:

- **NEVER add co-author information or Claude attribution**
- Commits should be authored solely by the user
- Do not include any "Generated with Claude" messages
- Do not add "Co-Authored-By" lines
- Write commit messages as if the user wrote them

## Remember:

- You have the full context of what was done in this session
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit

## Related Skills

- `/ezra-create-pr` — full PR preparation workflow that uses this skill's commit patterns for all fix commits
- `/ezra-describe-pr` — generate PR descriptions after committing
