---
template_id: request.target_stack_section
version: "1"
required_variables:
  - stack
  - stack_narrative
---
## TARGET STACK — decided, not proposed

This cycle builds **`{{stack}}`**. That is a platform decision already made by the cycle's
configuration; it is not yours to choose, revisit, or improve on.

{{stack_narrative}}

**If the requirements document names a different stack, the stack above wins and the PRD is
the thing that is out of date.** A PRD often states the architecture that existed when it was
written. Designing for what it names instead of what this cycle configures produces a design
nobody can build: the scaffold expands `{{stack}}`, every file lands somewhere your design did
not anticipate, and the mismatch surfaces hours later as an unrelated failure.

Design *within* this stack. Its conventions — where routes live, how views are addressed, what
a test file is — are inputs to your design, not details to be settled later by whoever
implements it.
