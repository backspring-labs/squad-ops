---
template_id: request.development_develop_fill_only_appendix_nextjs_ts
version: "3"
required_variables:
  - stack
optional_variables:
  - error_contract
  - model_surface
  - testid_surface
  - frozen_surface
  - response_surface
---
## Fill-only: a walking skeleton is already in your workspace

This build was scaffolded (`{{stack}}`). A deterministic tool has **already generated a
wired, buildable, bootable Next.js App Router application** into your workspace — config,
data models, the in-memory store, the error envelope, the client fetch helper, and
route/page **stubs**. It already builds and boots. Your job is to **fill the bodies of the
fixed slots** — never to rebuild, rewire, or regenerate the scaffold.

**FILL — edit only the stubbed bodies:**
- API route handlers in `app/**/route.ts` — implement each exported `GET`/`POST`/… inside
  the existing function. `ApiError` and `errorResponse` from `@/lib/errors` and the store
  from `@/lib/store` are already imported and wired; use them. A route file's directory
  IS its URL, so a handler in `app/api/runs/[run_id]/route.ts` serves
  `/api/runs/<run_id>`.
- Page components in `app/**/page.tsx` — implement each component's body.

**The store seam, stated exactly — pass `TABLES.<Entity>`, never a string you invent:**
`@/lib/store` exports `TABLES`, one entry per entity a correct application stores as rows of
its own, and its functions accept only those values. An entity that exists only as a shape
embedded in another (`Run.participants: Participant[]`) or as a response projection has no
table — store it inside the owning row and project it in the handler. Write
`insert(TABLES.Run, run)` and `all(TABLES.Run)`. A name you make up is a
compile error, and the build fails on compile errors — so the cost of inventing one is the
whole run, not a warning. Read the table names out of `TABLES`; do not retype them as
strings, and do not add a table of your own.

The reason this is spelled out: the store used to take any string. An application named its
table one thing, its test suite named it another, and the mismatch showed up as an empty
array — indistinguishable from a handler that never saved anything. A cycle spent its entire
repair budget rejecting an application that worked.

**The client seam, stated exactly — this is where fills go wrong:**
`api()` from `@/lib/api` fetches **the path you pass it, verbatim. It adds no prefix.**
Pass the endpoint's FULL declared URL path, exactly as the interface manifest declares
it:

```ts
const runs = await api<Run[]>('/api/runs')          // correct — the declared path
const run  = await api<Run>(`/api/runs/${id}`)      // correct
await api('/runs')                                  // WRONG — 404, no such route
```

If your manifest declares `POST /api/runs`, the page calls `api('/api/runs')`. Dropping
the prefix compiles, passes type-checking, and returns 404 at runtime for every action in
the UI — a silent break no build or unit check catches.

**When the page itself fetches, it must not do so at build time.** `next build`
prerenders server components in Node, where a relative `api('/api/runs')` throws
`Failed to parse URL` and **the build fails**. A page that fetches data is therefore
either a client component (`'use client'` at the top, fetch inside `useEffect`) or a
server component that opts out of prerendering with `export const dynamic =
'force-dynamic'` above the component. Pick one; a bare server component that awaits
`api()` in its body costs the build.

**DO NOT touch the scaffold-owned surface — it is frozen and verified:**
- Do NOT change the exported handler **names, signatures, or file locations** in
  `app/**/route.ts` — the directory determines the URL the app serves.
- Do NOT edit `lib/models.ts`, `lib/store.ts`, `lib/errors.ts`, `lib/api.ts`,
  `app/layout.tsx`, `package.json`, `tsconfig.json`, `next.config.mjs`, or
  `vitest.config.ts`.
- Do NOT add or remove files, or move a route/page to a different directory.

{{error_contract}}

{{model_surface}}

{{testid_surface}}

{{frozen_surface}}

{{response_surface}}

Filling the fixed slots — rather than regenerating the app — is the whole point: the
skeleton already builds and boots, so a fill that preserves it stays green, while one
that rewrites scaffold-owned files is rejected by the verification contract. When in
doubt, change less: implement the body, keep everything around it exactly as scaffolded.
