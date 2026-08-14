---
template_id: request.qa_test_fill_mode_appendix
version: "1"
required_variables:
  - slot_lines
  - shell_files
optional_variables: []
---
## FILL MODE: a deterministic test scaffold already covers the mechanics (SIP-0104)

This workspace carries a generated verification scaffold: one test shell per
contract-derived behavior, with file placement, imports, the store lifecycle, the
invocation call, and the declared-status assertion **already written and frozen**. The
mechanical layer is done. Your job is the residual semantic layer only: response values,
store effects, cross-operation semantics, PRD-derived properties the contract cannot
express.

**Already covered deterministically (do not re-test these behaviors mechanically):**
{{slot_lines}}

**For the scaffold, emit FILL BLOCKS addressed by slot id — nothing else can address a
slot:**

```fill:slot-<id>
    expect(body.id).toBeTruthy()
    expect(all('runs')).toHaveLength(1)
```

Fill EVERY slot listed above — with domain assertions, or with an explicit
not-applicable disposition when the declared status genuinely says everything:

```fill:slot-<id>
not_applicable: <one-line reason>
```

Rules for fill bodies (violations are rejected deterministically and the slot renders
as a failing state):

- Assertions only. NO imports, NO `require()`, NO `fetch()` or any network access —
  the suite runs in-process with no server.
- One fill per slot; a slot filled twice is rejected outright.
- Never emit or rewrite the scaffold files themselves — a path-addressed file at a
  scaffold path is discarded. The shells below are read-only context.
- `body` is the final response's parsed JSON; where a create precedes the invocation,
  `created` is the created entity's parsed JSON.

Additive tests are welcome IN ADDITION to fills: whole new test files beside the
scaffold, emitted as normal ```typescript:__tests__/<name>.test.ts``` fences, under the
standing rules (declared dependencies only, in-process execution model, no live server).

**The scaffold shells (read-only — write your fills against these):**
{{shell_files}}
