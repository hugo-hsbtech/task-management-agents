# Feature Landscape

**Domain:** Multi-agent AI engineering workflow / agentic task management
**Project:** HSBTech AI Engineering Workflow
**Researched:** 2026-05-05
**Overall confidence:** HIGH (grounded in project spec + 2025-2026 ecosystem evidence)

---

## Table Stakes

Features users expect from an agentic engineering workflow system. Missing = product feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Work item hierarchy (EPIC → User Story → Task) | Standard project tracking mental model; Linear already enforces this | Low | Already specified in plan.md; structure is non-negotiable for traceability |
| Linear as system of record | Prevents hidden state across agent boundaries; single truth source | Low-Med | MCP integration is the mechanism; agents read/write all state transitions here |
| Automated task-to-branch-to-PR pipeline | Core value of the system; without this it is just a chatbot | High | Every task completion must produce a reviewable artifact |
| Stacked PR targeting (task → story → epic → main) | Without this, merge chains are manual and fragile | Med | gh-stack / GitHub native stacked PR support now exists; targeting hierarchy must be correct from creation |
| Draft PR on EPIC branch at kickoff | Establishes the merge surface before any task work begins | Low | Standard practice; draft communicates work-in-progress to human reviewers |
| Human approval gate — no auto-merge | Without this, system is unusable in any professional setting | Low (policy) | This is a constraint, not a feature to build; enforce via no merge command in any agent |
| QA agent review of every PR diff | Code review against acceptance criteria before marking done | High | Independent from builder; must receive only the diff, not builder reasoning — adversarial stance is critical |
| Fix subtask generation from QA findings | Closing the loop; otherwise QA findings are documentation, not work items | Med | Cap at max 5 subtasks per QA report to prevent backlog explosion |
| UAT instructions on PRs | Human testers need to know what to verify; without this, manual testing is inconsistent | Low-Med | Generated from user story acceptance criteria; required on all US PRs and applicable task PRs |
| Dependency awareness before execution | Agent must not start a blocked or dependency-unmet task | Med | Global Orchestrator reads Linear blocked-by / relates-to links before dispatching |
| Structured agent contracts (JSON I/O schemas) | Without typed boundaries, debugging multi-agent failures is nearly impossible | Med | Already defined in AGENT-CONTRACTS.md; every agent input/output must be machine-readable |
| Traceable state transitions in Linear | Audit trail of every agent action; required for human oversight and debugging | Low-Med | Comment on every Linear issue when state changes; never rely on ephemeral agent memory |
| CLI trigger mode (manual assisted) | Humans must be able to step through the workflow deliberately before trusting automation | Low | `run next step` interface; do not skip this in favor of going fully autonomous on day one |

---

## Differentiators

Features that set this system apart from raw AI coding tools (Devin, Copilot, Cursor). Not expected, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Three-level orchestration hierarchy | Main → Global → Work Item separates concerns cleanly; most systems conflate mode selection with task dispatch | High | Unique: mode selection (cascade vs parallel), readiness detection, and per-item lifecycle management are distinct responsibilities |
| One-action-per-cycle constraint | Prevents runaway automation; each orchestrator tick is observable and reversible | Low (policy) | Deliberately limits autonomy; this is a trust-building feature, not a limitation |
| Intelligence / codebase enrichment agent | Agents that understand the codebase produce better implementations; pure task-spec execution misses architectural context | High | Enriches tasks before dispatch with relevant patterns, prior decisions, related modules |
| Persistent knowledge store | Accumulates QA insights, architectural decisions, reusable patterns across cycles | Med-High | File-based for simplicity; feeds enrichment agent; differentiator vs stateless agents like Devin |
| Risk agent + adaptive prioritization | Surfaces fragile tasks before they block delivery; most tools prioritize by date or human judgment only | High | Quality scoring, risk assessment, feeds Global Orchestrator priority queue |
| Runtime-agnostic agent design (skills as markdown) | Works with Claude Code, Codex, or future runtimes without code changes | Med | Skills are prompt specs, not imperative code; this is a significant architectural bet worth the complexity |
| UAT validation loop as first-class citizen | UAT is usually bolted on; making it a required agent gate before work item completion elevates delivery quality | Med | UAT agent validates user stories from user-acceptance perspective after QA approval; generates structured test evidence |
| Structured findings format from QA | QA output is a machine-readable report, not freeform comments; enables downstream automation (fix subtasks, risk scoring) | Med | Findings schema feeds Risk Agent and Fix Subtask generator deterministically |
| Parallel work item execution mode | Can dispatch multiple independent Work Item Orchestrators concurrently when task graph allows | High | Requires careful dependency checking; high value for large EPICs with independent task clusters |

---

## Anti-Features

Things to deliberately NOT build yet. Building these in early phases creates complexity without proportional value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Automatic merges to main | Destroys trust; one bad merge poisons the entire workflow | Enforce manual merge always; document clearly in every PR description |
| Event-driven triggers (webhooks) | Adds infrastructure complexity and race conditions before the core loop is proven | Use CLI loop; graduate to webhooks only after multiple proven cycles |
| Real-time observability dashboards | Premature; Linear comments provide sufficient audit trail for V1 | Use Linear native views; revisit when team size exceeds 1-2 humans |
| ML-based risk prediction | Requires training data that doesn't exist yet | Use heuristic risk scoring first (file churn, dependency count, prior QA failures) |
| Multi-project knowledge sharing | Cross-project intelligence requires significant abstraction overhead | Isolate knowledge store per project; revisit in future scope |
| Simulation / dry-run mode | Useful but complex to implement correctly; creates false safety sense | Use one-action-per-cycle + human review steps as the safety mechanism |
| Self-modifying agent workflows | Agents deciding to add/remove other agents from their own pipeline | All orchestration topology must be human-defined in skill specs |
| Auto-refactoring execution | Suggestions are valuable; auto-execution is dangerous without exhaustive test coverage | Have agents propose refactors as Linear issues, not execute them |
| Autonomous roadmap evolution | Suggesting new EPICs from system gaps crosses human strategy boundary | Keep roadmap human-owned; agents execute, humans plan |
| Agent confidence scoring as a merge gate | Sounds like safety but creates false precision; agents are bad at knowing what they don't know | Use QA + UAT human review as the quality gate; do not delegate merge decisions to confidence scores |

---

## Feature Dependencies

```
Linear Agent (read/write)
    └── Backlog Planning skill (creates hierarchy)
         └── Global Orchestrator (reads readiness)
              └── Work Item Orchestrator (drives lifecycle)
                   ├── Builder Agent (implements)
                   │    └── Git Agent (branches + PRs)
                   │         └── QA Agent (reviews diff)
                   │              └── Fix subtask generator → (loops back to Builder)
                   │                   └── UAT Agent (validates user story)
                   └── Intelligence Agent (enriches context before build)
                        └── Knowledge Store (persists patterns)
                             └── Risk Agent (scores quality, feeds Global Orchestrator)

Agent Contracts (JSON schemas)
    └── All agents (input/output boundary for every handoff)

CLI loop (trigger mode)
    └── Main Orchestrator (entry point, mode selection)
         ├── cascade mode → sequential Work Item Orchestrators
         └── parallel mode → concurrent Work Item Orchestrators
```

Key dependency rules:
- QA cannot be skipped; UAT requires prior QA approval
- Builder cannot start a task that is blocked in Linear
- Git Agent cannot create PRs without knowing the correct target branch (stacked PR hierarchy)
- Knowledge Store must be writable before Intelligence Agent can accumulate value
- Risk Agent adds value only after sufficient QA findings history exists

---

## MVP Recommendation

**Prioritize for Phase 1 (prove the loop):**
1. Linear Agent — read/write operational state
2. Backlog Planning skill — plan.md → EPIC/Story/Task hierarchy in Linear
3. Builder Agent — implement from task spec + acceptance criteria
4. Git Agent — branch + commit + stacked PR targeting
5. QA Agent — diff review → structured findings
6. Fix subtask generation from QA findings
7. Work Item Orchestrator — drives 1 item through implement → PR → QA → fix → done
8. Agent Contracts — typed JSON I/O for all handoffs
9. CLI trigger mode — manual step-through

**Phase 2 additions (expand capability):**
- Global Orchestrator — prioritized ready-task detection
- Main Orchestrator — mode selection, parallel dispatch
- UAT Agent — user story validation gate
- Intelligence Agent — task enrichment with codebase context
- Knowledge Store — pattern persistence

**Phase 3 additions (intelligence layer):**
- Risk Agent — quality scoring + adaptive prioritization
- Knowledge Store semantic search
- Parallel execution mode

**Defer indefinitely:**
- All items in Anti-Features section above
- Real-time dashboards
- Multi-project intelligence
- ML-based risk prediction

---

## Sources

- [How agentic AI will reshape engineering workflows in 2026 | CIO](https://www.cio.com/article/4134741/how-agentic-ai-will-reshape-engineering-workflows-in-2026.html)
- [Agentic workflows for software development | QuantumBlack, McKinsey](https://medium.com/quantumblack/agentic-workflows-for-software-development-dc8e64f4a79d)
- [GitHub adds Stacked PRs to speed complex code reviews | InfoWorld](https://www.infoworld.com/article/4158575/github-adds-stacked-prs-to-speed-complex-code-reviews.html)
- [Devin's 2025 Performance Review | Cognition](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [Anthropic launches a multi-agent code review tool for Claude Code | The New Stack](https://thenewstack.io/anthropic-launches-a-multi-agent-code-review-tool-for-claude-code/)
- [Linear MCP Integration for AI Agents | Composio](https://composio.dev/toolkits/linear)
- [Multi-agent code review: Agents That Prove, Not Guess | Google Cloud / Medium](https://medium.com/google-cloud/agents-that-prove-not-guess-a-multi-agent-code-review-system-e2c0a735e994)
- [Human-In-the-Loop Software Development Agents | arXiv](https://arxiv.org/abs/2411.12924)
- [State of AI Agent Memory 2026 | mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [The 2026 Guide to Agentic Workflow Architectures | StackAI](https://www.stackai.com/blog/the-2026-guide-to-agentic-workflow-architectures)
- [Effective context engineering for AI agents | Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [AI Agent Risk Assessment: Score, Classify, and Enforce | Cycles](https://runcycles.io/blog/ai-agent-risk-assessment-score-classify-enforce-tool-risk)
