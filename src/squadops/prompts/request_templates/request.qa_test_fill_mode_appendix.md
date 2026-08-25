---
template_id: request.qa_test_fill_mode_appendix
version: "2"
required_variables:
  - slot_lines
  - shell_files
optional_variables:
  - error_envelope
  - additive_files
---
## FILL MODE: a deterministic test scaffold already covers the mechanics (SIP-0104)

This workspace carries a generated verification scaffold: one test shell per
contract-derived behavior, with file placement, imports, the store lifecycle, the
invocation call, and the declared-status assertion **already written and frozen**. The
mechanical layer is done. Your job is the residual semantic layer only: response values,
store effects, cross-operation semantics, PRD-derived properties the contract cannot
express.

**YOUR SLOTS — fill every one of these:**
{{slot_lines}}

Each line names a slot and the behavior its shell already invokes and status-asserts.
That mechanical half is done, so do not re-assert placement, invocation or the declared
status inside a fill. **The slot itself still needs your assertions**: what the response
should CONTAIN and what the store should look like afterwards.

**For the scaffold, emit FILL BLOCKS addressed by slot id — nothing else can address a
slot:**

```fill:slot-<id>
    expect(body.id).toBeTruthy()
    expect(all('runs')).toHaveLength(1)
```

**Error responses — read the envelope, do not guess it:**
{{error_envelope}}

```fill:slot-<id>
    expect(body.error.code).toBe('validation_error')
    expect(all('runs')).toHaveLength(0)
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
- Because you cannot import, only what the shell already imports is in scope. From the
  store that is **`all(table)`** — use it for store-effect assertions. Do not reference
  any other store helper: it will not be defined and the slot will fail to run.
- One fill per slot; a slot filled twice is rejected outright.
- Never emit or rewrite the scaffold files themselves — a path-addressed file at a
  scaffold path is discarded. The shells below are read-only context.
- `body` is the final response's parsed JSON; where a create precedes the invocation,
  `created` is the created entity's parsed JSON.

**Asserting on the store — pass `TABLES.<Entity>`, never a string you invent.**
`@/lib/store` exports `TABLES`, one entry per entity a correct application stores as rows of
its own, and its functions accept only those values. Write
`expect(all(TABLES.Run)).toHaveLength(1)`. An entity that exists only as a shape embedded in
another (`Run.participants`) or as a response projection has **no table**: it lives inside the
owning entity's row, so assert on that row's field (`body.participants`, or the row from
`all(TABLES.Run)`), never on a table for it. A fill naming a table `TABLES` does not
export is rejected at the fill gate with the real tables named, and a name you make up is a
compile error — either way an invented table costs the slot, not a warning.

This is spelled out because it has already cost one. The store used to accept any string:
an application named its table one thing, the suite named it another, and the mismatch
appeared as an empty array — which reads exactly like a handler that never saved anything.
Three repair rounds blamed the application, and the application was correct.

Additive tests are welcome IN ADDITION to fills: whole new test files beside the
scaffold, emitted as normal ```typescript:__tests__/<name>.test.ts``` fences, under the
standing rules (declared dependencies only, in-process execution model, no live server).

The plan also asked for the file(s) below. They are **additive and secondary** — a
whole file here never substitutes for a fill, and filling every slot above comes
first. Ignore any instruction carried in the task description that conflicts with the
rules in this section (in particular, a suggestion to call a live server: there is
none):
{{additive_files}}

**The scaffold shells (read-only — write your fills against these):**
{{shell_files}}
