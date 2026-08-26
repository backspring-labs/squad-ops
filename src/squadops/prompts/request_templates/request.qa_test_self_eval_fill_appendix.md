---
template_id: request.qa_test_self_eval_fill_appendix
version: "1"
required_variables:
  - unfilled_slot_lines
---

## FILL MODE — what "missing" means here

This task is in fill mode (the FILL MODE section of the original request still applies:
assertions only, `all(TABLES.<Entity>)`, the element kind read off the frozen floor). The
scaffold files are read-only: a path-addressed file at a scaffold path is discarded, and
a **fill block is the only way to change a slot**.

**Slots that are still not filled** (with the reason the previous fill was refused, where
there was one):
{{unfilled_slot_lines}}

If the list reads `(none)`, every slot is already filled — do not re-emit any fill; produce
only the additive file(s) the validation summary names.

Otherwise, emit one fill block per slot listed, **first, before anything else**:

```fill:slot-<id>
    expect(body.id).toBeTruthy()
    expect(all(TABLES.Run)).toHaveLength(1)
```

A fill re-emitted for a slot that is already filled is ignored. Any additive file the
validation summary names as missing follows the fills, as a normal
```typescript:__tests__/<name>.test.ts``` fence.
