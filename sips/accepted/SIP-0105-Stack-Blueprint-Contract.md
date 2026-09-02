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

## Design decisions harvested from the stack #1 expander (#1149, 2026-09-01)

**Why this section exists.** #1131 extracts the inline `fullstack_fastapi_react` expander out
of `src/squadops/capabilities/scaffold.py` into a stack module of its own, the way stack #2
already lives in `stack_nextjs_ts.py`. The "why" of stack #1 lives in that block's comments
and docstrings, and a comment survives an extraction only if the refactorer reads it. #1149
makes the harvest the precondition of the move: the rationale is recorded here first, the
extraction PR cites the entries it preserves, and the code comments stay in the code as well
(a comment is necessary, not sufficient — `CLAUDE.md`). This SIP is the home because it
governs the seam the extraction serves; the proposed Design Decision Register SIP would be
the general mechanism and is still `proposed`, so this line does not wait for it. Same shape
as SIP-0104 §13, different purpose: these are not amendments to this SIP's design, they are
the decisions embodied in the first blueprint the contract describes.

**Source.** `scaffold.py` on `main` at `06daead7` (2026-09-01): the expander block at lines
1335–1985 and stack #1's registration in `_STACKS` at 2101–2133. Each entry names the rule,
the evidence behind it, and who or what ruled it; where the tree records only a diagnostic
label (`pf-NN`) and no issue, the entry says so rather than inventing one. Plan:
`docs/plans/1-7-1-plan.md` §2.1.

### 1. Required request fields reject blank input at the model layer (#593)

**Rule.** `backend/models.py` defines `NonBlankStr = Annotated[str,
StringConstraints(strip_whitespace=True, min_length=1)]` and every required field of a
declared request shape — and of an entity-typed request model (entry 4) — is typed with it.
Whitespace is stripped before the length check, so `'  '` is as blank as `''`. The contract
pins `validation_error → 422` for it and the blank-input probe enforces it against the running
app, so the rule is scaffold-owned *and* probe-pinned.
**Evidence.** #593 (closed 2026-07-28); PR #634, commit `f2582766`. #874 (`84dbd29d`) later
made the rejects-blank expectation the criteria pack's call rather than a universal one.
**Ruled by.** The #593 decision, as merged in #634.

### 2. An optional or null-defaulted field freezes nullable (#1125)

**Rule.** In `_model_source`, a field with `default: null`, or an optional field with no
default, is emitted as `{ann} | None = None`; a non-null default as `{ann} = default`; a list
default as `Field(default_factory=list)`. The two absent-value spellings mean the same thing
and freeze the same way.
**Evidence.** The old branch emitted `str = None` for `default: null` — a non-nullable
annotation with a `None` default — and pydantic v2 rejected it (`string_type`) the moment a
route forwarded the request's `None` into the model: five of six 1.6.5 FastAPI+React rolls
paid it as a round-0 500 (`docs/plans/1-6-6-plan.md` §1). Held R1, 3 of 3 exercised, in the
1.6.6 set.
**Ruled by.** PR #1136 (2026-08-27), 1.6.6 item A.

### 3. Models are emitted in manifest order and never need forward references

**Rule.** `_py_type` maps `string/integer/number/boolean` to Python annotations, recurses
into `list[X]`, and passes an entity name through as the class name. Entities are emitted in
manifest order, referenced entities first, and `routes.py` imports exactly the classes it
references — so no forward references and no `model_rebuild`.
**Evidence.** `_py_type` and `_routes_source` docstrings; no issue behind it.
**Ruled by.** Design as written.

### 4. An entity named as an endpoint's `request:` gets a request model of its own (#1128)

**Rule.** For every entity in `manifest.entity_typed_requests()`, a class named by
`manifest.request_model_name(entity)` is emitted, shaped by the same resolver the contract's
probe bodies use (`manifest.request_body_fields`): required, non-generated, undefaulted fields
as `NonBlankStr`, every other non-generated field optional. The entity class itself requires
its generated `id` and could never accept the body the contract sends. One resolver, two
consumers — the route emitter and the contract generator cannot disagree about what
`request: X` means.
**Evidence.** 1.6.5 FastAPI+React roll 3 (`cyc_184b3a1d194e`): `request: Participant`
produced probes with `json: {}` against a route that required `name` — unsatisfiable by
construction (`docs/plans/1-6-6-plan.md` §1, item E).
**Ruled by.** PR #1141 (2026-08-27).

### 5. The error-seam import is wired into the frozen route stub

**Rule.** When the manifest declares an error contract, `routes.py` carries
`from .errors import ApiError` in its frozen import block. That makes `import_present(ApiError)`
a valid *interface* criterion — it must pass on the bare skeleton — and the fill calls the
already-imported symbol instead of guessing the module.
**Evidence.** SIP-0098 §6.2 (a criterion is validated against the bare skeleton and a reference
fill before it enters the contract).
**Ruled by.** SIP-0098, implemented.

### 6. The in-memory store is scaffold-owned and its import is wired like the error seam (#603)

**Rule.** `backend/store.py` is emitted — one `dict[str, Entity]` per declared entity, named
`<snake>_store`, keyed by the entity's id, plus `reset()` for test isolation — and the frozen
route stub imports every store name. The fill *uses* the store; it never defines a second one
and never edits the file.
**Evidence.** The manifest declared `persistence: in_memory` and the skeleton emitted nothing
that held the data, so the planner invented a module on every roll — outside every safety net:
nothing froze it, no contract criterion named it, its imports were guessed fresh each time.
pf-40 died there, on a `from models import …` missing the leading dot, so the app never
started and the behavioural probe could not run. Emitting the file makes the imports correct
by construction.
**Ruled by.** Commit `f07c688b` (#603, closed 2026-07-26).
**Open half.** "One store per declared entity" hands the qa author a table for shapes and
projections no correct app writes (#1087). The Next.js store already derives its tables from
`root_persisted_entities` (`scaffold.py:653`, 1.6.4); the stack-#1 half is the 1.7.1 rider and
lands *after* #1131, because it deliberately moves the reference contract's digests.

### 7. The router takes no prefix (pf-41)

**Rule.** `router = APIRouter()` with no `prefix=`. The frontend calls `/api/...` and the proxy
strips that prefix before the request reaches the app (entry 11), so the emitted paths are
already the full backend paths. Adding `prefix=` puts every route behind a second `/api` and
the app answers 404 to its own contract. The rule is stated in the emitted module's docstring
so the fill dev reads it in the file.
**Evidence.** pf-41 (diagnostic label; no issue number in the tree); commit `448d8c1b`
("the router takes no prefix — state it"). 1.6.6 item D (#1129) later made `endpoint_defined`
*resolve* an `APIRouter(prefix=…)` when a repair introduces one, so a correct repair is not
refused on the convention; the frozen stub still declares none.
**Ruled by.** The pf-41 fix, `448d8c1b`.

### 8. The success status is interface, pinned in the frozen decorator (pf-39, #772)

**Rule.** `status_code=` lives on the scaffold-owned route decorator, so the fill cannot drop
it. A *declared* `success_status` is pinned as declared; an *undeclared* one is pinned to
`derived_success_status(method, path)` — the same default the contract's deriver asserts —
because an omitted kwarg meant FastAPI's 200 against the deriver's 201, unwinnable. The
registration declares it: `skeleton_pins_success_status=True`.
**Evidence.** pf-39 (label only, no issue in the tree) for the first half; #772 (closed
2026-08-26) for the undeclared case. `tests/unit/capabilities/test_success_status_seam.py`
guards that the default has one home.
**Ruled by.** PR #1118 (#772).

### 9. One error envelope, rendered by two handlers, conformed in one file

**Rule.** `backend/errors.py` holds the code→status map generated from the manifest's error
contract. `ApiError(code, message)` raised from a route body and the `RequestValidationError`
handler both render exactly `{"error": {"code": …, "message": …}}`. An unknown code maps to
400; `validation_error` to its mapped status, else 422. FastAPI's default validation error
fires before any route body runs, so the registered handler is the only place it can be
conformed — the fill never hand-renders JSON and never edits this file.
**Evidence.** `_ERRORS_PY` docstring; the error contract is contract-owned (SIP-0098).
**Ruled by.** Design as written.

### 10. `main.py` is the invariant bootstrap; the requirements are ranges

**Rule.** CORS origins come from `CORS_ORIGINS` (comma-separated, default `*`); `/health` is the
deterministic readiness probe; `register_error_handlers(app)` before the router; business routes
only in `routes.py`; `title` is the project id. `backend/requirements.txt` pins
`fastapi>=0.115,<0.200`, `uvicorn[standard]>=0.30,<0.40`, `pydantic>=2.7,<3`.
**Evidence.** `_MAIN_PY` docstring. **No rationale is recorded for the version ranges** — they
are carried as data, not as a decision. (#637 is the class: images run locked deps the suite
never exercises.)
**Ruled by.** Design as written.

### 11. The `/api` proxy is dev-only; the backend's host and port are blueprint, not interface

**Rule.** `vite.config.js` proxies `/api` to `http://localhost:8000` and rewrites the prefix
away; production serves the built assets behind a reverse proxy that does the same strip.
**Evidence.** `_VITE_CONFIG` comment. The production half is verified by no criterion: #598
(the emitted nginx's default site shadows `/api/*`) is the 1.7.1 rider, reporting-only.
**Ruled by.** Design as written.

### 12. The frontend test harness is scaffold-owned, mirroring the backend conftest (#627, pf-53)

**Rule.** `vite.config.js` carries the `test:` key (jsdom, `setupFiles: ['src/test-setup.js']`)
— vitest reads it, `vite build` ignores it. `test-setup.js` imports
`@testing-library/jest-dom/vitest`: the `/vitest` entry registers matchers on vitest's own
`expect`; the bare entry assumes a *global* `expect` and crashes collection under vitest's
default `globals:false` (caught on the real toolchain, not in review). Harness wiring is a
workspace invariant, never a per-suite guess.
**Evidence.** pf-53: with no seeded harness, qa either refused to test or invented one that
could not run. #627 (closed 2026-07-28), PR #633 (`d1682c33`).
**Ruled by.** PR #633.

### 13. `afterEach(cleanup)` is registered by the harness, not by suites (#1127)

**Rule.** `test-setup.js` imports `afterEach` from vitest and `cleanup` from Testing Library
and registers `afterEach(cleanup)`. Testing Library auto-registers cleanup only when a
*global* `afterEach` exists; under `globals:false` there is none, so nothing unmounts between
tests and any suite that renders in more than one `it` fails "Found multiple elements".
**Evidence.** 1.6.5 FastAPI+React roll 1 (`docs/plans/1-6-6-plan.md` §1); held R2 6 of 6 in
the 1.6.6 set.
**Ruled by.** PR #1137 (2026-08-27), 1.6.6 item B.

### 14. The harness proof renders the app shell at a path no route claims

**Rule.** `frontend/src/__tests__/harness.test.jsx` renders `App` under a `MemoryRouter` at
`/__harness__` and asserts the `.app` container exists. It passes on the bare skeleton *and*
after any fill because no manifest route claims that path; it asserts wiring (vitest + jsdom +
Testing Library + router), never application behaviour; and it doubles as the in-workspace
example of the idiom — new suites go in new files beside it and render with `MemoryRouter`
the same way.
**Evidence.** The file's own header comment; #627 family.
**Ruled by.** PR #633.

### 15. `api.js` is interface wiring: the `/api` base path and envelope unwrapping

**Rule.** `apiFetch(path, options)` prefixes `/api`, sets the JSON content type, throws
`ApiError(code, message, status)` for any non-OK response — reading the pinned envelope when
present, falling back to `'error'` and the status text when not — and returns `null` on 204.
Views call `apiFetch('/path')`; they never construct URLs or unwrap errors themselves.
**Evidence.** `_API_JS` header comment. #668's scope note records the adjacent gap: a qa
suite mocking `apiFetch` with the wrong signature is not caught by anchors, and the client's
signature is deterministic and knowable.
**Ruled by.** Design as written.

### 16. App wiring is scaffold-owned; a route is added by amending the manifest

**Rule.** `App.jsx` imports one component per `frontend.routes` entry and renders a `<Route>`
for each inside `<div className="app">` (the anchor entry 14 asserts). It is never edited by
hand; a new route is a manifest amendment and a re-expansion.
**Evidence.** `_app_jsx`'s emitted comment.
**Ruled by.** Design as written.

### 17. The root DOM anchor is stamped on the view stub (#659)

**Rule.** The first `testids` entry of a route becomes `data-testid` on the stub's container,
so it exists from the bare skeleton onward and the fill inherits it in place. The full anchor
inventory rides as a comment in the stub because the stub has no other elements yet; the dev
prompt's testid-surface appendix carries the binding instruction.
**Evidence.** #659 (closed 2026-07-30), PR #662.
**Ruled by.** PR #662.
**Open half.** The qa side ignores the anchors prompts-only (fay-14, #668) — enforcement is the
1.7.1 pack, and #1123's routing signal reads the same inventory.

### 18. `conftest.py` at the workspace root is the single source of the import root (pf-26)

**Rule.** The frozen conftest puts the workspace root on `sys.path` so `import backend`
resolves regardless of the directory pytest runs from, and owns the app import behind the
`client` fixture. Suites fill bodies against `client`; they never author
`from <root>.main import app`.
**Evidence.** The pf-26 divergence — files under `backend/` but the qa test invented
`from app.main import app` (`docs/plans/SIP-0100-phase-0-mutation-path-inventory.md`). The
registration's `harness_entry_modules=("backend.main", "app.main", "main")` lists the three
roots suites have been seen to import.
**Ruled by.** Design as written; label only, no issue in the tree.

### 19. Store names are deterministic

**Rule.** `_snake` turns `RunEvent` into `run_event`, so the store is `run_event_store` and the
frozen stub's `from .store import …` always matches what `store.py` defines. Stable names are
what let the qa author and the fill name the same object.
**Evidence.** `_snake` docstring.
**Ruled by.** Design as written.

### 20. The registration is the seam's whole view of stack #1

**Rule.** The `_STACKS` entry declares: `qa_test_namespace=("backend/tests/",
"frontend/src/tests/")`; `harness_entry_modules` (entry 18); `check_stack="fastapi"`;
`criteria_pack="fullstack_fastapi_react"` — named for the stack today, but an indirection so a
later stack (a FastAPI+Vue stack wants the same backend criteria) can share one without
minting a fourth stack vocabulary; `error_seam=ERROR_SEAM_FASTAPI` (`scaffold.py:746`);
`probe_profile="fastapi_uvicorn"`; `skeleton_pins_success_status=True` (entry 8);
`dev_capability="fullstack_fastapi_react"`; and `app_invocation` (entry 21). After #1131 these
are the module's exports, registered exactly as `stack_nextjs_ts.py`'s are.
**Evidence.** The entry's comments; S1 (this SIP's consolidation of the per-stack surfaces).
**Ruled by.** This SIP's acceptance ruling, 2026-08-17.

### 21. What "invokes the application" means for a React SPA (#1126)

**Rule.** A suite reaches the app by rendering a real component or `App`
(`invocation_import` matches an import from `/App` or `/views/<Name>`). The network is a seam
*under* the component, so a global `fetch` stub or a `vi.mock` of the app's own `api.js` is
legitimate when a component is rendered and self-mocking when nothing is; mocking a view or
the `App` module itself is mocking the subject. The shared half of the vocabulary is
`app_invocation.py:26` (`NETWORK_SEAM_FETCH_STUB`); the definition is the stack's, not the
shared detector's.
**Evidence.** 1.6.5 FastAPI+React roll 1: the shared detector keyed "invokes the application"
on an `app/api/` import (the Next.js model) and discarded a green React suite
(`art_477b87f85956`). Held R3 6 of 6 in the 1.6.6 set. The owner's question of 2026-08-27 —
whether they must keep reminding us to stay stack-aware — is why #1131's structural guard
exists.
**Ruled by.** PR #1139 (2026-08-27), 1.6.6 item C.

### 22. The fill slots are the route bodies plus one component per declared route

**Rule.** `_fill_slots_fullstack_fastapi_react` returns `("backend/routes.py", *views)`, one
view per `frontend.routes` entry, deduplicated in order. Everything else the expander emits is
frozen, and `tests/unit/capabilities/test_scaffold_contract.py:94–106` asserts the reference
contract's `frozen:` digests cover every non-fill file by real hash.
**Evidence.** SIP-0104's ownership model (fill-only bodies, scaffold-owned surface).
**Ruled by.** Design as written.

### 23. Why stack #1 is still inline, and what the move must preserve (#822)

**Rule as recorded** (`scaffold.py:37–39`, `:2134–2137`): stack #2 was written as its own
module because a second inline expander would push the file past 2000 lines and interleave two
stacks' templates; extracting stack #1 to match was "deliberately not bundled — it would move
bytes the reference contract is pinned to."
**Status, 2026-09-01.** The file is 2,312 lines with one inline expander. #1131 is the
extraction, this register is its precondition, and the pin the comment names is the proof of
the move: `tests/fixtures/reference_contract/contract_v11_harness_cleanup_1127.yaml` holds the
sha256 of every frozen file, and `tests/unit/capabilities/test_contract_derivation_reference.py:128`
reproduces the contract byte-for-byte. A pure move leaves every digest unchanged;
`GENERATOR_VERSION` does not participate for stack #1 (it gates only the SIP-0104 emitter,
which this stack does not opt into — `scaffold.py:2157–2158`).
**Ruled by.** #822's S2 decision (2026-08-17) for the deferral; the 1.7.1 plan §2.1 for the move.

**Not harvested here, by design.** `envelope_example` is `ErrorSeam`'s (`scaffold.py:741`),
stack-neutral, and is not part of the move. `correction_runner.py` and the executor paths are
harvested before their own extractions (#1152), not in this pass.
