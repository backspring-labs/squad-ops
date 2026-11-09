---
template_id: request.increment_page_loader_appendix
version: "1"
required_variables:
  - page_loader_lines
  - page_loader_source
---

### How a page criterion's test loads its view

Each criterion below is proven on a page, and its test runs twice: on the product before this
change, where it must fail, and on the built change, where it must pass. A view this change adds
has no module before the change. A test that imports it fails before any assertion runs, which
never counts as the criterion failing, and the increment is refused however correct the build.

So each of these tests loads its view through `loadView`, from the page loader beside it, and
never imports the view's module itself:

{{page_loader_lines}}

The loader is the framework's file. It is written beside the test in every tree the test runs
on, so write the test file alone, never a file at the loader's path. It is, in full:

```js
{{page_loader_source}}
```

Pass `loadView` the view's module as your test's own import would name it, relative to the test's
directory, and render what it returns as the product's own tests render a view: under its
router, with its providers, its requests stubbed as they stub them. Before the change it
renders the not-found text in place of the view, so the test fails at the assertion that looks
for the view's anchor. The paths, data and test ids below are illustrative: use your criterion's
own view, route and anchor.

```jsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { loadView } from './criterion_page_loader'

describe('P1: the trail search page', () => {
  it('lists the trail the query matches', async () => {
    vi.stubGlobal('fetch', async () => new Response(JSON.stringify([{ id: 't1', name: 'Fernhollow' }])))
    const TrailSearchView = await loadView('../views/TrailSearchView.jsx')
    render(
      <MemoryRouter initialEntries={['/search?q=fern']}>
        <TrailSearchView />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('trail-search-view')).toHaveTextContent('Fernhollow')
  })
})
```

A view that exists before the change is loaded the same way, and is what the test renders on
both trees. Every other test in the suite, one no criterion above names, imports its views as
the product's own tests do.
