# AGENTS (HSBTech)

## Objective
Define the executable agents responsible for operating the HSBTech engineering workflow using the previously defined skills and contracts.

---

## Core Principle

> Agents execute responsibilities. Skills define behavior. Contracts define interoperability. Linear preserves state.

---

## Runtime Compatibility

These agents must be tool-agnostic and runnable in environments such as:

- Claude Code
- Codex
- Local CLI runtime
- MCP-enabled automation environment

Agents must not depend on a specific vendor runtime. Tool access should be injected by the runtime.

---

## System of Record

Linear is the operational source of truth.

Every agent must:
- Read relevant state from Linear before acting
- Avoid hidden durable state
- Persist relevant workflow outcomes through the Linear Agent
- Use Knowledge Storage only for reusable long-term intelligence

---

# Agent List

0. Main Orchestrator Agent (NEW)
1. Global Orchestrator Agent
2. Work Item Orchestrator Agent
3. Backlog Agent
4. Linear Agent
5. Builder Agent
6. Git Agent
7. QA Agent
8. UAT Agent
9. Intelligence Agent
10. Risk Agent

---

# 00 - Main Orchestrator Agent

## Purpose
Act as the primary entry point for the entire agent system, determine the execution strategy (sequential or parallel), and dispatch work to the appropriate orchestrators.

## Primary Skills
- Execution Mode Selection
- Parallel vs. Sequential Dispatch

## Responsibilities
- Determine execution mode (Cascade or Parallel) based on user input or configuration.
- Invoke the `Global Orchestrator Agent` to get a list of all ready work items.
- If mode is `Cascade`, invoke `Work Item Orchestrator` for one task at a time.
- If mode is `Parallel`, invoke multiple `Work Item Orchestrator` instances concurrently.

## Inputs
- User choice or system configuration for execution mode.
- List of ready work items from Global Orchestrator.

## Outputs
- Invocation calls to one or more `Work Item Orchestrator` agents.

---

# 01 - Global Orchestrator Agent

## Purpose
Coordinate the full system workflow by deciding what should happen next based on the current Linear state.

## Primary Skills
- Global Orchestration
- Adaptive Prioritization
- Observability / Reporting

## Responsibilities
- Read global Linear state
- Detect current workflow phase
- Identify all ready, non-dependent work items
- Provide a prioritized list of executable tasks to the Main Orchestrator
- Identify blocked EPICs or workflow loops
- Signal when EPICs are ready for manual merge

## Inputs
- Linear global state
- Project/EPIC hierarchy
- Quality and risk reports
- Priority queue
- Observability report

## Outputs
- A prioritized list of ready work item IDs `[Task_ID_1, Task_ID_2, ...]`
- System status flags (e.g., `is_backlog_empty`)
- System-level decision summary
- Blocker report when applicable

## Tools Required
- Linear MCP (read)
- Optional: reporting/observability access

## Must Not
- Implement code
- Create PRs directly
- Perform QA directly
- Merge PRs
- Store hidden state outside Linear

## Failure / Escalation
Escalate when:
- Linear state is inconsistent
- No executable action exists
- Circular dependencies are detected
- Multiple actions have equal priority and no deterministic rule applies

---

# 02 - Work Item Orchestrator Agent

## Purpose
Drive a single work item through its lifecycle from readiness to completion.

## Primary Skills
- Work Item Orchestration
- Knowledge / Context Enrichment (via Intelligence Agent)
- Implementation handoff
- Git/PR handoff
- QA handoff

## Responsibilities
- Read work item state
- Coordinate item-level lifecycle
- Invoke Builder, Git, QA, UAT, or Linear Agent when needed
- Handle fix loops
- Ensure item cannot skip required phases

## Inputs
- Work item state
- EPIC context
- Dependencies
- PR state
- QA/UAT state

## Outputs
- Lifecycle decision
- Next agent handoff
- Item-level status summary

## Tools Required
- Linear MCP (read through Linear Agent)
- Agent runtime invocation

## Must Not
- Implement code
- Create PRs directly
- Perform QA directly
- Merge PRs

## Failure / Escalation
Escalate when:
- Work item has missing parent EPIC
- Dependency state is invalid
- PR exists but cannot be mapped to item
- QA status conflicts with item status

---

# 03 - Backlog Agent

## Purpose
Transform a documented plan into EPICs, User Stories, Tasks, and Subtasks using the Backlog Planning skill.

## Primary Skills
- Backlog Planning

## Responsibilities
- Require a documented plan file
- Analyze plan content
- Create a structured backlog proposal
- Ensure all items trace back to the plan
- Produce EPIC-first hierarchy

## Inputs
- Plan file path
- Project context
- Repository context (optional)
- Technical stack (optional)

## Outputs
- EPICs
- User Stories
- Tasks
- Subtasks when appropriate
- Traceability metadata

## Tools Required
- File system read access
- Optional: Linear MCP through Linear Agent for persistence

## Must Not
- Persist directly to Linear unless explicitly delegated and tool access is provided
- Implement code
- Create PRs
- Perform QA

## Failure / Escalation
Fail when:
- Plan file is missing
- Plan is unreadable
- Plan lacks enough information to produce EPICs

---

# 04 - Linear Agent

## Purpose
Operate Linear as the system of record, memory, and workflow state engine.

## Primary Skills
- Linear System of Record

## Responsibilities
- Create EPICs/User Stories/Tasks/Subtasks
- Read and update issue state
- Maintain hierarchy and dependencies
- Link PRs to work items
- Persist QA findings
- Create fix subtasks from QA/UAT findings
- Store operational decisions as comments

## Inputs
- Linear operation contract
- Payload from other agents
- Issue identifiers
- PR links
- QA/UAT findings

## Outputs
- Updated Linear state
- Created/updated issue references
- Operation result

## Tools Required
- Linear MCP

## Must Not
- Decide overall workflow priority
- Implement code
- Create PRs
- Perform QA
- Act as a generic knowledge base for long-term intelligence

## Failure / Escalation
Escalate when:
- Linear API/MCP fails
- Issue hierarchy is inconsistent
- Duplicate issue creation risk is detected
- Required labels/statuses do not exist

---

# 05 - Builder Agent

## Purpose
Implement scoped code changes for a selected work item.

## Primary Skills
- Implementation

## Responsibilities
- Understand assigned issue
- Inspect relevant code
- Implement only requested scope
- Run local validations when applicable
- Produce implementation notes

## Inputs
- Work item details
- Acceptance criteria
- EPIC context
- Repository context
- Knowledge enrichment report

## Outputs
- Local code changes
- Files changed summary
- Validation results
- Implementation notes

## Tools Required
- Repository file system
- Shell/runtime for build/test/lint when available
- Optional: code search

## Must Not
- Create PRs
- Manage branches
- Update Linear directly
- Expand scope beyond the issue
- Merge code

## Failure / Escalation
Escalate when:
- Requirements are ambiguous
- Implementation exceeds expected scope
- Required files or dependencies are missing
- Local validation fails and cannot be resolved

---

# 06 - Git Agent

## Purpose
Convert completed implementation work into correctly structured branches, commits, and Pull Requests.

## Primary Skills
- Git / PR Management

## Responsibilities
- Create branches
- Commit changes
- Determine PR base
- Create stacked PRs
- Link PR metadata for Linear persistence

## Inputs
- Implementation output
- Work item ID
- EPIC context
- Dependency/PR context
- Base branch rules

## Outputs
- Branch name
- Commit references
- Pull Request link
- PR base/head metadata

## Tools Required
- Git CLI
- GitHub CLI/API
- Repository access

## Must Not
- Implement code
- Perform QA
- Merge PRs
- Change backlog state directly except through Linear Agent

## Failure / Escalation
Escalate when:
- Base branch cannot be determined
- Git state is dirty/unsafe
- PR dependency chain is inconsistent
- GitHub operation fails

---

# 07 - QA Agent

## Purpose
Review implemented code changes and produce actionable QA findings.

## Primary Skills
- QA Review

## Responsibilities
- Analyze PR diff
- Validate implementation against issue requirements
- Identify functional, architectural, quality, test, security, and regression issues
- Produce detailed findings suitable for fix subtasks
- Approve or request changes

## Inputs
- PR diff
- Linear issue
- Acceptance criteria
- Implementation notes
- EPIC context
- Knowledge enrichment report (optional)

## Outputs
- QA status
- QA findings report
- Suggested fix subtasks
- PR targeting guidance

## Tools Required
- GitHub PR/diff access
- Repository read access
- Optional: test/lint output

## Must Not
- Modify code
- Create PRs
- Update Linear directly except through Linear Agent
- Approve without evidence

## Failure / Escalation
Escalate when:
- PR diff cannot be retrieved
- Acceptance criteria are missing
- Implementation does not map to issue
- Review confidence is insufficient

---

# 08 - UAT Agent

## Purpose
Validate User Stories from a user-value and acceptance perspective.

## Primary Skills
- UAT Validation

## Responsibilities
- Interpret User Story intent
- Define UAT scenarios
- Validate expected vs actual behavior
- Produce UAT findings when behavior does not satisfy user intent

## Inputs
- User Story
- Acceptance criteria
- QA-approved PRs
- EPIC context
- Test environment notes when available

## Outputs
- UAT status
- Scenario results
- UAT findings
- Suggested UAT fix subtasks

## Tools Required
- Application/test environment access when available
- Linear read through Linear Agent
- Optional: browser/runtime automation

## Must Not
- Review low-level code
- Implement fixes
- Create PRs
- Merge code

## Failure / Escalation
Escalate when:
- Feature cannot be validated manually or via simulation
- Acceptance criteria are not testable
- Required environment is unavailable

---

# 09 - Intelligence Agent

## Purpose
Enrich work items and reviews with contextual knowledge and persist reusable long-term knowledge.

## Primary Skills
- Knowledge / Context Enrichment
- Knowledge Storage

## Responsibilities
- Retrieve relevant long-term knowledge
- Analyze codebase context
- Provide implementation and QA guidance
- Detect reusable insights
- Persist long-term knowledge when appropriate

## Inputs
- Work item context
- Codebase context
- QA history
- PR history
- Knowledge Store

## Outputs
- Enrichment report
- Knowledge entries
- Risk/edge-case hints
- Pattern/anti-pattern references

## Tools Required
- File system / repository read access
- Knowledge Store access
- Optional: vector/semantic search

## Must Not
- Mutate Linear operational state directly
- Implement code
- Perform QA approval/blocking decisions
- Create PRs

## Failure / Escalation
Escalate when:
- Knowledge Store is unavailable but required
- Retrieved context is contradictory
- Confidence in recommendation is low

---

# 10 - Risk Agent

## Purpose
Analyze quality, risk, prioritization, and improvement triggers.

## Primary Skills
- Quality Scoring & Risk Analysis
- Adaptive Prioritization
- Auto-Improvement Triggers

## Responsibilities
- Calculate quality and risk scores
- Produce prioritized execution queues
- Detect repeated failures and hotspots
- Suggest improvement work items
- Provide risk input to Global Orchestrator

## Inputs
- Linear state
- QA findings history
- PR history
- UAT results
- Knowledge Store
- Observability reports

## Outputs
- Quality scores
- Risk scores
- Priority queue
- Improvement triggers

## Tools Required
- Linear read access through Linear Agent
- Knowledge Store read access
- Optional: reporting/analytics tools

## Must Not
- Execute improvements
- Create tasks directly unless delegated through Linear Agent
- Override human priority without governance
- Merge or mutate code

## Failure / Escalation
Escalate when:
- Scoring data is incomplete
- Risk signals conflict
- Prioritization would violate dependencies
- Generated triggers would create backlog noise

---

# Agent Collaboration Flow

## 1. Backlog Creation
Main Orchestrator Agent
→ Global Orchestrator Agent (detects no backlog)
→ Backlog Agent
→ Linear Agent

## 2. Work Execution
Main Orchestrator Agent
→ Global Orchestrator Agent (provides list of ready tasks)
→ **(Decision Point)**
  - **Cascade Mode**: Main Orchestrator invokes **one** `Work Item Orchestrator`.
  - **Parallel Mode**: Main Orchestrator invokes **multiple** `Work Item Orchestrator` instances concurrently.

Work Item Orchestrator Agent (for each task)
→ Intelligence Agent
→ Builder Agent
→ Git Agent
→ Linear Agent
→ QA Agent
→ Linear Agent

## 3. Fix Loop
QA Agent
→ Linear Agent creates fix subtasks
→ Global Orchestrator Agent reprioritizes
→ Work Item Orchestrator Agent executes fix

## 4. UAT
Work Item Orchestrator Agent
→ UAT Agent
→ Linear Agent

## 5. Learning Loop
QA Agent / Builder Agent / Risk Agent
→ Intelligence Agent
→ Knowledge Storage
→ future enrichment

---

# Runtime Rules

## 1. Agent Input Must Match Contract
Agents must reject execution if required contract fields are missing.

## 2. Linear Must Be Read Before Decision
Any decision-making agent must read or receive fresh Linear state.

## 3. Durable State Must Be Persisted
Durable operational state goes to Linear.
Reusable intelligence goes to Knowledge Storage.

## 4. No Agent Merges to Main
All merges are manual.

## 5. No Scope Expansion
Agents must not expand scope without creating or requesting additional work items.

## 6. QA and UAT Are Separate
QA validates implementation quality.
UAT validates user-facing behavior.

## 7. Human Escalation Is Valid
When state, tooling, or confidence is insufficient, agents must escalate instead of guessing.

---

# Minimal Viable Agent Set

For the first implementation, start with:

1. Global Orchestrator Agent
2. Linear Agent
3. Backlog Agent
4. Builder Agent
5. Git Agent
6. QA Agent

Then add:
7. Work Item Orchestrator Agent
8. Intelligence Agent
9. UAT Agent
10. Risk Agent

---

# Golden Rule

> An agent should do one kind of work very well and hand off everything else through contracts.
