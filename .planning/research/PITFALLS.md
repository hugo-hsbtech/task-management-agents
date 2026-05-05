# Domain Pitfalls: Multi-Agent AI Engineering Workflow

**Domain:** Multi-agent AI engineering orchestration with Linear state machine, stacked PRs, QA loops, and human-controlled merges
**Researched:** 2026-05-05
**Project:** HSBTech AI Engineering Workflow

---

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or system collapse.

---

### Pitfall 1: Non-Atomic Task Claiming Allows Double-Work in Parallel Mode

**What goes wrong:** In Parallel Mode, two Work Item Orchestrators both read Linear state, both see LIN-123 as `todo`, and both claim it by setting `status = in_progress`. Because the MCP write round-trip is not a compare-and-swap, one agent overwrites the other's claim. Both agents implement the same task, create conflicting branches, and open duplicate PRs. The second write silently wins, making the first agent's claim invisible.

**Why it happens:** Linear's MCP `update` operation is not an atomic check-and-set. Reading state and writing state are separate calls. The window between `read todo` and `write in_progress` is enough for a second agent to read the same state.

**Consequences:** Duplicate PRs from the same task, conflicting branches in the EPIC branch, wasted compute, confused QA state in Linear, and manual cleanup work.

**Prevention:**
- Implement claim verification: after writing `status = in_progress`, immediately re-read the item from Linear and confirm `assignee` or a custom `claimed_by` field matches this orchestrator's execution_id.
- If the re-read does not match, abort this orchestrator's cycle for that item.
- In the Main Orchestrator claiming loop, add a configurable delay between claims to reduce the collision window.
- Treat all claiming operations as optimistic locks: claim, verify, proceed — or skip.

**Warning signs:** Two branches with the same Linear ID prefix appear in git. Two open PRs targeting the same EPIC branch for the same task.

**Phase to address:** Core parallel execution phase. Claiming atomicity must be validated before enabling Parallel Mode in any environment.

---

### Pitfall 2: QA Loop Runaway — Fix Subtasks Breeding More Fix Subtasks

**What goes wrong:** QA Agent reviews a PR and generates 5 fix subtasks. The Builder Agent implements those fixes. QA reviews again and finds 4 new issues — some introduced by the fixes themselves. A new batch of fix subtasks appears. The loop continues indefinitely. Without a hard stop, a single task can accumulate 20-30 subtasks before a human intervenes.

**Why it happens:** AI QA agents with broad review mandates will always find something to flag. Each implementation pass introduces new surface area. Without a termination condition, the system optimizes for thoroughness, not completion. The max_fix_subtasks = 5 cap limits each individual QA report, but does not limit the total number of QA cycles per task.

**Consequences:** Backlog explosion, EPIC never closes, human loses trust in the system, work items consume disproportionate resources.

**Prevention:**
- Add a `qa_cycle_count` field to each work item in Linear. Increment it on every QA failure.
- Define a hard `max_qa_cycles` limit (recommended: 3). When exceeded, halt the loop and flag the item for human review — do not create more subtasks.
- Distinguish between blocking findings (must fix) and non-blocking findings (may fix later). Only blocking findings should generate fix subtasks.
- The QA Agent must have explicit instructions: "If all remaining findings are non-blocking, approve the PR and annotate findings as tech debt."
- Track rework index in the Risk Agent to surface chronically-looping tasks early.

**Warning signs:** A work item has more than 2 QA review cycles. A task has more than 10 total subtasks. The same QA finding category (e.g., `code_quality`) appears in consecutive reviews.

**Phase to address:** QA loop design phase. The termination condition and rework counter must exist before any automated QA execution.

---

### Pitfall 3: Stacked PR Base Branch Drift Causes Cascading Merge Conflicts

**What goes wrong:** Task PRs A and B both target the EPIC branch. PR A is merged into the EPIC branch (by a human or via review approval). PR B now has a stale base — it was opened against the EPIC branch before PR A landed, so the shared commit ancestor is no longer the branch tip. When the Git Agent or a human tries to merge PR B, GitHub reports merge conflicts even when no files actually conflict logically.

**Why it happens:** Squash merges and rebase merges both rewrite commit hashes. The base branch that PR B was opened against no longer exists at that SHA. GitHub cannot automatically reconcile this.

**Consequences:** PRs appear broken when they are not. Human must manually rebase and force-push the branch. If multiple tasks are in-flight simultaneously, each merge triggers a rebase cascade for all remaining open PRs.

**Prevention:**
- After every PR merge into the EPIC branch, the Git Agent must check all remaining open task PRs targeting that EPIC branch and rebase them (using `git rebase epic-branch` on each task branch, then force-push).
- Automate this as a dedicated action type: `REBASE_STACK`. Triggered after any PR merge into an EPIC branch.
- Use GitHub's `gh stack sync` pattern — cascade rebases atomically from the lowest unmerged PR upward.
- Add PR merge order as a field in the work item context so the Git Agent always knows which PRs are ahead in the stack.
- Never open multiple task PRs targeting the same EPIC branch without tracking their ordering dependency.

**Warning signs:** A PR shows merge conflicts but the file changes are in separate directories. A task PR's base branch SHA does not match the current EPIC branch tip.

**Phase to address:** Git and PR management phase. The rebase cascade trigger must be designed before any parallel task execution is attempted.

---

### Pitfall 4: Linear State Drift — Agent Acts on Stale State

**What goes wrong:** An orchestrator reads Linear state at cycle start. A network delay, MCP timeout, or parallel write from another orchestrator changes the state between the read and the action. The orchestrator acts on state that is no longer accurate — for example, executing a task that another agent has already started, or creating fix subtasks for a QA finding that was already resolved.

**Why it happens:** Linear's MCP layer does not provide subscription or real-time push. Every read is a point-in-time snapshot. In parallel execution, the snapshot can become stale within seconds.

**Consequences:** Duplicate work, contradictory state in Linear, QA findings created against resolved items, subtasks linked to wrong parent states.

**Prevention:**
- Enforce the "always read Linear first" rule at the Work Item Orchestrator level, not just the Global Orchestrator level. Before every action — not just at cycle start — re-read the specific work item's current state.
- Compare the pre-action state hash (or `updatedAt` timestamp) against the post-claim read. If they differ, abort the action and restart the cycle.
- Treat Linear's `updatedAt` field as an optimistic lock version number.
- Add a structured pre-flight check in the Work Item Orchestration contract: `"linear_state_validated_at": ISO timestamp` must appear in every action envelope.

**Warning signs:** A work item has contradictory status fields (e.g., `status: done` but `qa_status: pending`). Two fix subtasks with identical titles exist under the same parent.

**Phase to address:** Runtime loop design phase (MVP). Pre-flight state validation must be built into the Work Item Orchestrator contract from the first iteration.

---

### Pitfall 5: Context Window Exhaustion Mid-Lifecycle — Silent Instruction Dropout

**What goes wrong:** A Builder Agent session handles a large task — reads 15 files, generates implementation notes, creates a PR, then QA produces findings with a 5-item fix list. By the time the fix cycle begins, the agent's context is 70-80% full. The original acceptance criteria from Linear, the architectural constraints from the EPIC context, and the implementation decisions from the first cycle are all in the oldest portion of the context. Auto-compaction summarizes them, losing specificity. The agent continues confidently but is now implementing against a lossy summary, not the original requirements.

**Why it happens:** LLMs concentrate attention on the beginning and end of context. Middle content — where initial requirements often live after a long session — receives degraded attention. Auto-compaction keeps recent content but truncates older content to fit the token budget. Skills get a combined 25,000-token re-attach budget after compaction, and older invocations are dropped first.

**Consequences:** Implementation diverges from requirements in subtle ways. QA flags issues that seem like new bugs but are actually context-loss artifacts. The system accumulates technical debt from "plausible but wrong" implementations.

**Prevention:**
- Never rely on conversation history to carry requirements through a multi-cycle lifecycle. Externalize all durable requirements to Linear and re-inject them fresh at each new cycle.
- The Work Item Orchestrator must pass the full Linear issue (description, acceptance criteria, implementation notes from prior cycles) as explicit structured input on every invocation — not as conversational memory.
- Each agent skill invocation should be treated as stateless: it receives all context it needs in its input contract, and it writes all durable results to its output contract.
- Monitor token budget at the start of each cycle. If the session is over 60% of context capacity, emit a `context_budget_warning` in the result envelope.
- Use `context: fork` (subagent mode) for Builder and QA executions to run them in isolated contexts rather than accumulating state in one long session.

**Warning signs:** The Builder Agent's implementation notes for a fix cycle omit references to constraints that were stated in the original task. QA findings in cycle 2 include issues that were already addressed in cycle 1.

**Phase to address:** Agent contract design phase. The stateless input contract pattern must be enforced from the start. Context budget monitoring should be added as an operational health feature.

---

## Moderate Pitfalls

Mistakes that cause rework, friction, or degraded reliability.

---

### Pitfall 6: Linear MCP Rate Limits During Batch Backlog Creation

**What goes wrong:** The Backlog Agent parses a large plan and generates an EPIC with 6 user stories, 18 tasks, and 45 subtasks. Each Linear entity requires at minimum one MCP call to create and another to link to its parent. A full backlog creation can require 100-150 MCP operations. With a limit of 2,500 requests per hour (API key auth) and a 10,000-point per-query complexity cap, a large backlog creation batch hits rate limits partway through, leaving the Linear hierarchy in a partially-created state with orphaned items.

**Prevention:**
- Implement exponential backoff with jitter on all Linear MCP calls. Treat `429 Too Many Requests` as a retriable error, not a failure.
- Batch creation: create all EPICs first, then user stories, then tasks, then subtasks. Never create children before confirming parent IDs.
- Persist progress checkpoints: after each entity is created and confirmed in Linear, record its ID in the in-progress backlog output. If the operation fails, resume from the last confirmed ID.
- Cap GraphQL query complexity by querying items individually rather than in deeply nested single queries. The 10,000-point limit is easily hit when fetching an EPIC with all children in one query.

**Warning signs:** Partial Linear hierarchy with some tasks missing parent links. MCP calls returning `error_type: tool_failure` with HTTP 429 in the message body.

**Phase to address:** Backlog planning and Linear integration phase.

---

### Pitfall 7: Skill Description Drift Causes Wrong Skill Auto-Invocation

**What goes wrong:** Claude Code loads skill descriptions into context and uses them to decide when to invoke a skill automatically. As skills evolve, their descriptions are updated, but the `when_to_use` and `description` fields drift out of sync with actual skill behavior. The QA Review skill gets invoked when the user asks about code quality in conversation. The Backlog Planning skill triggers when the user asks "what should we build next?" The auto-invocation behavior becomes unpredictable.

**Why it happens:** Skill descriptions are the only routing mechanism for auto-invocation. They are written once and rarely reviewed. All skill descriptions share a combined character budget (1,536 characters each, 8,000 total fallback). Overly broad descriptions win routing conflicts against specific ones.

**Consequences:** Agents execute skills out of sequence, potentially mutating Linear state when only a read was intended, or creating backlog items from a casual conversation.

**Prevention:**
- Set `disable-model-invocation: true` for all skills that have side effects (backlog creation, PR creation, fix subtask creation, status updates). Only Claude should auto-invoke read-only or enrichment skills.
- Write skill descriptions as `"Only invoke when: [precise conditions]"` rather than `"Use when: [broad scenario]"`.
- Review all skill descriptions when adding a new skill, to check for routing conflicts.
- Treat skills with Linear write operations as operator-invocable only via explicit `run action <ACTION_TYPE>` commands.

**Warning signs:** Linear state is updated during a conversational session not initiated with `run next step`. A skill is invoked with no prior `execution_id` in the result envelope.

**Phase to address:** Skill design phase. Add `disable-model-invocation` as a default for all write-operation skills before any skills are shipped.

---

### Pitfall 8: UAT Agent Scope Creep — Validating What Was Not Built

**What goes wrong:** The UAT Agent receives a user story and acceptance criteria, then validates behavior against the acceptance criteria. However, the UAT Agent, lacking tight scope constraints, also "notices" adjacent behaviors — related features not implemented in this EPIC, deprecated workflows, or missing features from the roadmap — and generates findings for them. These findings create fix subtasks for work that was never in scope for this cycle.

**Why it happens:** LLM-based agents are curious by default. Without an explicit scope boundary in the UAT skill, the agent evaluates "what a user would expect" rather than "what this user story committed to deliver." The difference is subtle in the prompt but significant in outcome.

**Consequences:** Fix subtasks appear for out-of-scope work. The EPIC cannot close because UAT findings reference unimplemented features. Human must manually close spurious findings.

**Prevention:**
- The UAT input contract must include a `scope_boundary` field: `"Only validate acceptance criteria listed in this document. Do not evaluate features not listed in acceptance_criteria."` This must appear as an explicit constraint in the UAT skill instructions, not just in the input schema.
- UAT findings must each reference the specific acceptance criterion they address. Findings without an `acceptance_criterion_id` reference should be rejected by the schema validator.
- Add an anti-hallucination check: the UAT Agent must not create findings for behaviors not testable from the provided PR diff.

**Warning signs:** UAT findings reference features not mentioned in the acceptance criteria. A UAT finding's `related_requirement` field is empty or says "general usability."

**Phase to address:** UAT agent design phase.

---

### Pitfall 9: QA Agent Hallucinated Findings — False Positives on Correct Code

**What goes wrong:** The QA Agent reviews a PR diff and generates a finding for a pattern it "believes" is an anti-pattern, but the pattern is correct for this codebase (an intentional architecture decision, a project convention, or a framework-specific idiom). The finding generates a fix subtask. The Builder Agent "fixes" it. QA reviews again, now finds the code is wrong (because the fix broke the intentional pattern), and generates a new finding. The cycle repeats.

**Why it happens:** LLMs have strong priors from training data. Without codebase-specific context, the QA Agent applies generic best practices that contradict project-specific decisions. This is most acute for architecture decisions, framework idioms, and deliberate trade-offs.

**Consequences:** False positive QA cycles consuming implementation time. Builder Agent introduces regressions by "fixing" correct code.

**Prevention:**
- The Knowledge Store must include an `architecture` category entry for all deliberate architectural decisions. The QA skill must load this context before generating findings.
- QA findings must require `evidence.file` and `evidence.location` fields to be non-empty — findings without file-level evidence are invalid.
- Severity `low` and `medium` findings that conflict with a known architecture decision in the knowledge store should be automatically downgraded to `non_blocking`.
- Add an explicit "known patterns" section to the QA Review skill: "Before flagging a pattern as an anti-pattern, check the knowledge store for architecture entries that justify it."

**Warning signs:** A QA finding's `category` is `architecture` but the `evidence.related_requirement` field does not reference a user story or acceptance criterion. The same code pattern is flagged in consecutive QA cycles.

**Phase to address:** QA agent design phase and Knowledge Store design phase. Architecture context must be in the knowledge store before QA runs on any non-trivial code.

---

### Pitfall 10: Over-Automation — Human Judgment Replaced Where It Must Be Retained

**What goes wrong:** The system operates smoothly through MVP and the team begins automating more decision points. The Risk Agent's adaptive prioritization begins auto-selecting which tasks to run next without human review. The Improvement Trigger auto-creates improvement tasks in Linear without human approval. The QA Agent's approval starts being treated as equivalent to human code review. The human's role gradually shifts from decision-maker to approver of AI-generated approvals.

**Why it happens:** Automation success creates momentum toward more automation. Each agent's output appears reasonable, so humans begin skipping review. The system's guardrails (no auto-merge to main) are preserved, but the decisions feeding into what gets merged have been quietly automated.

**Consequences:** Poor architectural decisions accumulate. Risk assessments miss project-specific context only a human understands. Improvement tasks crowd the backlog with AI-generated work that does not reflect actual priorities.

**Prevention:**
- Document explicitly which decisions require human judgment and cannot be delegated to agents: architectural direction, priority overrides, scope change approval, improvement task acceptance, and risk threshold calibration.
- Auto-Improvement Triggers must require explicit human approval before Linear entities are created. The `linear_state: "suggested"` status should gate actual backlog creation.
- Global Orchestrator reports must be human-readable summaries, not just machine-readable JSON. The human must be able to understand what the system is doing without reading logs.
- Treat the human's `run next step` confirmation as a checkpoint for reviewing the proposed action, not just a trigger. The decision envelope must surface the rationale, not just the action type.

**Warning signs:** The human can no longer explain why a specific task was prioritized by the system. Improvement tasks appear in Linear that no human requested. The QA approval rate exceeds 90% without any human-flagged issues in a high-complexity codebase.

**Phase to address:** Orchestration design phase and CLI loop design phase. The human-readable decision envelope must be prioritized as a first-class output, not an afterthought.

---

## Minor Pitfalls

---

### Pitfall 11: Branch Naming Collisions in Long-Running EPICs

**What goes wrong:** Two tasks with similar short slugs produce identical branch names. `feature/LIN-123-add-auth` and `feature/LIN-124-add-auth-ui` both get slugified to `feature/LIN-12*-add-auth`. The Git Agent pushes the second branch and silently overwrites or conflicts with the first.

**Prevention:** Always include the full Linear ID as the first segment of the branch slug: `feature/LIN-123-<slug>`. Slug generation should strip only special characters, not truncate the ID. Add a pre-push branch uniqueness check via `gh` or `git ls-remote`.

**Phase to address:** Git agent skill design.

---

### Pitfall 12: Knowledge Store Pollution — Low-Quality Entries Accumulate

**What goes wrong:** The Intelligence Agent creates knowledge entries after every cycle. Over time, entries accumulate that are vague, contradictory, or duplicates of existing entries. The Knowledge Enrichment skill loads this context into Builder Agent sessions, increasing noise and token usage without increasing quality.

**Prevention:** Knowledge entries must pass a minimum quality bar before persistence: `insight` field must be non-empty, `evidence.linear_issue` or `evidence.pr` must be populated, and `applicability` must describe a specific condition. The Risk Agent's auto-improvement cycle should include a periodic knowledge store audit that flags entries without evidence links for human review.

**Phase to address:** Knowledge Store design phase.

---

### Pitfall 13: Fix Subtask PR Targeting Errors

**What goes wrong:** A fix subtask is created targeting a QA finding in the original task PR (LIN-123). The Git Agent creates a fix branch targeting the EPIC branch (the default) rather than the task's PR branch. The fix lands in the EPIC but not in the task PR, so the task PR still shows the unfixed code during QA re-review.

**Why it happens:** The default Git Agent behavior targets the EPIC branch. Fix subtasks need to target the original task's PR branch, not the EPIC branch. This routing logic must be explicit in the fix subtask creation contract.

**Prevention:** The `FIX_CREATE` action must populate `pr_targeting_guidance.target_pr` with the original task's PR branch, not the EPIC branch. The Git Agent must read this field and use it as the base branch — never default to the EPIC branch for fix subtasks.

**Warning signs:** QA re-review still shows the unfixed code after a fix subtask is marked done. The fix PR's base branch is the EPIC branch, not the task branch.

**Phase to address:** Fix loop design phase and Git agent skill design.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Parallel execution (Main Orchestrator) | Double-claiming (Pitfall 1), stale state (Pitfall 4) | Claim verification loop, `updatedAt` optimistic lock |
| QA loop implementation | QA runaway (Pitfall 2), hallucinated findings (Pitfall 9) | `max_qa_cycles` counter, evidence-required findings schema |
| Git / PR management | Stacked PR base drift (Pitfall 3), fix targeting errors (Pitfall 13), branch collision (Pitfall 11) | REBASE_STACK action, explicit `target_pr` in fix contracts |
| Backlog creation (Linear) | Rate limit partial state (Pitfall 6) | Exponential backoff, checkpoint persistence |
| Skill authoring | Auto-invocation routing conflicts (Pitfall 7) | `disable-model-invocation: true` for all write-operation skills |
| UAT agent design | Scope creep findings (Pitfall 8) | Explicit `scope_boundary` field in UAT input contract |
| Knowledge Store design | Knowledge pollution (Pitfall 12) | Minimum quality bar on evidence fields |
| CLI loop and automation | Context exhaustion (Pitfall 5) | Stateless input contract pattern, context budget monitoring |
| Orchestration evolution | Over-automation (Pitfall 10) | Human-readable decision envelope, approval-gated improvement tasks |

---

## Sources

- Linear API Rate Limiting: https://linear.app/developers/rate-limiting (HIGH confidence — official Linear documentation, accessed 2026-05-05)
- MCP Server Reliability Study (100 servers stress-tested): https://www.digitalapplied.com/blog/mcp-server-reliability-100-server-stress-test-study (MEDIUM confidence)
- Claude Code Skills Documentation: https://code.claude.com/docs/en/skills (HIGH confidence — official Anthropic documentation, accessed 2026-05-05)
- Stacked PR Workflow and Conflict Patterns: https://www.davepacheco.net/blog/2025/stacked-prs-on-github/ (MEDIUM confidence)
- GitHub gh-stack Extension: https://github.github.com/gh-stack/ (MEDIUM confidence)
- AI Agent QA Infinite Loop Prevention: https://www.fixbrokenaiapps.com/blog/ai-agents-infinite-loops (MEDIUM confidence)
- Harness Engineering for AI Coding Agents: https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents (MEDIUM confidence)
- Context Window Degradation: https://factory.ai/news/context-window-problem (MEDIUM confidence)
- Multi-Agent Memory Engineering: https://www.oreilly.com/radar/why-multi-agent-systems-need-memory-engineering/ (MEDIUM confidence)
- Concurrent State Access Pitfalls: https://www.augmentcode.com/guides/debug-parallel-ai-agents (MEDIUM confidence)
- LLM Hallucinations in Code Review: https://diffray.ai/blog/llm-hallucinations-code-review/ (MEDIUM confidence)
- Human-in-the-Loop Patterns: https://zapier.com/blog/human-in-the-loop/ (MEDIUM confidence)
- Over-Automation Problem: https://siliconangle.com/2026/01/18/human-loop-hit-wall-time-ai-oversee-ai/ (MEDIUM confidence)
