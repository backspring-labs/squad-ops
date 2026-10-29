---
template_id: request.increment_views_appendix
version: "1"
required_variables:
  - view_lines
---

## The pages this change adds, and the anchor each one's view renders

Each page below is one this change adds. Its view gives its root element the anchor as its
`data-testid`: for the anchor `export-view`, the view's outermost element is written as
`<section data-testid="export-view">`. When the increment is judged, each page is opened in a
browser on the built product, and it holds only when an element on it carries that `data-testid`.
A page without it rejects the increment, whatever its tests read. A criterion's test on one of
these pages finds the view by the same anchor.

{{view_lines}}
