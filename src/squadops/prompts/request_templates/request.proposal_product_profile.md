---
template_id: request.proposal_product_profile
version: "1"
required_variables:
  - surface_lines
  - placement_lines
optional_variables:
  - gaps_section
---
### What the product exposes, and where its tests run

**Its public surfaces.** A criterion asserts at one of these, the way a caller reaches the product:
an endpoint under the HTTP base, a page under the UI base, a command (or a subcommand of it), or a
name a package exports. A criterion on anything else is refused.
{{surface_lines}}

**Its test runners, and where a criterion's test goes under each.** The runner is the first one
listed whose tested paths hold every path the criterion exercises. A criterion whose paths no runner
tests, or only one that hosts no criterion, is refused:
{{placement_lines}}

{{gaps_section}}
