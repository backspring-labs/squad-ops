A Next.js application using the App Router, written in TypeScript. **One project at the
repository root** — there is no separate backend or frontend tree, and no `frontend/`
directory.

- **Server endpoints are route handlers** at `app/api/<path>/route.ts`, exporting one async
  function per HTTP method (`export async function POST(request: Request)`). Not server
  actions: an action has no stable URL, so nothing can address it over HTTP.
- **A path parameter is a directory in brackets** — `/runs/{run_id}` lives at
  `app/api/runs/[run_id]/route.ts`, and its value arrives in the handler's second argument.
- **Pages are `app/<path>/page.tsx`** with a default-exported component. The URL comes from the
  directory; the filename is always `page.tsx`.
- **Server-first.** `'use client'` belongs only on a component that genuinely needs browser
  interactivity — anything client-rendered is absent from the initial HTML.
- **Shared code lives in `lib/`** and is imported through the `@/` alias.
- **Tests are vitest**, in `__tests__/`, with a `.test.ts` suffix.
- **`next build` type-checks.** TypeScript is strict and build failures on type errors are
  deliberate: it is the only static analysis this stack has.
