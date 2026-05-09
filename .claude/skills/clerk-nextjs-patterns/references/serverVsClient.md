# Server vs Client Auth (CRITICAL)

## CRITICAL: Always `await auth()`

```tsx
// WRONG — returns a Promise, not the auth object
const { userId } = auth(); // undefined!

// CORRECT
const { userId } = await auth();
```

## Import Rules

```tsx
// Server Components, Server Actions, Route Handlers
import { auth, currentUser } from "@clerk/nextjs/server";

// Client Components (must have "use client" directive)
"use client";
import { useAuth, useUser } from "@clerk/nextjs";
```

Never cross these boundaries. Server imports in Client Components or vice versa will break.

## Server Component

```tsx
import { auth, currentUser } from "@clerk/nextjs/server";

export default async function DashboardPage() {
  const { isAuthenticated } = await auth();
  if (!isAuthenticated) return <div>Please sign in</div>;

  const user = await currentUser();
  return <h1>Welcome, {user?.firstName}!</h1>;
}
```

> **Core 2**: `isAuthenticated` unavailable. Use `if (!userId)` instead.

## Client Component (with Orval Hooks)

In the Ezra monorepo, client components that need API data should use Orval-generated hooks. Auth tokens are injected automatically via `ClerkTokenSync` + `baseFetch`.

```tsx
"use client";
import { useGetDeals } from "@ezra/api-client/api";

export function DealList() {
  // Token is automatically attached — no manual getToken() needed
  const { data, error, isLoading } = useGetDeals();

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <ul>
      {data?.data.map((deal) => (
        <li key={deal.id}>{deal.company_name}</li>
      ))}
    </ul>
  );
}
```

## Client Component (Auth State Only)

When you need auth state for UI logic (not API calls):

```tsx
"use client";
import { useUser, useAuth } from "@clerk/nextjs";

export function UserMenu() {
  const { isLoaded, isSignedIn, user } = useUser();
  const { signOut } = useAuth();

  if (!isLoaded) return <div>Loading...</div>;
  if (!isSignedIn) return null;

  return (
    <div>
      <p>{user.firstName}</p>
      <button onClick={() => signOut()}>Sign out</button>
    </div>
  );
}
```

## Hybrid Pattern (Server fetch + Client interaction)

```tsx
// Server Component: fetch initial data
import { auth } from "@clerk/nextjs/server";
import { DealForm } from "@/components/deals/dealForm";

export default async function DealPage() {
  const { userId } = await auth();
  if (!userId) return <div>Please sign in</div>;
  // Pass minimal props to client component
  return <DealForm userId={userId} />;
}

// Client Component: interactive UI with Orval hooks
"use client";
import { useGetDeals } from "@ezra/api-client/api";

export function DealForm({ userId }: { userId: string }) {
  const { data } = useGetDeals(); // auto-authenticated
  return <form>...</form>;
}
```

## Conditional Rendering with `<Show>`

For client-side conditional rendering based on auth state:

```tsx
import { Show } from "@clerk/nextjs";

<Show when="signed-in" fallback={<p>Please sign in</p>}>
  <Dashboard />
</Show>
```

> **Core 2**: Use `<SignedIn>` and `<SignedOut>` components instead of `<Show>`.

## Docs

[Clerk auth() reference](https://clerk.com/docs/reference/nextjs/auth)
