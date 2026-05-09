# Caching with Auth (MEDIUM)

**CRITICAL**: Cache keys MUST include `userId` or `orgId` to prevent data leaking between users.

## User-Scoped Cache

> **Token freshness caveat**: `unstable_cache` only executes the function body on cache miss. If you call `getToken()` inside the cached function, the token is captured at cache-write time and won't refresh until the cache expires. Keep `revalidate` shorter than the Clerk token lifetime (default ~60s) to avoid stale tokens. Alternatively, fetch the token outside the cache and pass it as a parameter.

```typescript
import { auth } from "@clerk/nextjs/server";
import { unstable_cache } from "next/cache";

export default async function ProfilePage() {
  const { userId, getToken } = await auth();
  if (!userId) return <div>Not signed in</div>;

  // Token fetched outside cache — always fresh
  const token = await getToken();

  const cachedGetUserData = unstable_cache(
    async (authToken: string) => {
      const res = await fetch(`${process.env.API_URL}/api/v1/users/${userId}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      return res.json();
    },
    [`user-${userId}`],
    { revalidate: 60, tags: [`user-${userId}`] },
  );

  const userData = await cachedGetUserData(token!);
  return <div>{userData.name}</div>;
}
```

## Revalidate After Mutations

After a Server Action mutates data, revalidate the cache tag:

```typescript
"use server";
import { revalidateTag } from "next/cache";
import { auth } from "@clerk/nextjs/server";

export async function updateProfile(formData: FormData) {
  const { userId, getToken } = await auth();
  if (!userId) throw new Error("Unauthorized");

  const token = await getToken();
  await fetch(`${process.env.API_URL}/api/v1/users/${userId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name: formData.get("name") }),
  });

  revalidateTag(`user-${userId}`);
}
```

## Org-Scoped Cache

```typescript
const { orgId, getToken } = await auth();

const getOrgData = unstable_cache(
  async () => {
    const token = await getToken();
    const res = await fetch(`${process.env.API_URL}/api/v1/orgs/${orgId}/data`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },
  [`org-${orgId}-data`],
  { revalidate: 300, tags: [`org-${orgId}`] },
);
```

## Cache + TanStack Query

For client-side data, TanStack Query handles caching via its own `staleTime` and `gcTime` (configured at 60s stale in `@ezra/hooks/queryProvider`). Server-side `unstable_cache` is only needed for Server Components.

| Context | Caching Mechanism |
|---------|-------------------|
| Server Components | `unstable_cache` with userId/orgId in key |
| Client Components (Orval hooks) | TanStack Query (automatic, staleTime: 60s) |
| Server Actions | `revalidateTag` / `revalidatePath` after mutations |

## Docs

[Next.js Caching](https://nextjs.org/docs/app/building-your-application/caching)
