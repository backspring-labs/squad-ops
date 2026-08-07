---
status: proposed
title: Stack Blueprint Contract
---
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

## Test-type taxonomy (added 2026-07-27 — pf-47/pf-49 evidence)

Three production defects in twenty-four hours traced to the same missing dimension, so it
is recorded here as a first-class schema requirement rather than a field on the side.

**The evidence.** (1) pf-47 and pf-49 both burned their full correction budgets in a
repair deadlock: every typed check on a frontend test file skips (Python-AST checkers),
so no repair could ever produce an executed verdict — fixed tactically by check
applicability + retest-decides (PR #624). (2) pf-49's repair was routed to the dev role
to rewrite QA's own broken test file: the failure-locus table reads **pytest** exit-code
semantics (exit 2/4 = suite broken, exit 1 = subject broken), but Vitest signals a
transform failure with the same exit 1 it uses for assertion failures — the classifier
cannot be corrected by exit codes alone. (3) The `tests_pass` evidence aggregates every
runner into one `{executed, exit_code, tests_passed}` shape with no record of who
produced it, so heterogeneous evidence arrives pre-flattened.

**The pattern.** The task layer has one task type (`qa.test`), one check (`tests_pass`),
and one evidence shape for things that differ on every axis the correction machinery
cares about. The verification contract already distinguishes `build` / `suite` /
`probes` as separate behavioral families — the taxonomy exists upstream and is thrown
away the moment work becomes tasks.

**The deeper defect in `analysable_suffix` (sharpened in review, 2026-07-27).** The
sketch's `analysable_suffix: str` was not merely awaiting a second stack to falsify it —
**the first stack already did**. `fullstack_fastapi_react` has been Python *plus*
JavaScript since the expander's first commit; the singular was never true for any real
instance. The assumption survived its own counterexample because the field was written
from the *checker's* perspective: "analysable" meant "what our Python AST parser can
read" — a limitation of the tooling encoded as a property of the domain. The frontend
was not modeled as a second language without checkers; it was silently absent, and
absence demands no handling — every downstream organ inherited the omission without
confronting it. The schema must therefore split the conflated field: the stack declares
its **languages as facts**; **checker coverage is a separate per-language declaration**;
and an empty checker list ("javascript: no structural checkers yet") is a representable,
load-bearing state that forces downstream consumers — check authoring, locus routing,
repair acceptance — to answer "then what verifies this language?" explicitly. A partial
model is worse than none: it implies the rest does not exist.

**The requirement.** *Test type* is a first-class classification, carried on the QA task
and threaded into its evidence; *runner* is an implementation property of the type, not
the classification itself. Each blueprint populates a handling row per type:

| axis | backend-unit | frontend-component | frontend-build | behavioral-probe |
|---|---|---|---|---|
| runner | pytest | vitest | vite | probe runner |
| evidence vocabulary | exit 1 / 2 / 4 distinct | exit 1 only; suite-broken visible in **output**, not exit code | build log | HTTP status |
| suite-broken → repairer | QA re-authors | QA re-authors | n/a (build is the test) | n/a (probes are contract-owned) |
| subject-broken → repairer | dev | dev | dev | dev, always |
| repair verification | AST checks + retest | retest only (no structural checks exist) | re-run build | re-fire probe |
| execution locus | QA container | QA container | QA container | sandbox (SIP-0102) |

This strengthens the existing open question toward **"the blueprint declares data that
generic machinery consumes"**: the locus classifier, repair router, and patch-acceptance
policy all become lookups over the type row instead of encoding one stack's runner
conventions as universal truths. It also sharpens the acceptance gate: the second
stack's schema must be written against at least two *test types* per stack, or the
generalisation repeats the pytest-universal mistake one level up.

**Near-term seam (filed separately, not blocked on this SIP):** thread the test type and
runner identity into `test_result` at the runner seam, and key the locus table on it —
conservative default (unknown type → UNKNOWN → dev chain) preserves today's behavior
exactly. *Status 2026-07-29: shipped (#626 via PR #642 — `RunTestsResult.runner` +
runner-owned `suite_broken` verdicts) and validated live in the FAY measurement window:
fay-3's pytest exit 1 classified subject-broken and routed to the dev chain correctly;
fay-6's vitest failures were not misread as pytest exits.*

## Product intent: stack packs (recorded 2026-07-29)

The owner's direction, recorded so the blueprint schema is designed toward it rather than
discovered to conflict with it later: stacks become **packs — plugins loadable at runtime**.
A squad is given a stack-agnostic PRD; the pack selection decides how the squad implements
it (the canonical thought experiment: the same group_run PRD built on LAMP). The pipeline
already has the right joints — agnostic PRD → pack-flavored interface manifest →
pack-owned expander and check menu — and `dev_capability` is already a config selector.
The blueprint of this SIP is the pack's core declaration; "plugin" adds a loading/packaging
story on top, not a different schema.

Two consequences for the schema, both learned the cheap way this window:

- **The contract emitter's criteria families are pack-parameterized, not universal.** A
  server-rendered stack has no frontend build step — `vc-frontend-builds` is meaningless
  for LAMP, while HTTP probes and suite checks transfer untouched. The pack therefore
  declares not just how to scaffold but **which criteria families the emission gate may
  draw from**. (This does not touch the consolidation refactor's non-goal; it binds the
  eventual schema.)
- **Pack quality and roll yield are separate variables.** Yield is partly a function of how
  deeply the implementation model knows the stack (training distribution). A perfect pack
  for an obscure stack will still roll worse than a mediocre pack for FastAPI or LAMP. The
  blueprint cannot fix this and should not be judged by it.

## FAY window evidence (2026-07-29): the pack interface, discovered by loss mode

The first pre-registered Functional App Yield window (fay-2..fay-7, deploy `880b1ea9`)
produced loss modes that each name a declaration the blueprint must carry. This is the
empirical companion to the schema discussion above — the interface was discovered by
friction, not invented:

| Window evidence | Required pack declaration |
|---|---|
| #626 (shipped, validated live) | runners + per-runner suite-health semantics (exit tables vs output signatures) |
| #633 (shipped; fay-6 ran authored vitest suites) | test-harness provisioning: devDeps, config, frozen setup/harness files |
| fay-6: frontend suites non-convergent — dev and QA have no shared DOM truth; both saw each other's artifacts and still disagreed (a shared *record* is not an *arbiter*) | **verification anchors** for UI surfaces (scaffold-declared testid convention injected into both dev and QA prompts) — the same contract-as-arbiter move that makes backend suites converge |
| 3 of 5 scored plans authored doomed verification tasks (`node --check` on `.jsx` twice, template-unknowable regexes once) — models correctly sense verification gaps and reach for wrong tools (#645) | the **named check menu**: the blueprint declares the checks plan authors may use; free-form commands are both a per-roll failure mode and unportable across stacks. The menu *is* the pack's verification API |
| fay-4: a build-breaking view was invisible until final verification — view tasks carry prose-only criteria | the menu must include **per-language compile/build checks available at task time**, not only as final-verification guards |
| SIP-0102's environment contract (image + operation commands + readiness + port) already exists as a seam; the FAY auditor consumes it for every functional score | strong evidence for the open question below: the blueprint owns (or composes with) the **environment/packaging contract** — `FULLSTACK_FASTAPI_REACT` is already one instance of it |

Sequencing note: the two 1.5-candidate items — the curated check menu (#645's structural
fix) and the workspace-revision unification — are **pack-enablement work without being
named that**: they shrink and enumerate exactly the surface a pack must fill. The
acceptance gate stays the second real stack; choose it **maximally different** (server-
rendered, no bundler, non-Python test runner) so the schema is written against genuine
variance rather than a cousin of stack #1.

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
