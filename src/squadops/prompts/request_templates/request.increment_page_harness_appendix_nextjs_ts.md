---
template_id: request.increment_page_harness_appendix_nextjs_ts
version: "1"
required_variables:
  - page_criteria
  - page_loader_import
  - route_caller_import
---

### How a criterion's test renders its page

Each of these criteria is proven on a page: {{page_criteria}}. Its test runs twice: on the
application before this change, where it must fail, and on the built change, where it must pass.
A page this change adds has no `page.tsx` before the change, and neither does a route it adds. A
test that imports either module fails before any assertion runs, which never counts as the
criterion failing, and the increment is refused however correct the build.

So **a criterion's own test** loads its page through the scaffold's `loadPage`, and answers the
page's requests through `callRoute`, both imported as shown. It never imports a page or a route
module. This replaces, for those test files only, the page import your other instructions show:
that form is right for a page that already exists, and a criterion's page may not. Every other
test keeps it.

The paths, fields and test ids below are illustrative. Use your criterion's own page and anchors,
and the request shapes in the manifest:

```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { loadPage } from '{{page_loader_import}}'
import { callRoute } from '{{route_caller_import}}'

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/archive',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}))
vi.stubGlobal('fetch', (path: string, init: RequestInit = {}) => {
  const { signal: _signal, ...rest } = init
  return callRoute(rest.method ?? 'GET', path, rest)
})

describe('T7: the archive page', () => {
  it('lists an archived run', async () => {
    const created = await callRoute('POST', '/api/runs', {
      body: JSON.stringify({ title: 'Lakeside loop', datetime: '2030-05-01T07:00', location: 'Dock 3' }),
      headers: { 'content-type': 'application/json' },
    })
    const run = await created.json()
    await callRoute('POST', `/api/runs/${run.id}/archive`)
    const Page = await loadPage('/archive')
    render(<Page />)
    expect(await screen.findByTestId('archive-row')).toHaveTextContent('Lakeside loop')
  })
})
```

`loadPage(path)` finds the page the App Router serves for the path, as `callRoute` finds a route,
and returns it ready to render with its `params` and `searchParams` props. Pass the path as a
browser shows it, with its params filled in (`/runs/r1`, not `/runs/:run_id`); a page that reads
them through `useParams` reads what your `next/navigation` mock returns. A path no page serves
renders a 404 page without your anchors, and a route no handler serves answers 404, so before the
change the test fails at its assertion.
