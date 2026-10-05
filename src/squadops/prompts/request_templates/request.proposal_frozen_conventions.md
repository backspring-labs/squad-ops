---
template_id: request.proposal_frozen_conventions
version: "1"
required_variables:
  - convention_sections
---

### What the application's frozen code already decides

Part of the application is generated from the manifest and frozen: no build changes it, before your
change or after. The rules below hold in every build. A criterion that asserts one of them names
nothing new, so it cannot fail on the accepted application. A criterion that contradicts one fails
every correct build.

{{convention_sections}}
