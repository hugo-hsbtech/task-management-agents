---
name: feature-flags-posthog
description: PostHog feature flag API patterns — create, target, discover stale flags, archive, delete, and cross-project lifecycle management. Use with feature-flags-ts-posthog or feature-flags-fastapi-posthog for SDK evaluation code.
origin: Ezra
author: Carlos Melgoza
---

# Feature Flags — PostHog API Patterns

PostHog-specific patterns for managing the full flag lifecycle via API and UI. Covers the gaps between PostHog and enterprise flag platforms.

## When to Activate

- Creating or updating a flag via the PostHog API
- Auditing flags for staleness across projects
- Planning flag cleanup or archiving
- Setting up targeting rules or rollout percentages
- Diagnosing a flag evaluation issue

## Projects as Environments

PostHog uses **separate projects** for environments — there is no per-environment targeting within a single project. A flag called `new-checkout-flow` in your `production` project is a different object from the same flag in your `staging` project.

```
PostHog org
├── project: production   (API key: phc_prod_xxx)
├── project: staging      (API key: phc_stg_xxx)
└── project: development  (API key: phc_dev_xxx)
```

Consequence: promoting a flag from staging to prod means **recreating it via API** in the production project, or manually mirroring targeting rules in the UI. There is no built-in "copy flag config" operation.

## Authentication

All API calls require a Personal API Key (not the project API key):

```bash
Authorization: Bearer phx_your_personal_api_key
```

Base URL: `https://app.posthog.com` (or your self-hosted URL)

## Flag Create

```bash
POST /api/projects/{project_id}/feature_flags/

{
  "key": "new-checkout-flow",
  "name": "New Checkout Flow",
  "active": false,
  "filters": {
    "groups": [
      {
        "properties": [],
        "rollout_percentage": 0
      }
    ]
  }
}
```

**Always create with `active: false` and `rollout_percentage: 0`.** Enable deliberately after verifying both code paths work.

### Multivariate flag

```bash
{
  "key": "checkout-variant",
  "name": "Checkout A/B Test",
  "active": false,
  "filters": {
    "multivariate": {
      "variants": [
        { "key": "control", "name": "Control", "rollout_percentage": 50 },
        { "key": "test",    "name": "Test",    "rollout_percentage": 50 }
      ]
    },
    "groups": [{ "properties": [], "rollout_percentage": 100 }]
  }
}
```

### Remote config flag

```bash
{
  "key": "checkout-config",
  "filters": {
    "payloads": { "true": "{\"timeout\": 5000, \"retries\": 3}" },
    "groups": [{ "properties": [], "rollout_percentage": 100 }]
  }
}
```

## Flag Targeting Rules

```bash
PATCH /api/projects/{project_id}/feature_flags/{flag_id}/

{
  "filters": {
    "groups": [
      {
        "properties": [
          {
            "key": "email",
            "type": "person",
            "value": ["@yourcompany.com"],
            "operator": "icontains"
          }
        ],
        "rollout_percentage": 100
      },
      {
        "properties": [],
        "rollout_percentage": 10
      }
    ]
  }
}
```

Groups are evaluated top-to-bottom. First matching group wins. Order matters.

### Common targeting operators

| Operator | Meaning |
|---|---|
| `exact` | Exact match (string or array) |
| `is_not` | Not equal |
| `icontains` | Case-insensitive contains |
| `regex` | Regex match |
| `gt` / `lt` / `gte` / `lte` | Numeric comparison |
| `is_set` / `is_not_set` | Property exists check |
| `is_date_before` / `is_date_after` | Date comparison |
| `version_lt` / `version_gt` | Semantic version |

### Group (B2B org) targeting

```bash
{
  "filters": {
    "aggregation_group_type_index": 0,
    "groups": [
      {
        "properties": [
          {
            "key": "plan",
            "type": "group",
            "value": ["enterprise"],
            "operator": "exact",
            "group_type_index": 0
          }
        ],
        "rollout_percentage": 100
      }
    ]
  }
}
```

## Flag Toggle

```bash
PATCH /api/projects/{project_id}/feature_flags/{flag_id}/

{ "active": true }
```

## Flag Discovery

```bash
GET /api/projects/{project_id}/feature_flags/?active=true&search=checkout
```

Query params: `active` (bool), `search` (string), `type` (`experiment`, `release`).

There is no built-in "stale flags" filter. Use the staleness detection pattern below.

## Staleness Detection (Manual)

PostHog does not auto-classify flags as stale. Use this pattern to find candidates:

### Get All Flags
```bash
GET /api/projects/{project_id}/feature_flags/?limit=100
```

### Check Flag Status
```bash
GET /api/projects/{project_id}/feature_flags/{flag_id}/status/
```

Response includes:
```json
{
  "active": true,
  "reason": {
    "code": "inactive",            // "active" | "inactive" | "disabled"
    "detail": "No evaluations in last 30 days"
  }
}
```

### Categorize Results

| Condition | Category |
|---|---|
| `active: false` | Disabled — confirm dead code removed |
| `status.code == "inactive"` + flag is old | Stale candidate |
| `active: true` + 100% rollout + no recent changes | Launched — schedule cleanup |
| `active: true` + complex targeting | Active — leave alone |

**Note:** This is a per-flag API call. For a full audit, loop all flags and check status individually. There is no bulk health endpoint.

## Cross-Project Flag Promotion

To promote a flag from staging to production:

1. Read the flag definition from staging:
   ```bash
   GET /api/projects/{staging_project_id}/feature_flags/{flag_id}/
   ```

2. Create it in production with `active: false`:
   ```bash
   POST /api/projects/{prod_project_id}/feature_flags/
   # Use same key, name, filters — but start inactive
   ```

3. Verify both code paths work in production.

4. Enable in production:
   ```bash
   PATCH /api/projects/{prod_project_id}/feature_flags/{flag_id}/
   { "active": true }
   ```

Always keep flag keys identical across projects. The key is the contract between your code and PostHog.

## Manual Removal Readiness Checklist

PostHog has no `check-removal-readiness` equivalent. Run this manually:

```
[ ] Flag status endpoint returns "inactive" or flag is at 100% rollout
[ ] No evaluations in last 7 days (check Insights → Feature Flags usage chart)
[ ] Flag serves the same variation in ALL projects (dev/staging/prod)
[ ] No other flag lists this flag in its dependencies
[ ] Codebase grep: zero references to the flag key string
[ ] Both branches exist in code and are tested
[ ] Team notified if flag key is referenced in other repos
```

Only after all boxes are checked: archive, then remove code, then delete.

## Archive a Flag

Archiving hides the flag from lists but preserves history. Prefer archive over delete.

```bash
PATCH /api/projects/{project_id}/feature_flags/{flag_id}/

{ "deleted": false, "active": false }
```

To mark as archived in the UI sense, set `active: false`. PostHog's true archive state is set via the UI "Archive" button or via the `filters` property with a specific deleted marker.

## Delete a Flag

```bash
DELETE /api/projects/{project_id}/feature_flags/{flag_id}/
```

Wait at least 30 days after removing flag code before deleting. This ensures any cached evaluations expire and any delayed deployments complete.

## Auto-Rollback Setup

PostHog supports automatic flag rollback based on Sentry error rates or custom HogQL metrics.

Configure in the PostHog UI: Feature Flags → {flag} → Add rollback condition.

Rollback triggers:
- Sentry error count exceeds threshold
- Custom HogQL metric (e.g., `count of error events where flag = 'on' > X`)

When triggered: flag is automatically set to `active: false` and an activity log entry is created with `trigger: automatic_rollback`.

## Flag Dependencies

```bash
POST /api/projects/{project_id}/feature_flags/

{
  "key": "new-checkout-v2",
  "filters": {
    "groups": [
      {
        "properties": [
          {
            "key": "new-checkout-flow",
            "type": "flag",
            "value": "true",
            "operator": "exact"
          }
        ],
        "rollout_percentage": 100
      }
    ]
  }
}
```

PostHog validates at creation time that the dependency exists and blocks circular references.

## Activity Log

```bash
GET /api/projects/{project_id}/activity_log/?scope=FeatureFlag&item_id={flag_id}
```

Every targeting change, toggle, creation, and deletion is recorded. Use this to audit who changed what before a cleanup.

**Remember**: PostHog has no cross-environment flag model. dev, staging, and prod are separate projects — always verify a flag's targeting config in each project independently before promoting to production.

## See Also

- `feature-flags` — universal patterns: naming, types, lifecycle, hygiene rules
- `feature-flags-ts-posthog` — TypeScript + PostHog SDK evaluation
- `feature-flags-fastapi-posthog` — FastAPI + PostHog SDK evaluation
