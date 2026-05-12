# AGENT CONTRACTS (HSBTech)

## Objective
Define the runtime contracts, state model, execution interfaces, and handoff structures required to connect HSBTech skills into executable agents.

---

## Core Principle

> Skills define behavior. Agents execute behavior. Contracts make them interoperable.

---

## System Layers

### 1. Skills
Reusable operational instructions:
- Backlog Planning
- Implementation
- QA Review
- Git/PR Management
- Linear System of Record
- Work Item Orchestration
- Global Orchestration
- UAT Validation
- Observability / Reporting
- Knowledge Enrichment
- Knowledge Storage
- Quality Scoring & Risk Analysis
- Adaptive Prioritization
- Auto-Improvement Triggers

### 2. Agents
Executable actors that use one or more skills.

### 3. Runtime
The execution environment:
- Claude Code
- Codex
- MCP tools
- GitHub
- Linear
- Local repository

### 4. Linear
System of record:
- state
- memory
- hierarchy
- PR links
- QA results
- workflow status

---

## Global State Model

Every work item must be represented using a consistent state structure.

```json
{
  "work_item_id": "LIN-123",
  "type": "epic | user_story | task | subtask",
  "title": "string",
  "status": "todo | in_progress | blocked | in_review | done",
  "qa_status": "not_required | pending | approved | changes_required",
  "uat_status": "not_required | pending | approved | changes_required",
  "parent_id": "LIN-100",
  "epic_id": "LIN-100",
  "dependencies": ["LIN-101", "LIN-102"],
  "pr_links": [],
  "plan_source": "/docs/plan.md",
  "metadata": {}
}
```

---

## Standard Runtime Envelope

Every agent/skill execution should follow this envelope.

```json
{
  "execution_id": "uuid",
  "requested_by": "global_orchestrator | work_item_orchestrator | human",
  "skill": "string",
  "agent": "string",
  "input": {},
  "output": {},
  "status": "success | failed | blocked",
  "errors": [],
  "next_recommended_action": "string"
}
```

---

## Error Contract

```json
{
  "status": "failed",
  "error_type": "missing_input | invalid_state | tool_failure | validation_failure | blocked_dependency",
  "message": "string",
  "recoverable": true,
  "required_action": "string"
}
```

---

# Skill Contracts

---

## 0. Main Orchestrator Contract

### Input

```json
{
  "execution_mode": "cascade | parallel",
  "ready_work_items": ["LIN-101", "LIN-102", "LIN-103"]
}
```

### Output

```json
{
  "mode": "cascade | parallel",
  "dispatched": [
    {
      "work_item_id": "LIN-101",
      "orchestrator_instance": "work_item_orchestrator_1",
      "claim_status": "claimed | skipped",
      "final_status": "completed | failed | blocked"
    }
  ],
  "cycle_summary": "string"
}
```

### Claiming Rule
Before dispatching in Parallel Mode, the Main Orchestrator must claim each task by setting `status = in_progress` in Linear and verifying the write was successful. If the claim fails, the task is skipped for this cycle.

### Next Step
- Each dispatched `Work Item Orchestrator` runs independently.
- Cycle report is persisted to Linear via the Linear Agent.

---

## 1. Backlog Planning Contract

### Input

```json
{
  "plan_source": "/docs/plan.md",
  "project_context": {
    "name": "string",
    "repository": "string",
    "technical_stack": []
  }
}
```

### Output

```json
{
  "epics": [
    {
      "title": "[EPIC] string",
      "description": "string",
      "acceptance_criteria": [],
      "user_stories": [],
      "tasks": []
    }
  ],
  "traceability": {
    "plan_source": "/docs/plan.md"
  }
}
```

### Next Step
- Linear System of Record persists generated backlog.

---

## 2. Linear System of Record Contract

### Input

```json
{
  "operation": "create | update | read | link | comment | create_subtasks",
  "payload": {}
}
```

### Output

```json
{
  "operation": "string",
  "result": "success | failed",
  "linear_entities": [
    {
      "id": "LIN-123",
      "type": "epic | user_story | task | subtask",
      "url": "string"
    }
  ]
}
```

### Next Step
- Global Orchestrator reads updated Linear state.

---

## 3. Work Item Orchestration Contract

### Input

```json
{
  "work_item": {
    "id": "LIN-123",
    "type": "task | subtask | user_story",
    "status": "todo",
    "dependencies": []
  },
  "epic_context": {},
  "linear_state": {}
}
```

### Output

```json
{
  "work_item_id": "LIN-123",
  "lifecycle_status": "implementation_ready | pr_ready | qa_ready | fix_required | done",
  "next_skill": "implementation | git_pr_management | qa_review | linear_system_of_record",
  "handoff_payload": {}
}
```

### Next Step
- Delegates to the next skill required for the work item lifecycle.

---

## 4. Implementation Contract

### Input

```json
{
  "work_item_id": "LIN-123",
  "issue_description": "string",
  "acceptance_criteria": [],
  "epic_context": {},
  "plan_source": "/docs/plan.md",
  "repository_context": {
    "root_path": "string",
    "technical_stack": []
  },
  "knowledge_context": {}
}
```

### Output

```json
{
  "work_item_id": "LIN-123",
  "implementation_status": "completed | blocked | failed",
  "summary": "string",
  "files_changed": [
    {
      "path": "string",
      "change_summary": "string"
    }
  ],
  "validation": {
    "build": "passed | failed | not_run",
    "tests": "passed | failed | not_run",
    "lint": "passed | failed | not_run",
    "typecheck": "passed | failed | not_run"
  },
  "implementation_notes": {
    "decisions": [],
    "assumptions": [],
    "risks": [],
    "qa_notes": []
  }
}
```

### Next Step
- Git/PR Management creates branch/PR.

---

## 5. Git / PR Management Contract

### Input

```json
{
  "work_item_id": "LIN-123",
  "implementation_output": {},
  "epic_id": "LIN-100",
  "dependencies": [],
  "existing_pr_context": {
    "epic_pr": "string",
    "base_pr": "string"
  }
}
```

### Output

```json
{
  "work_item_id": "LIN-123",
  "branch": "feature/LIN-123-short-slug",
  "commits": [],
  "pull_request": {
    "url": "string",
    "title": "[LIN-123] short description",
    "base": "string",
    "head": "string"
  }
}
```

### Next Step
- Linear System of Record attaches PR link.
- Work item moves to in_review.
- QA Review becomes eligible.

---

## 6. QA Review Contract

### Input

```json
{
  "work_item_id": "LIN-123",
  "linear_issue": {},
  "pull_request": {
    "url": "string",
    "diff": "string"
  },
  "implementation_notes": {},
  "epic_context": {}
}
```

### Output

```json
{
  "work_item_id": "LIN-123",
  "qa_status": "approved | changes_required",
  "summary": "string",
  "findings": [
    {
      "title": "string",
      "severity": "critical | high | medium | low",
      "category": "functional | architecture | code_quality | test | security | regression",
      "status": "blocking | non_blocking",
      "problem": "string",
      "evidence": {
        "file": "string",
        "component": "string",
        "location": "string",
        "related_requirement": "string"
      },
      "expected_behavior": "string",
      "actual_behavior": "string",
      "suggested_fix": "string",
      "suggested_subtask": {
        "title": "[FIX] string",
        "description": "string",
        "acceptance_criteria": [],
        "validation_steps": []
      },
      "pr_targeting_guidance": {
        "target_pr": "string"
      }
    }
  ]
}
```

### Next Step
- If approved: Linear marks work item done.
- If changes_required: Linear creates fix subtasks.

---

## 7. UAT Validation Contract

### Input

```json
{
  "user_story_id": "LIN-200",
  "acceptance_criteria": [],
  "related_prs": [],
  "qa_status": "approved",
  "epic_context": {}
}
```

### Output

```json
{
  "user_story_id": "LIN-200",
  "uat_status": "approved | changes_required",
  "scenarios": [
    {
      "description": "string",
      "expected_behavior": "string",
      "actual_behavior": "string",
      "result": "pass | fail"
    }
  ],
  "findings": []
}
```

### Next Step
- Linear System of Record persists UAT status and findings.

---

## 8. Observability / Reporting Contract

### Input

```json
{
  "linear_state": {},
  "time_window": "string",
  "scope": "project | epic | work_item"
}
```

### Output

```json
{
  "summary": {},
  "epic_reports": [],
  "bottlenecks": [],
  "next_actions": [],
  "risks": []
}
```

### Next Step
- Human or Global Orchestrator consumes the report.

---

## 9. Knowledge / Context Enrichment Contract

### Input

```json
{
  "work_item_id": "LIN-123",
  "linear_context": {},
  "codebase_context": {},
  "qa_history": [],
  "knowledge_store": {}
}
```

### Output

```json
{
  "work_item_id": "LIN-123",
  "enrichment_report": {
    "suggested_approach": "string",
    "impact_analysis": {
      "files": [],
      "modules": []
    },
    "risks": [],
    "edge_cases": [],
    "recommendations": []
  }
}
```

### Next Step
- Implementation and QA may use enrichment as input.
- No direct state mutation.

---

## 10. Knowledge Storage Contract

### Input

```json
{
  "knowledge_entry": {
    "title": "string",
    "type": "architecture | qa | implementation | backlog | risk | pattern | anti_pattern",
    "context": "string",
    "evidence": {
      "linear_issue": "string",
      "pr": "string",
      "files": [],
      "qa_finding": "string"
    },
    "insight": "string",
    "recommendation": "string",
    "applicability": "string",
    "date": "YYYY-MM-DD"
  }
}
```

### Output

```json
{
  "stored": true,
  "location": "knowledge/category/file.md",
  "entry_id": "string"
}
```

### Next Step
- Knowledge Enrichment retrieves it in future cycles.

---

## 11. Quality Scoring & Risk Analysis Contract

### Input

```json
{
  "linear_state": {},
  "qa_findings": [],
  "pr_history": [],
  "uat_results": [],
  "knowledge_store": {}
}
```

### Output

```json
{
  "scores": [
    {
      "work_item_id": "LIN-123",
      "quality_score": 85,
      "risk_score": "low | medium | high",
      "rework_index": 1,
      "explanation": "string"
    }
  ],
  "epic_scores": []
}
```

### Next Step
- Adaptive Prioritization consumes scores.

---

## 12. Adaptive Prioritization Contract

### Input

```json
{
  "linear_state": {},
  "quality_scores": [],
  "risk_scores": [],
  "dependency_graph": {},
  "blockers": []
}
```

### Output

```json
{
  "priority_queue": [
    {
      "work_item_id": "LIN-123",
      "priority_score": 92,
      "reason": "High risk and blocks 3 tasks"
    }
  ]
}
```

### Next Step
- Global Orchestrator uses queue to decide next work item.

---

## 13. Auto-Improvement Triggers Contract

### Input

```json
{
  "qa_findings_history": [],
  "quality_scores": [],
  "observability_reports": [],
  "knowledge_store": {},
  "linear_state": {}
}
```

### Output

```json
{
  "triggers": [
    {
      "type": "refactoring | testing | architecture | performance | reliability",
      "title": "[IMPROVEMENT] string",
      "reason": "string",
      "evidence": [],
      "suggested_work_item": {
        "title": "string",
        "description": "string",
        "acceptance_criteria": []
      }
    }
  ]
}
```

### Next Step
- Linear System of Record may persist approved improvement tasks.

---

# Agent Mapping

| Agent | Primary Skills |
|---|---|
| Main Orchestrator Agent | Main Orchestration (execution mode, dispatch, claiming) |
| Global Orchestrator Agent | Global Orchestration, Adaptive Prioritization, Observability |
| Work Item Orchestrator Agent | Work Item Orchestration |
| Backlog Agent | Backlog Planning |
| Linear Agent | Linear System of Record |
| Builder Agent | Implementation |
| Git Agent | Git/PR Management |
| QA Agent | QA Review |
| UAT Agent | UAT Validation |
| Intelligence Agent | Knowledge Enrichment, Knowledge Storage |
| Risk Agent | Quality Scoring, Risk Analysis, Auto-Improvement Triggers |

---

# End-to-End Flow

## Initial Backlog Creation

1. Human provides plan file.
2. Global Orchestrator detects no backlog.
3. Backlog Agent generates EPICs/User Stories/Tasks.
4. Linear Agent persists backlog.
5. Global Orchestrator reads updated state.

---

## Work Item Execution

1. Global Orchestrator asks Adaptive Prioritization for next item.
2. Work Item Orchestrator receives selected item.
3. Intelligence Agent enriches context.
4. Builder Agent implements.
5. Git Agent creates PR.
6. Linear Agent links PR and updates status.
7. QA Agent reviews.
8. Linear Agent records QA result.
9. If QA fails, Linear Agent creates fix subtasks.
10. If QA passes, work item is marked done.

---

## UAT Flow

1. User Story implementation is QA approved.
2. UAT Agent validates behavior.
3. Linear Agent persists UAT result.
4. If UAT fails, fix subtasks are created.
5. If UAT passes, User Story is complete.

---

## Improvement Flow

1. Risk Agent detects recurring issue.
2. Auto-Improvement Trigger produces suggested work item.
3. Linear Agent persists it only when allowed.
4. Adaptive Prioritization decides when it matters.

---

# Runtime Rules

## 1. Linear First
Every orchestration cycle starts by reading Linear.

## 2. No Hidden State
Any durable state must be persisted in Linear or Knowledge Storage.

## 3. No Direct Cross-Skill Mutation
Skills return structured output. State mutation happens through the Linear System of Record or Knowledge Storage skill.

## 4. No Automatic Merge
No agent merges into main automatically.

## 5. Small Work Items
Implementation should remain small and scoped.

## 6. QA Never Skipped
Every PR must pass QA before completion.

---

# Golden Rule

> Contracts are the boundary between intelligence and chaos.
