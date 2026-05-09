# Server Actions (HIGH)

Server Actions are public HTTP endpoints. **Always verify auth at the start** — middleware alone is not enough because Server Actions can be invoked directly.

## Basic Protection

```typescript
"use server";
import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

export async function createDeal(formData: FormData) {
  const { isAuthenticated, userId, getToken } = await auth();
  if (!isAuthenticated) throw new Error("Unauthorized");

  const token = await getToken();
  const name = formData.get("name") as string;

  await fetch(`${process.env.API_URL}/api/v1/deals`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ company_name: name }),
  });

  revalidatePath("/deals");
}
```

> **Core 2**: `isAuthenticated` unavailable. Use `if (!userId)` instead.

**Note**: Server Actions run on the server, so they cannot use Orval-generated hooks (those are React hooks). Use `auth().getToken()` and direct `fetch` to the backend API. Alternatively, use the plain client:

```typescript
"use server";
import { auth } from "@clerk/nextjs/server";
import { createApiClient } from "@ezra/api-client/plain-client";

export async function createDeal(formData: FormData) {
  const { userId, getToken } = await auth();
  if (!userId) throw new Error("Unauthorized");

  const token = await getToken();
  const client = createApiClient(process.env.API_URL!, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await client.post("/api/v1/deals", { company_name: formData.get("name") });
}
```

## Org + Role Check

```typescript
"use server";
import { auth } from "@clerk/nextjs/server";

export async function createProject(formData: FormData) {
  const { userId, orgId, orgRole } = await auth();
  if (!userId || !orgId) throw new Error("Must be in an organization");
  if (orgRole !== "org:admin") throw new Error("Only admins can create projects");

  // proceed with backend API call
}
```

## Permission Check (RBAC)

```typescript
"use server";
import { auth } from "@clerk/nextjs/server";

export async function deleteDeal(dealId: string) {
  const { userId, has } = await auth();
  if (!userId) throw new Error("Unauthorized");

  const canDelete = await has({ permission: "org:deals:delete" });
  if (!canDelete) throw new Error("Forbidden");

  // proceed with backend API call
}
```

## Pattern: Server Action + TanStack Query Invalidation

After a Server Action mutates data, invalidate relevant TanStack Query caches client-side:

```tsx
"use client";
import { useQueryClient } from "@tanstack/react-query";
import { createDeal } from "@/actions/deals";

export function CreateDealForm() {
  const queryClient = useQueryClient();

  async function handleSubmit(formData: FormData) {
    await createDeal(formData);
    // Invalidate all deal-related queries (prefix matching)
    queryClient.invalidateQueries({ queryKey: ["v1", "deals"] });
  }

  return <form action={handleSubmit}>...</form>;
}
```

## Docs

[Clerk Server Actions](https://clerk.com/docs/reference/nextjs/server-actions)
