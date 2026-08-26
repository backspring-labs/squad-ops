---
template_id: request.qa_test_repair_fill_appendix
version: "1"
required_variables:
  - failed_slot_lines
---

## FILL MODE REPAIR — the slots whose fills failed

The FILL MODE section above is the contract you author under here too: assertions
only, `all(TABLES.<Entity>)`, the element kind read off the frozen floor, in-process
execution with no server. The scaffold files are read-only: a path-addressed file at
a scaffold path is discarded, and a **fill block is the only way to change a slot**.

**These slots failed, with the runner's own reason:**
{{failed_slot_lines}}

Emit one replacement fill block per slot listed — **first, before anything else** — and
nothing for slots not listed unless the failure reason above implicates them. Every
other slot keeps the fill it already has, byte for byte.

```fill:slot-<id>
    expect(body.id).toBeTruthy()
    expect(all(TABLES.Run)).toHaveLength(1)
```

Fix the fill, not the application: if the reason above says the response or the store
did not match what the fill asserted, and the fill asserted something the contract does
not declare, correct the fill; a fill the shell's frozen floor already contradicts is
rejected at the gate with the declared kind named.
