---
template_id: request.design_revision_request_appendix
version: "1"
required_variables:
  - reviewer_notes
---
## THIS CYCLE'S PREVIOUS FRAMING WAS RETURNED — respond to it

An earlier attempt at this cycle's framing was sent back, either by a reviewer reading the
proposed interface or by a deterministic gate rejecting the plan built from it. You are
producing the technical design again so that it **answers what came back**, not so that you
can design the application from scratch.

### What was returned

{{reviewer_notes}}

### How to respond

- **Address it directly in the design.** The interface manifest is being revised against the
  same notes; if your design and that manifest disagree, the next reader cannot tell which
  one the squad meant.
- **Keep everything that was not raised.** Re-deriving the rest replaces decisions that were
  accepted with different ones, for no gain.
- **If a note answers a question the design left open,** record the answer as settled and say
  where it came from, so the reasoning survives past this cycle.
- **If you think it is wrong,** say so explicitly and explain why. A design that quietly
  complies while believing otherwise is worse than a disagreement on the record.
