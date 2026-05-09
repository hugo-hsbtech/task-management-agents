---
name: domain-organization
description: Advisory skill for evaluating and organizing backend domain packages according to DDD best practices, capability-oriented design, and Ezra conventions. Use when creating new domains, reviewing existing domain boundaries, refactoring packages, or deciding where new business logic should live.
---

# Domain Organization

Advisory skill for evaluating backend domain package boundaries. Analyzes existing or proposed domains against capability-oriented design principles and recommends improvements.

## When to Use

- creating a new domain package under `backend/packages/domains/`
- deciding where new business logic should live
- reviewing whether an existing domain has grown beyond its boundary
- refactoring or splitting a domain package
- questioning whether something belongs in `domains/`, `apps/`, or elsewhere

## First Reads

Before advising on domain organization, read:

- `backend/packages/CLAUDE.md` — package category rules (apps vs domains vs clients)
- `backend/CLAUDE.md` — backend conventions and stack overview
- `backend/packages/domains/core/CLAUDE.md` — what belongs in the shared foundation
- `backend/packages/domains/core/src/ezra_core/` — current core contents (database, settings, S3, schemas)
- The `pyproject.toml` of any domain under discussion — check its dependencies on other domains
- The `src/` tree of any domain under discussion — understand what it actually contains

## Core Principle: Domains Are Capabilities, Not Entities or Technologies

A well-designed domain package answers the question **"what can the system do?"** — not "what does the system know about?" or "what technology does it use?"

### Good Domain Names (Capability-Oriented)

| Domain | Capability |
|--------|-----------|
| `authentication` | Verify identity, manage sessions, sync users |
| `storage` | Store and retrieve files, generate presigned URLs |
| `workflows` | Define, execute, and observe durable workflows |
| `core` | Shared infrastructure: database, settings, base schemas |
| `ai` | LLM client management, prompt fetching, observability, agent instrumentation |
| `notifications` | Send emails, push notifications, in-app alerts |
| `search` | Index, query, and rank across entities |
| `billing` | Manage subscriptions, usage tracking, invoicing |
| `permissions` | Authorization rules, role management, access control |

### Bad Domain Names (and Why)

| Domain | Problem | Category |
|--------|---------|----------|
| `deals` | Business entity — becomes a gravity well that pulls in unrelated concerns (triage, agents, matching, documents) | Entity-oriented |
| `llm` | Technology wrapper — names the tool, not the capability it enables | Technology-oriented |
| `mcp` | Protocol wrapper — describes wire format, not what it does for the system | Technology-oriented |
| `users` | Entity — conflates identity, profile, preferences, and permissions | Entity-oriented |
| `documents` | Entity — conflates storage, parsing, analysis, and search | Entity-oriented |
| `langfuse` | Vendor name — couples the domain to a specific product | Vendor-oriented |

## The Three-Part Test

When evaluating whether a proposed domain is well-bounded, apply these three tests:

### 1. Capability Test — "Can I describe this domain as a verb phrase?"

- "authenticate users" — yes, capability
- "store files" — yes, capability
- "deals" — no, that's a noun. What does the system *do* with deals? Triage them, analyze them, score them — those are separate capabilities.

### 2. Stability Test — "Will this domain's boundary hold as the product grows?"

- `authentication` — yes, auth is auth regardless of what features ship
- `deals` — no, "deals" will absorb triage, scoring, document analysis, compliance checks, notifications, etc. as the product evolves
- `storage` — yes, file storage is a stable capability

### 3. Reusability Test — "Could multiple apps or features use this domain?"

- `workflows` — yes, any feature can define workflows
- `ai` — yes, any feature can instrument agents and fetch prompts
- `deals` — no, only deal-related features use it. This signals it may belong in an app, not a domain.

## Where Things Belong

### `packages/domains/` — Cross-Cutting Capabilities

Shared capabilities used by multiple apps. No HTTP layer. No business entities as top-level concepts.

Examples: `core`, `authentication`, `storage`, `workflows`, `ai`, `search`, `notifications`

### `packages/apps/` — Deployable Services with Business Logic

Business entities and their specific logic live here. An app owns its routes, models, and entity-specific services. It composes capabilities from domain packages.

Example: A deals app (`packages/apps/deals/`) would own:
- Deal models and schemas
- Deal CRUD service
- Deal-specific routes
- It *uses* `storage` for file handling, `ai` for agent instrumentation, `workflows` for triage pipelines

### `packages/domains/core/` — Infrastructure Concerns

Protocol adapters, base classes, and shared infrastructure that don't merit their own domain.

Examples of what belongs in core:
- Database engine/session factory
- Base settings classes
- MCP server factory and auth (protocol infrastructure, not a domain)
- Shared error schemas

## Handling Technology Wrappers

When you encounter a domain that wraps a technology (LLM, MCP, message queue, etc.), ask: **"What capability does this enable for the rest of the system?"**

| Technology | Capability | Recommended Domain |
|-----------|-----------|-------------------|
| PydanticAI + Langfuse | AI agent instrumentation, prompt management, observability | `ai` |
| FastMCP + Starlette | Expose tools over MCP protocol | `core` (infrastructure) |
| Temporal | Durable workflow execution | `workflows` |
| S3/aioboto3 | File storage and retrieval | `storage` |
| Clerk | Identity verification and user sync | `authentication` |

The domain name should describe the capability, not the technology. If you swap Langfuse for another observability tool, the `ai` domain's interface should remain stable.

## Handling Business Entities

When someone proposes a domain named after a business entity (deals, users, invoices, projects), decompose it:

1. **List the verbs** — what does the system do with this entity?
2. **Group by capability** — which verbs cluster into coherent capabilities?
3. **Map to existing domains** — do any clusters map to existing capabilities?
4. **Remainder goes in the app** — entity CRUD and entity-specific logic stays in the app

### Example: Decomposing "Deals"

Verbs: create, update, delete, triage, analyze documents, score completeness, match criteria, generate one-pagers, store files, notify stakeholders

| Verb Cluster | Capability Domain | Notes |
|-------------|-------------------|-------|
| Triage, score, analyze | `ai` (agent instrumentation) + app-level triage service | Agents use `ai` for instrumentation; triage orchestration is app logic |
| Store/retrieve files | `storage` | Already exists |
| Match criteria | App logic | Deal-specific business rules |
| Create, update, delete | App logic | CRUD for the deal entity |
| Notify stakeholders | `notifications` | Cross-cutting capability |

Result: the `deals` domain dissolves. Deal CRUD and triage orchestration live in a deals app. The agents use `ai` for instrumentation. Files use `storage`. No `deals` domain needed.

### Real Example: Current `ezra_deals` Domain

The `deals` domain currently contains:

```
ezra_deals/
  service.py          # Deal CRUD — app logic
  models.py           # Deal SQLAlchemy models — app logic
  schemas.py          # Deal Pydantic schemas — app logic
  email.py            # Deal notification emails — notifications capability
  s3.py               # Deal file helpers — storage capability
  settings.py         # Deal-specific settings — app config
  triage/
    pipeline.py       # Triage orchestration — app logic
    state.py          # Deal state machine — app logic
    config.py         # Triage config — app config
    agents/           # 7 PydanticAI agents — use ai capability
    documents/        # Classifier, uploader — use storage capability
    intake/           # Router — app logic
    screening/        # Gate assessor — app logic
    utils/llm.py      # Custom LLM client (duplicates ezra_llm!) — should use ai
    utils/logging.py  # Custom logger — app utility
```

Target state after decomposition:

```
packages/apps/api/src/ezra_api/
  routers/deals.py           # Deal REST routes (already exists)

packages/apps/worker/         # or a deals-specific app
  deal_models.py              # Deal, DealDocument SQLAlchemy models
  deal_service.py             # Deal CRUD service
  deal_schemas.py             # Deal Pydantic schemas
  triage/                     # Triage orchestration, state machine, screening
    pipeline.py
    state.py
    agents/                   # Agent definitions (use ezra_ai for instrumentation)
    intake/

packages/domains/ai/          # Renamed from llm, absorbs triage/utils/llm.py usage
packages/domains/storage/     # Already handles file ops (deals/s3.py migrates here)
packages/domains/notifications/ # New — absorbs deals/email.py pattern
```

## Advisory Checklist

When asked to evaluate domains, produce a report covering:

1. **Current domains inventory** — list each domain with a one-line description of what it contains
2. **Three-part test results** — run each domain through the capability, stability, and reusability tests
3. **Recommendations** — for each domain that fails any test:
   - What's wrong (entity-oriented, technology-oriented, too broad, too narrow)
   - Where its contents should move
   - Migration path (what depends on it, what breaks)
4. **Proposed domain map** — the target state with clean capability boundaries

## Anti-Patterns

- **The God Domain**: a domain that grows to contain everything related to the core business entity. Fix: decompose into capabilities.
- **The Vendor Domain**: a domain named after a specific tool or vendor. Fix: name after the capability.
- **The Protocol Domain**: a domain that wraps a protocol (MCP, gRPC, GraphQL). Fix: fold infrastructure into core; business logic into relevant capability domains.
- **The Mirror Domain**: a domain that exactly mirrors an app's routes. Fix: if it's only used by one app, it belongs in the app.
- **The Junk Drawer**: a domain called `utils`, `helpers`, or `common`. Fix: distribute to relevant domains or core.
- **The Island Domain**: a domain that re-implements capabilities that exist in other domains rather than depending on them. Symptom: the domain has its own `utils/llm.py` when `ezra_llm` exists, or its own S3 helpers when `ezra_storage` exists. This happens when entity-oriented domains become self-contained islands — developers add what they need locally because the domain feels like a complete unit. Fix: delete the local copies and depend on the capability domains.

## Done Checklist

After advising on domain organization:

- Each recommended domain passes the three-part test (capability, stability, reusability)
- No domain is named after a business entity, technology, or vendor
- Business entity logic has a clear home in an app package
- Infrastructure concerns either live in `core` or have a capability-oriented domain name
- Migration path is practical — no "rewrite everything" recommendations
- Dependencies between domains are acyclic and follow the rule: domains depend on `core`, apps depend on domains

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Domain has its own `utils/llm.py`, `s3.py`, or similar | Island Domain — re-implements existing capability | Delete local copy, depend on the capability domain (`ezra_llm`, `ezra_storage`) |
| Domain only used by one app | Mirror Domain — domain mirrors app structure | Move contents into the app package |
| New feature doesn't "fit" any existing domain | Missing capability domain, or feature is app-specific | Run the three-part test: if it's reusable, create a new capability domain; if not, it belongs in an app |
| Domain has 10+ modules spanning unrelated concerns | God Domain — entity name attracted everything | Decompose: list verbs, group by capability, distribute |
| Two domains have circular imports | Boundary violation — domains depend on each other | Extract shared types to `core`, or merge if they're really one capability |
| Domain named after a vendor and vendor is being swapped | Vendor Domain — name couples to product | Rename to capability, keep interface stable, swap implementation |

## See Also

- `fastapi-patterns` — how apps compose domain packages via dependency injection
- `fastmcp-server` — MCP server scaffolding (currently `ezra_mcp`, recommended to move to `core`)
- `ezra-llm-integration` — AI/LLM instrumentation patterns (currently `ezra_llm`, recommended rename to `ai`)
- `ezra-scaffold-backend-tests` — scaffolding tests when creating new domain or app packages