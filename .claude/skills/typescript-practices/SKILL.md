---
name: typescript-practices
description: [NOT APPLICABLE — Ezra-specific reference; do not invoke in this project] TypeScript practices for TS/TSX, Node.js, and React work. Use when implementing, refactoring, or reviewing TypeScript; designing shared types or public APIs; validating external data; tightening strictness; or fixing type errors. Prioritizes boundary-first design, explicit contracts, discriminated unions, exhaustive handling, runtime validation, and avoiding unsafe `any` or suppressions by default.
author: Carlos Melgoza
---

# TypeScript Practices

Use this skill for TypeScript work where correctness, maintainability, and API design matter. This skill complements `coding-standards`; it does not replace local style or framework-specific patterns.

## When to Activate

- Writing or refactoring shared TypeScript modules, services, hooks, or components
- Changing public contracts between layers, packages, routes, or background jobs
- Fixing bugs caused by incorrect assumptions about data shape or state transitions
- Adding or modifying integrations at HTTP, database, env var, queue, or tool/LLM boundaries
- Reviewing TypeScript code for long-term maintainability instead of just "making tsc pass"
- Tightening strictness or paying down unsafe casts, suppressions, and implicit contracts

## Operating Mode

1. Read local constraints first.
   Inspect `package.json`, `tsconfig*.json`, lint config, test config, and nearby patterns before changing code.
2. Fix the model, not the symptom.
   Prefer changing the type boundary or runtime contract over scattering assertions downstream.
3. Keep the diff narrow.
   Do not rewrite unrelated code. Do not weaken compiler or linter settings to get green.

## Non-Negotiable Bar

### Strictness Is a Feature

- Treat strict typing as a product requirement, not optional polish.
- Do not relax `strict`-family settings or widen config exclusions to silence errors in touched code.
- If existing config is weak, improve the changed area locally rather than broadening escape hatches.
- When shaping or reviewing `tsconfig`, strongly prefer `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, and `useUnknownInCatchVariables` in addition to `strict`.

### Avoid Unsound Escape Hatches

- Do not introduce `any`, `as any`, `@ts-ignore`, or broad non-null assertions as a first resort.
- Use `unknown` for untrusted input and narrow it with guards or schema parsing.
- If a suppression is unavoidable, keep it local, make the invariant explicit, and prefer `@ts-expect-error` over `@ts-ignore`.

### Parse at the Edge

- Validate external input at boundaries: HTTP, DB rows, env vars, queues, local storage, tool output, and LLM output.
- Once data is parsed, keep core logic on trusted domain types.
- If the repo already uses a runtime schema library such as Zod, Valibot, or io-ts, derive the TypeScript type from the schema instead of duplicating it.

### Model State Explicitly

- Prefer discriminated unions over boolean bags and loosely optional objects.
- Make invalid states unrepresentable.
- Use exhaustive `switch` statements with a `never` check when handling closed state sets.

### Keep Public Contracts Boring

- Annotate exported functions, hooks, utilities, and shared stores at module boundaries.
- Prefer small domain types over giant "catch-all" interfaces.
- Do not leak raw transport DTOs across the app when an adapter can normalize them once.
- If a type is painful to express, simplify the runtime API first.

### Inference Inside, Clarity Outside

- Let local variables infer when the initializer is obvious.
- Add annotations where they clarify contracts, stabilize inference, or improve editor feedback.
- Prefer `satisfies` for config and literal objects when you want validation without widening.
- Use `as const` intentionally for stable literals and discriminants.

### Prefer Built-In Type Tools Before Clever Metaprogramming

- Reach for built-in utility types such as `Pick`, `Omit`, `Record`, `NonNullable`, `Parameters`, and `ReturnType` before inventing custom helpers.
- Use template literal types when a closed string convention matters, such as route, event, or key formats.
- Use mapped and conditional types to remove repetition or model input/output relationships, not to show off type-level cleverness.
- If an advanced type makes the runtime API harder to understand, simplify the API.

### Derive All API-Shaped Types from Generated Models

- Any type that represents API data — component props, hook parameters, hook return types, function arguments, utility inputs/outputs — MUST derive from Orval-generated types in `@ezra/api-client/model/<service>` using `Pick`, `Omit`, `Partial`, or intersection (`&`).
- NEVER redeclare fields manually that already exist in generated types.
- Examples:
  - Component props: `type DealCardProps = Pick<DealListResponse, "id" | "company_name" | "triage_status"> & { className?: string }`
  - Hook return: `type UseDealResult = { deal: DealResponse | undefined; isLoading: boolean }`
  - Function param: `function formatDealDate(deal: Pick<DealResponse, "created_at">): string`
  - Partial updates: `type DealFormData = Pick<DealCreate, "company_name" | "description">`
- For presentation-only fields not in the API (e.g., `className`, `onAction`, `isExpanded`), add them via intersection.
- This ensures all types stay in sync with backend schema changes and avoids type drift.

### Typed Async and Collection Flows

- Prefer `Promise.all` for independent work.
- Narrow collections before consuming them; do not carry `undefined` or nullable values further than necessary.
- Normalize errors at boundaries. Avoid catch-all branches that silently return `null` or partial data without a clear contract.

### Tests Must Defend the Contract

- Every bug fix gets a regression test.
- Every new branch or state variant gets coverage.
- Add type-level tests only if the repo already uses `tsd`, `expectTypeOf`, or similar tooling.
- Run the project's typecheck, relevant tests, and lint before considering the task complete.

## Preferred Patterns

### Boundary Parsing

```typescript
const UserResponse = z.object({
  id: z.string(),
  email: z.string().email(),
  role: z.enum(['admin', 'member']),
})

type UserResponse = z.infer<typeof UserResponse>

export async function fetchUser(userId: string): Promise<UserResponse> {
  const response = await fetch(`/api/users/${userId}`)
  const json: unknown = await response.json()
  return UserResponse.parse(json)
}
```

### Discriminated Unions

```tsx
type LoadState<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'loaded'; data: T }
  | { kind: 'error'; message: string }

function renderState(state: LoadState<User>) {
  switch (state.kind) {
    case 'idle':
      return null
    case 'loading':
      return <Spinner />
    case 'loaded':
      return <Profile user={state.data} />
    case 'error':
      return <ErrorMessage message={state.message} />
    default: {
      const exhaustive: never = state
      return exhaustive
    }
  }
}
```

### `satisfies` for Stable Literals

```typescript
const FEATURE_FLAGS = {
  billingV2: 'billing-v2',
  searchRanking: 'search-ranking',
} as const satisfies Record<string, string>
```

### Utility and Template Literal Types

```typescript
type PublicUser = Omit<User, 'passwordHash'>
type UserMap = Record<User['id'], PublicUser>
type ApiRoute = `/api/${string}`
```

## Review Checklist

Before finishing, verify:

- Touched compiler settings are moving toward stricter, more accurate checks rather than broader escape hatches
- External or persisted data is validated at the boundary
- No new unsafe casts or suppressions were added without a documented invariant
- Exported APIs are intentionally typed
- State transitions are explicit and exhaustive
- The change includes the right regression or branch tests
- `tsc`, lint, and relevant tests were run using the repo's existing commands

## Anti-Patterns to Remove

- `Promise<any>` or `Record<string, any>` in application code
- Reusing transport types as domain types when they require normalization
- Optional-property bags that permit impossible states
- Broad `catch` blocks that erase useful error information
- Non-null assertions after lookups or DOM queries without a clear invariant
- Fixing type errors by weakening `tsconfig`, lint rules, or generated types

**Remember**: A suppression or `any` that silences an error today becomes the bug you can't find next year. Fix the model, not the symptom — change the type boundary or runtime contract instead of scattering assertions downstream.

## See Also

- `coding-standards` — universal code hygiene
- `tdd-workflow` — building or fixing behavior test-first
- `verification-loop` — final checks before handoff or PR
- `frontend-patterns` — React-specific composition and state patterns
- `security-review` — auth, secrets, user input, and privilege boundaries
