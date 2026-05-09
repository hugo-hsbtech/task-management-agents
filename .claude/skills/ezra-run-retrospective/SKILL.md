---
name: ezra-run-retrospective
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] Automated retrospective that reviews session history to identify improvements.
version: 1.0.0
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Retrospective

Automated session analysis that identifies friction points and proposes concrete improvements to CLAUDE.md, documentation, and skills.

## Core Principle

Extract learnings from session history automatically—no user interviews. Focus on actionable improvements that will help future sessions avoid the same struggles.

## When to Use

Invoke this skill:
- After completing a task that involved significant debugging or investigation
- When you want to capture what was learned during a session
- At the end of a work session to identify improvement opportunities
- When the agent struggled or took multiple attempts to complete a task

## Analysis Process

### Step 1: Review Session History

Analyze the conversation transcript for:

**Friction Indicators:**
- Multiple attempts or iterations to solve the same problem
- Repeated clarifications needed from the user
- Difficulty finding files or understanding codebase structure
- Errors or issues that took significant time to debug
- Workarounds for missing documentation or unclear patterns
- Trial-and-error debugging that could have been avoided

**Success Indicators:**
- What worked well and should be preserved
- Effective use of tools, skills, or documentation
- Clear patterns that were followed correctly
- Efficient problem-solving approaches

**Non-Obvious Discoveries:**
- Solutions that required investigation beyond documentation
- Patterns or conventions discovered through code exploration
- Error messages that were misleading or required interpretation
- Configuration or setup knowledge not documented

### Step 2: Categorize Findings

Organize discoveries into categories:

#### CLAUDE.md Updates
Conventions, patterns, or pitfalls that should be added to project-level CLAUDE.md:
- Code patterns that agents frequently get wrong
- Project-specific conventions not obvious from code
- Known pitfalls or error-prone areas
- Testing conventions and requirements
- Verification steps for specific types of changes

##### CLAUDE.md Placement Guidelines

When proposing CLAUDE.md updates, specify the target file path explicitly.

**Hierarchy principle**: Place guidance at the most specific level where it applies.

| Level | Path Pattern | Content |
|-------|--------------|---------|
| Monorepo | `/CLAUDE.md` | Cross-cutting: testing standards, shared conventions |
| Claude-specific | `/.claude/CLAUDE.md` | Skill usage, GitHub workflows, tool patterns |
| Submodule | `/<submodule>/CLAUDE.md` | Architecture, tech stack, domain patterns |
| Subdirectory | `/<submodule>/<dir>/CLAUDE.md` | Local conventions, gotchas, specialized patterns |

**Before adding to a CLAUDE.md**:
1. Check if guidance already exists in a parent CLAUDE.md (avoid duplication)
2. Determine scope: applies broadly (parent) or specifically (this directory)
3. For testing patterns, reference the testing docs index rather than duplicating
4. Convert legacy `.cursorrules`/`.claude-rules` files to CLAUDE.md format when found

#### Documentation Gaps
Missing or outdated documentation:
- Guides that don't exist but should
- Outdated documentation that caused confusion
- Unclear explanations of architecture or patterns
- Missing examples or usage instructions

#### Skill Candidates
Knowledge worth extracting to reusable skills:
- Non-obvious debugging techniques discovered
- Tool integration patterns that required experimentation
- Project-specific workflows that apply across tasks
- Error resolution patterns that could recur

#### Codebase Issues
Structural problems that made the task harder:
- Components that are too large or poorly organized
- Unclear naming that caused confusion
- Missing abstractions that would help
- Test infrastructure issues

### Step 3: Propose Concrete Improvements

For each finding, provide:
- **Specific problem**: What made the task harder?
- **Root cause**: Why did this happen?
- **Proposed fix**: Exact change to make (with diffs/patches when applicable)
- **Impact**: How will this help future sessions?

## Self-Reflection Questions

Use these to guide analysis:

- What did I struggle with that wasn't obvious from CLAUDE.md or documentation?
- What would I wish CLAUDE.md told me before starting this task?
- What error messages or symptoms were misleading?
- Did I follow existing patterns, or invent new approaches? Why?
- What patterns should be codified for future sessions?
- Were there files I couldn't find easily? Why?
- Did tests work as expected? Were conventions clear?
- What verification steps did I use? Could they be automated?
- What would make this task faster next time?

## Output Format

Generate a structured retrospective with this format:

```markdown
# Session Retrospective: [Brief Task Description]

**Date:** [Today's date]
**Duration:** [Approximate session length if clear from context]

---

## Summary

[2-3 sentence summary of what was accomplished and the main learnings]

---

## What Worked Well

[List specific successes - what patterns, tools, or approaches were effective]

- [Success 1]
- [Success 2]
...

---

## Friction Points Identified

[Specific struggles with examples from the session]

### [Friction Category 1]
**Problem:** [What happened]
**Example:** [Quote or reference from session]
**Root Cause:** [Why it happened]

### [Friction Category 2]
...

---

## Proposed Improvements

### CLAUDE.md Updates

#### [Update 1: Title]
**Rationale:** [Why this is needed]

**Proposed Addition:**
```markdown
[Exact text to add to CLAUDE.md]
```

**Location:** [Where in CLAUDE.md this should go]

---

### Documentation

#### [Doc Update 1: Title]
**Issue:** [What's missing or wrong]
**Proposed Fix:** [What to create/update]
**Priority:** [High/Medium/Low]

---

### Skill Candidates

#### [Skill 1: Name]
**Trigger Conditions:** [When would this skill be useful?]
**Knowledge to Capture:** [What should the skill contain?]
**Priority:** [High/Medium/Low]

**Proposed Skill Description:**
```
[Draft description following skill pattern]
```

---

### Codebase Improvements

#### [Improvement 1: Title]
**Problem:** [Structural issue that caused friction]
**Impact:** [How this affects development]
**Suggested Refactoring:** [What to change]
**Priority:** [High/Medium/Low]

---

## Action Items

- [ ] [Concrete next steps with owners if applicable]
- [ ] Review proposed CLAUDE.md updates and submit PR
- [ ] Create issues for high-priority codebase improvements
- [ ] Consider implementing high-priority skill candidates
...

---

## Notes

[Any additional context, caveats, or observations]
```

## Quality Standards

Before finalizing output, verify:

- [ ] Each finding references specific examples from the session
- [ ] Proposed improvements are concrete and actionable (not vague)
- [ ] CLAUDE.md additions are specific enough to be useful
- [ ] Skill candidates have clear trigger conditions
- [ ] Root causes are identified, not just symptoms
- [ ] Impact/priority is assessed realistically
- [ ] No sensitive information (credentials, internal URLs) included

## Path Formatting

When referencing files in retrospectives:
- Use relative paths from repo root (e.g., `.claude/skills/...`)
- Never use absolute paths (e.g., `/Users/...`)
- This ensures documentation works for all team members

## Save Location

Save retrospectives to:
```
docs/retrospectives/YYYY-MM-DD-task-slug.md
```

Create the directory if it doesn't exist.

## Integration Notes

This skill is designed to be invoked manually at the end of sessions. Future enhancements could include:
- Automatic triggering after certain types of tasks
- Integration with commit hooks to capture learnings per PR
- Periodic reviews of multiple retrospectives to identify patterns

## Example Triggers

Invoke this skill when:
- User runs `/retrospective` command
- User asks "what did we learn?" or "review this session"
- After completing a task that involved significant debugging
- When extracting knowledge for improvement (Claudeception-style)

## Remember

The goal is continuous improvement through objective analysis. Focus on:
- Concrete, actionable improvements
- Patterns that will genuinely help future sessions
- Root causes, not just symptoms
- Preserving successes as well as addressing failures