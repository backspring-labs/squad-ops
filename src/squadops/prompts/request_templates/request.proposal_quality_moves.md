---
template_id: request.proposal_quality_moves
version: "1"
required_variables:
  - quality_lines
---

### This application's quality against the campaign's first accepted build

Each measure as the evaluator read it on the first accepted build, then on this one, averaged over
the pages both builds served. Lighthouse scores run from 0 to 1, and higher is better. Axe and lint
count violations, and lower is better.

{{quality_lines}}
