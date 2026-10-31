---
template_id: request.increment_route_harness_appendix_nextjs_ts
version: "1"
required_variables:
  - route_criteria
  - route_caller_import
---

### How a criterion's test calls its route

Each of these criteria is proven at an API route: {{route_criteria}}. Its test runs twice: on the
application before this change, where it must fail, and on the built change, where it must pass.
A route this change adds has no `route.ts` before the change. A test that imports the route module
fails before any assertion runs, which never counts as the criterion failing, and the increment is
refused however correct the build.

So **a criterion's own test** calls its route through the scaffold's `callRoute`, imported as shown,
and never imports a route module. This replaces, for those test files only, the direct import your
other instructions show: that form is right for a route that already exists, and a criterion's
route may not. Every other test keeps the direct import.

The paths and fields below are illustrative. Use your criterion's own surface, and the request
shapes in the manifest:

```ts
import { describe, expect, it } from 'vitest'
import { callRoute } from '{{route_caller_import}}'

describe('T9: archiving a run', () => {
  it('answers 200 and marks the run archived', async () => {
    const created = await callRoute('POST', '/api/runs', {
      body: JSON.stringify({ title: 'Lakeside loop', datetime: '2030-05-01T07:00', location: 'Dock 3' }),
      headers: { 'content-type': 'application/json' },
    })
    const run = await created.json()
    const res = await callRoute('POST', `/api/runs/${run.id}/archive`)
    expect(res.status).toBe(200)
    expect((await res.json()).archived).toBe(true)
  })
})
```

`callRoute(method, path, init)` routes the path as the App Router does and calls the handler it
finds with the request and its `params`. A path no route serves answers 404, and a method its route
doesn't export answers 405, so before the change the test fails at its assertion. Pass a request
body as `init`, as above. Read the store through `@/lib/store`, as the frozen harness test does.
