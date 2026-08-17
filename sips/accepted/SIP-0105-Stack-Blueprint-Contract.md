---
status: accepted
title: Stack Blueprint Contract
sip_number: 105
updated_at: '2026-08-17T18:46:44.835365Z'
---
# SIP-0105: Stack Blueprint Contract

## Status
**Accepted 2026-08-17** — rewritten against main at 1.6 Stage 2g; the acceptance gate (a second real stack) was met on 2026-08-10.

Accepted **with its unbuilt parts named** — see §"What acceptance does and does not assert". Acceptance here ran *after* implementation rather than before it, which is recorded there rather than smoothed over.

**Targets:** the release that adds the **second** stack — deliberately not before. **`nextjs_ts`
landed 2026-08-10**, so the gate is met; see §"The acceptance gate is met — what the second
stack settled".
**Builds on:** SIP-0099 (Contract-First Build Scaffolding), which established the expander
and the fill-slot/frozen split for `fullstack_fastapi_react`; SIP-0098 (verification
contracts derived from the manifest); SIP-0100 (scaffold ownership enforcement).
**Motivating case (historical, and now resolved by a different route):** adding a second stack
meant finding and updating **five separate per-stack surfaces**, four of which failed silently
when missed. S1's consolidation and Stage 2a's executable inventory closed that class without
minting blueprint vocabulary — see §"What happened instead". **The live brief is narrower:**
*what does a missing field mean?* was answered four times in feature PRs, and its strongest
answer lives only in a docstring.

---

## Summary

Give a stack a **type**, and govern what may be added to it.

The original framing — *"an identifier that indexes four module-level dicts plus one function
with the answer written inline"* — was accurate when written and is no longer true: S1
consolidated those facts into `ScaffoldStack`, and Stage 2a's inventory now asserts every stack
is a member of every registry. **What survives is the part that was always the design question
rather than the refactor:** what a stack must be *required* to declare, what a missing field
*means*, and who may add a field at all.

This SIP does **not** propose the consolidation — that was a pure refactor with a
byte-identical test and needed no design approval. It proposes the **contract and its
governance**, which binds every future stack and therefore should not be made from a sample
size of one. It now rests on two, with the limits of that sample stated rather than implied.

## The problem, precisely

> **This section described code that no longer exists.** The table below is kept as the
> historical statement of the problem, with what actually happened recorded beneath it.
> Rewriting it silently would erase the evidence that the diagnosis was right and the
> remedy arrived by a different route (2g, 2026-08-17).

`expand()` dispatch was already clean — `_EXPANDERS` is a registry and adding a key touches
no branching logic. The risk was never if-statement sprawl. It was that a stack was five
facts living in five places:

| A stack must declare | Where it lived | Failed how |
|---|---|---|
| how to expand the skeleton | `_EXPANDERS` | loudly (`ValueError`) |
| which files are fill slots | **inline in `fill_slot_paths()`** | **silently — returned the FastAPI map** |
| QA test directories | `_QA_TEST_NAMESPACES` | silently — empty namespace, every QA write unauthorized |
| harness entry modules | `_HARNESS_ENTRY_MODULES` | silently — the boundary check never fired |
| which vocabulary the typed checks use | `resolve_check_stack()` | silently — checks skip |

### What happened instead (S1, #818, #822, SIP-0104)

**S1 consolidated the scattered facts into `ScaffoldStack` without minting blueprint
vocabulary**, deliberately: `scaffold.py:1668` records that naming it `ScaffoldStack` rather
than a blueprint was chosen so the consolidation would not *"quietly mint its vocabulary."*
That discipline held.

**The silent-omission class is gone.** Stage 2a's executable inventory
(`test_stack_inventory.py`) enumerates six per-stack registries and asserts every stack is a
member of each; four further registries outside `ScaffoldStack` all raise on an unknown stack.
The failure mode this SIP was written about — a stack silently inheriting FastAPI's answer —
no longer has a path.

**What leaked instead was the layer above.** *"What does a missing field mean?"* is a
blueprint-contract question and it was answered four times in feature PRs. The strongest
answer — #818's asymmetric-default doctrine, *"visible-and-unverified has a safe default;
silently-wrong does not"* — exists only as a docstring at `scaffold.py:1696`. **That is what
this document is for**, and it is a narrower brief than the one it opened with.

**On the two vocabularies — the SIP's own proposal here was wrong.** It said *"a blueprint is
the natural place to collapse them."* Stage 2e measured it: there are **three** axes, and two
are not drift. Stack identity is one value across five registries. The probe profile differs
from the stack id on *both* stacks, consistently and correctly — booting is its own axis, and
two stacks could share a boot mechanism while sharing nothing else. Collapsing that would be
the error. See §"What the second stack settled" for `check_stack`, which is the real
conflation.

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

## The acceptance gate is met — what the second stack settled *(2g, 2026-08-17)*

This SIP declined its own acceptance until a second real stack existed. **`nextjs_ts` landed
2026-08-10**, and the gate then sat open for five days without surfacing as a decision,
because the stack arrived incrementally and nothing was watching for the moment.

The schema was drafted against both stacks (2b), falsified (2c), reconciled (2e) and its
admission rule enforced (2f). What follows is what the second stack actually answered — and
the honest summary is that **this document's four worries were right in shape and wrong in
one particular**, so the rewrite is ratification rather than greenfield.

### Three predictions confirmed

- **`harness_entry_modules` on a stack with no import boundary.** The SIP feared it "assumes
  a Python-style import boundary". Stack #2 shipped `()` **as a declared fact rather than an
  omission** (`scaffold.py:1773`) — the asymmetric-default doctrine in practice.
- **`check_stack` on a stack the AST checks cannot parse.** Stack #2 shipped `""`, which
  forced the question *"then what verifies this language?"* — and **SIP-0104's deterministic
  scaffold is that answer.** The empty field produced a capability rather than a gap.
- **Criteria families as a per-stack fact.** Proved pack-parameterized: stack #2 emits slot,
  build and suite families with no `routes`/`views` split.

### One genuine surprise: the shape is neither callable nor data

The SIP asked whether `expand` is *"a callable, or data a generic expander consumes"*. The
emerged answer is **neither**: two callables, two tuples, and **five string names indexing
registries owned by the layer that owns each vocabulary.** That name-indirection is applied
consistently and argued for each time, and it is a third option the document did not consider.

### And the vocabulary question resolves against this document

`check_stack` carries **two questions on one field**, measured at 2e:

| evaluator | guard | what it needs |
|---|---|---|
| `endpoint_defined` | `if stack != "fastapi"` | genuinely FastAPI — it reads `@router.get` |
| `field_present`, `function_defined`, `harness_boundary` | `if stack is None` | any declared dialect |

A third stack declaring `check_stack: "flask"` would skip the first **correctly** and pass the
other three **correctly** — by accident. **The accident holds only while exactly one
framework-specific evaluator exists.** The blueprint should carry the *language* dialect and a
framework-specific evaluator should name its own requirement; that touches the evaluator
contract, so it is 1.7 work, disclosed here rather than quietly promoted.

### Falsification: four fields do not survive it (2c)

Three have **no consumer of any kind** — `BuildProfile.artifact_output_mode`,
`BuildProfile.validation_rules`, and `DevelopmentCapability.expected_extensions`, the last
with two docstrings asserting it is *"what a dev agent is given."* One,
`BuildProfile.default_task_tags`, has a reader and is empty on all five profiles: it asserts
per-stack variability **zero** stacks demonstrate. None may enter the blueprint.

### The admission rule, stated permanently *(S5, 2f)*

**A new blueprint field must be demonstrated on at least two stacks before admission.** A
one-stack need is expressed as a declared optional capability **with its reason**, never as a
general field implying every stack has one.

This is the SIP's own argument applied to its successors: if generalising from one instance
produces FastAPI-with-generic-names, then *extending* from one instance does the same thing
one field at a time. It is **enforced**, not requested — `test_stack_blueprint_falsification`
fails a field populated by one stack until a reason is recorded, and fails one populated by no
stack outright.

### What this will NOT have validated — disclose, do not imply generality

- **`nextjs_ts` is only partially "maximally different."** Non-Python runner ✓, server-rendered
  ✓ — but it has a bundler and shares React and TypeScript with stack #1's frontend half. A
  two-stack schema still risks a **cousin-shaped** generalisation. Waiting for stack #3
  repeats the failure that produced this SIP.
- **Seven whole-tree builds per acceptance pass** on stack #2 against three on stack #1. A
  cost, not a concession; revisit only with a measurement.
- **No authorable static check on the API route slots beyond the build.** `next build` runs
  tsc with type errors fatal, so **the bundler check is the type check** — detection is
  covered, *attribution* is not.

---

## Historical: why this was not ready to accept *(superseded above)*

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

## What acceptance does and does not assert *(owner ruling 2026-08-17)*

Accepted with its unbuilt parts named, because the normal sequence did not happen here and
saying so is the difference between a commitment and a claim.

**Acceptance ran BACKWARDS, and that is the honest record.** A SIP is meant to be accepted as
a design commitment *before* implementation. Here the gate — "the existence of a second real
stack" — was met on 2026-08-10 and **nothing surfaced it for a week**, because the stack
arrived incrementally and there was no event to trigger the decision. Meanwhile the schema was
written anyway: `ScaffoldStack` grew from five fields to nine, each in a feature PR. So the
gate did not stop the design being made. It stopped it being made *deliberately*.

**What acceptance asserts:** the contract and its governance are committed — what a stack must
declare, what a missing field means, and S5's admission rule that a new field must be
demonstrated on two stacks. Those rest on two real stacks and are enforced by
`test_stack_blueprint_falsification`.

**What acceptance does NOT assert — these are not built:**

| unbuilt | status |
|---|---|
| **Packs / plugin loading** | Not built, and the durable reason to keep this document. A stack is still registered in-tree, not loaded as a pack. |
| **`check_stack` split into language dialect vs framework requirement** | Not built. Deferred to **1.7** — it touches the evaluator contract. The current field carries two questions on one field and works only while exactly one framework-specific evaluator exists. |
| **Where a blueprint lives** | Not decided. `stack_nextjs_ts.py` is already a pack shipping its own expander while stack #1 is inline in `scaffold.py`; resolving the asymmetry moves bytes the reference contract is pinned to. Trigger: the packs work. |
| **Deleting the four fields 2c falsified** | Not done. Recorded and pinned in the falsification gate, to be removed before the schema freezes rather than after it accretes meaning. |

**And one limit on the evidence itself:** `nextjs_ts` is only *partially* the "maximally
different" second stack this SIP asked for — non-Python runner and server-rendered, but it has
a bundler and shares React and TypeScript with stack #1's frontend half. **A two-stack schema
still risks a cousin-shaped generalisation.** Waiting for a third stack would repeat the
failure that produced this SIP, so the sample is accepted with its shape stated rather than
implied.

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

> **Answered against the second stack (2g, 2026-08-17).** Each is marked with what the
> evidence says. Two are settled, one is settled *against* the option this SIP preferred, and
> one is deliberately left open with its trigger named.


- **Does the blueprint own the container/packaging set?** **NO — answered by composition.**
  `EnvironmentContract` already owns it, and gained `build_mutates_source` for stack #2
  without the blueprint being involved. The concern was real and the owner turned out to be a
  different seam. **Still open beneath it:** §4c of the schema draft argues the packaging set
  is plausibly a *deployment-target* fact rather than a stack fact, which a third stack on the
  same target would settle.
- **One blueprint per stack, or a composition of backend + frontend blueprints?** **ONE, on
  the evidence.** Next.js **collapses the split entirely** — one project, one tree, one build —
  and it is the stack chosen to stress the manifest's api/frontend split. That is evidence
  against composition as the primary shape, from the case most likely to demand it.
- **Is `expand` a callable, or data a generic expander consumes?** **NEITHER — this is the
  one genuine surprise.** The emerged shape is two callables, two tuples, and five string
  names indexing registries owned by the layer that owns each vocabulary. Stack #2 derives
  file *location* from the route path, which is a computation over the manifest and not a
  table; expressing it as data would build a template language — code with worse tooling and
  no type checking.
- **Where does the blueprint live?** **Still open, and the asymmetry now names its own
  resolution.** `stack_nextjs_ts.py` is already a pack shipping its own expander; stack #1 is
  still inline in `scaffold.py`. The asymmetry resolves by pushing S1 out, not pulling S2 in —
  but that moves bytes the reference contract is pinned to, so it is a deliberate act with its
  own boundary rather than a tidy-up. **Trigger: the packs/plugin-loading work**, which is the
  durable reason to keep this document at all.

## Non-goals

Adding a second stack (this only makes it cheap). Changing what the existing expander emits.
Touching the verification contract schema. Any behavioural change at all — if this SIP's
implementation moves a contract hash, it is wrong.
