# SIP: Stack Blueprint Contract

## Status
Draft (proposed)

**Targets:** the release that adds the **second** stack — deliberately not before. See
§"Why this is not ready to accept".
**Builds on:** SIP-0099 (Contract-First Build Scaffolding), which established the expander
and the fill-slot/frozen split for `fullstack_fastapi_react`; SIP-0098 (verification
contracts derived from the manifest); SIP-0100 (scaffold ownership enforcement).
**Motivating case:** adding a second stack today means finding and updating **five separate
per-stack surfaces**, four of which fail silently when missed. One of them —
`fill_slot_paths` — already hardcodes the FastAPI slot map behind a guard that only checks
whether the stack is *registered*, so a second stack would inherit `backend/routes.py` as a
fill slot and nothing would object.

---

## Summary

Give a stack a **type**. Today "a stack" is an identifier that indexes four module-level
dicts plus one function with the answer written inline. Replace that with a single
`StackBlueprint` object per stack, registered once, so adding a stack is one object and a
missing field is an import-time type error rather than a wrong answer three hours into a
cycle.

This SIP does **not** propose the consolidation of today's five facts — that is a pure
refactor with an exact byte-identical test and needs no design approval. This SIP proposes
**what a stack must be required to declare**, which is a commitment that binds every future
stack and therefore should not be made from a sample size of one.

## The problem, precisely

`expand()` dispatch is already clean — `_EXPANDERS` is a registry and adding a key touches
no branching logic. The risk is not if-statement sprawl. It is that a stack is five facts
living in five places:

| A stack must declare | Where it lives | Fails how |
|---|---|---|
| how to expand the skeleton | `_EXPANDERS` | loudly (`ValueError`) |
| which files are fill slots | **inline in `fill_slot_paths()`** | **silently — returns the FastAPI map** |
| QA test directories | `_QA_TEST_NAMESPACES` | silently — empty namespace, every QA write unauthorized |
| harness entry modules | `_HARNESS_ENTRY_MODULES` | silently — the boundary check never fires |
| which vocabulary the typed checks use | `resolve_check_stack()` | silently — checks skip |

Four of five fail silently, and the failure surfaces as an unexplained mid-cycle result
rather than a startup error.

**There are also already two stack vocabularies.** The manifest says
`fullstack_fastapi_react`; the acceptance checks branch on `stack != "fastapi"`. They are
bridged by `resolve_check_stack()` and have drifted apart. A blueprint is the natural place
to collapse them.

## Proposed shape (illustrative, not settled)

```python
@dataclass(frozen=True)
class StackBlueprint:
    id: str
    expand: Callable[[InterfaceManifest], list[dict[str, str]]]
    fill_slots: Callable[[InterfaceManifest], tuple[str, ...]]
    qa_test_namespace: tuple[str, ...]
    harness_entry_modules: tuple[str, ...]
    check_vocabulary: str      # collapses the two stack vocabularies
    analysable_suffix: str     # which files the AST checks may parse
```

Every public function becomes a lookup. `is_scaffoldable_stack` becomes membership.

The `analysable_suffix` field is load-bearing beyond tidiness: the typed acceptance checks
currently hardcode `.py`, and a check handed a file it cannot parse used to raise rather
than skip — which cost pf-41 three of its five correction attempts. A stack-derived source
language removes the hardcode at its root.

## Why this is not ready to accept

**Every field above is FastAPI-shaped thinking.**

- `analysable_suffix: str` assumes one analysable language per stack. A stack with a typed
  frontend has two.
- `harness_entry_modules` assumes a Python-style import boundary between tests and the app.
- `qa_test_namespace` assumes test ownership is expressed as directory prefixes.
- `fill_slots` as a callable over the manifest assumes slots are derivable from declared
  entities and routes.

Generalising from one instance does not produce a general contract. It produces the FastAPI
contract with generic field names — which is worse than no contract, because it looks
authoritative and the second stack will quietly bend itself to fit rather than reveal the
mismatch.

**So the acceptance gate for this SIP is the existence of a second real stack**, and the
schema should be written against both. Until then this document exists to hold the problem
statement and to stop anyone inventing the schema under deadline pressure while adding
stack #2.

## Sequencing

1. **Now, no SIP required:** consolidate today's five facts into one object with today's
   fields. Pure refactor; the test is exact — `expand()` output byte-identical, contract
   `content_hash` and `interface_manifest_hash` unmoved, both emission gates 6/6, regression
   unchanged. This removes the silent-omission failure mode immediately and prejudges
   nothing, since a single object is a strictly better starting point for the schema than
   five scattered dicts.
2. **When stack #2 is scoped:** promote this SIP, write the schema against two real stacks,
   reconcile the two stack vocabularies, and decide whether the blueprint also owns the
   packaging set (see below).
3. **After:** migrate the typed checks off their hardcoded `.py` onto the blueprint's
   declared source language.

## Open questions for review

- **Does the blueprint own the container/packaging set?** The Functional App roadmap's stack
  blueprint already claims the Dockerfile ("deterministic, checked in, never LLM-authored"),
  and #598 measured LLM-authored packaging failing to build on two consecutive rolls with
  *different* defects each time. Strong candidate, but it widens the blueprint from "how to
  scaffold source" to "how to ship", which may deserve its own boundary.
- **One blueprint per stack, or a composition of backend + frontend blueprints?** A
  FastAPI+React stack and a FastAPI+Vue stack share a backend half entirely. Composition
  avoids duplication but adds a join nobody needs until the third stack.
- **Is `expand` a callable on the blueprint, or does the blueprint declare data that a
  single generic expander consumes?** The latter is more constrained and more testable; it
  is also a much larger change and may not survive contact with a genuinely different stack.
- **Where does the blueprint live?** `scaffold.py` is already large. A `stacks/` package with
  one module per stack is the obvious home, but that is a file-layout decision worth making
  once rather than twice.

## Non-goals

Adding a second stack (this only makes it cheap). Changing what the existing expander emits.
Touching the verification contract schema. Any behavioural change at all — if this SIP's
implementation moves a contract hash, it is wrong.
