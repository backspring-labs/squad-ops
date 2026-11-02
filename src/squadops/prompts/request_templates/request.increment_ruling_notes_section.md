---
template_id: request.increment_ruling_notes_section
version: "1"
required_variables:
  - ruling_notes
---

### The reviewer's notes on the approval

The reviewer approved this change request and wrote these notes on how it is to be built. Your plan
follows them where they apply, inside the change request's footprint. Where a note asks for
something the change request doesn't cover, the change request decides.

For example, a note saying "an empty search returns the whole shelf, in its usual order" becomes a
behaviour the design states and a criterion the tests check. It does not add a file outside the
footprint.

{{ruling_notes}}
