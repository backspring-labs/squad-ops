# 1.6.0 Authorship Plan — Author the Design, Prove It Was Won

**Established:** 2026-08-07 · **Opens:** now (v1.5.0 tagged 2026-08-06; SIP-0103 accepted
2026-08-07). Successor to the 1.5 line's discipline (`docs/plans/1-5-0-stabilization-plan.md`):
one PR per issue with `Closes`, premise re-verified against code at build time, targeted
verification per fix, live validation before merge for behavior-changing work, bump only
after a green confirmation shakedown. Sequencing, not dates — **substance gates the cut.**

Roadmap position: `docs/plans/post-1-4-roadmap-reconciliation.md` (the 1.6 row, unchanged)
and `docs/plans/post-1-5-roadmap-reconciliation.md` (1.7/1.8 rows, plus the design
intention this release owns).

**Revised 2026-08-07** after an owner review round (twelve points). They are folded in
where they act rather than appended as a list, because an appendix gets skimmed and a
gate criterion does not. What they changed, for traceability: M0 gained a divergence
taxonomy; M2 gained the unresolved-decision lifecycle; M5 gained a structured revision
reason; Guard 1 gained an **equivalence** half; S3 gained the exit criterion it was
missing; B1 gained time-to-resolution; and three sections are new — **the authoring
failure taxonomy**, **generalization debt after 1.6**, and **blueprint vocabulary
governance**. The review's sharpest finding was that S1 and M0 had proof strategies and
S3 had only a subjective one; the second sharpest was that three separate asks (revision
reason, memory baseline, window attribution) are one artifact used three ways.

**Revised again 2026-08-07 — M0's premise was wrong.** A pre-build verification pass
measured the actual artifacts and found that the contract deriver already exists and that
contract v9 is its exact output for manifest v4. **This plan therefore contradicts accepted
SIP-0103 §5b Correction 1 on measured evidence**; the SIP stands as the accepted design
commitment and the correction lives here. Consequences: M0 collapses from "build a deriver"
to a guard plus wiring; Track M gains an explicit **gates-before-author** build order; and
the `success_status` rider is upgraded from a schema-tidiness argument to a live latent
defect with a reproduction.

**Revised 2026-08-07 — verification cadence added.** The plan named gates but left *when a
cycle is worth running* to be improvised. V1–V8 below make it explicit, and two of them are
corrections rather than additions: the seeded-mode control observation **moves earlier**
(one shakedown at the cut is a claim, not a control — it needs a clean baseline to compare
against), and a **pre-registration viability run** is added, because pre-registering a
window for a capability that has never once succeeded wastes the window.

**Claim sweep 2026-08-09 — this plan, SIP-0103, and the issues filed this release were all
checked against source.** Prompted by a defect in this plan's own S4 section, which described a
failure mode it had never verified (now #818). Results:

| Artifact | Load-bearing code claims | Wrong | Direction |
|---|---|---|---|
| this plan | swept in full | **9** | 7 overstated what exists |
| SIP-0103 | swept in full | **4 wrong + 1 normative bullet silently dropped** | all 4 overstated |
| issues #762–#818 | premises spot-checked | **0 in bodies** (1 title imprecise; #812's premise was already corrected on the issue) | — |

**Where the defects concentrate, and why.** The issue bodies are clean because each was written
*during* build-time premise verification — this plan's own opening discipline. The plan and the
SIP are prose written *between* builds, where nothing forces a file open. And **4 of this plan's
9 defects were inherited verbatim from the SIP**: the plan restated the SIP's claim rather than
checking the code, which is the same failure one level up.

All of them shared one origin: **a claim about code sourced from a document *about* the code** —
the SIP's prose, this plan's earlier sections, an issue number from memory, a test file cited as
precedent. Not one was a misreading of source. Corrections are inline, marked
`Correction 2026-08-09`.

### The two rules adopted from it

1. **Cite or mark unverified.** A load-bearing claim about code behavior carries a citation, or
   says it is unverified. **Bounding claims carry it first** — *narrower*, *only*, *already*,
   *merely*, *does not affect* — because those stop further investigation; an alarming claim
   gets checked by whoever must act on it, a reassuring one closes the question and is not
   discovered wrong until the code runs.
   **Cite `file::symbol`, not a bare line number.** Line citations rot: this plan's
   `scaffold.py:901` for the `status_code=` emission now points at request-shape source — the
   real line is **985**. The claim was right and the citation was already wrong.
2. **Propagate a premise correction to every artifact that carries it.** Corrections currently
   stop at the issue or the PR. #796 disproved the SIP's "zero new plumbing"; #811 made §5c.6's
   "already threads reviewer notes" true; #783 found `decisions[]` was never parsed. **None of
   those reached this plan or the SIP** — this sweep is what found them, weeks later. The
   vehicle for this already exists below and has never been used: the **evidence matrix**.

## Character

An **even minor**: a feature release led by headline SIPs, which gate the version.
Hardening rides along freely.

One coherent claim: **the squad authors the interface design from the PRD, and the
release proves it was won rather than asserted.**

Two headlines, one per lane, per the dual-lane precedent set by 1.4:

| Lane | Headline | SIP |
|---|---|---|
| **M** (executor / handlers / framing surfaces) | **Squad-Authored Manifest** | **SIP-0103**, accepted 2026-08-07 with §5a/§5b/§5c in force |
| **S** (test-runner / build-check / agent-image / deploy-infra) | **Generalized Build Capability** | `SIP-Stack-Blueprint-Contract` — **deliberately still proposed**; promoted *mid-release* (see Track S) |

### The two protections this release needs

1.5's protective device was "feature-free, defined behaviorally." A feature release needs
different guards. Two, both testable:

> **Guard 1 — authored mode is a mode of manifest *provenance*, not a second pipeline.**
> Post-approval, an authored manifest enters `plan_artifact_refs` exactly as a seeded one
> does; expander, contract derivation, bind-mode plan validation, and every 1.4/1.5
> enforcement surface operate identically.
>
> **Verification at cut, in two halves — structure and output:**
>
> - **1a, no fork:** no execution path branches on authoring mode below the framing
>   workload. **The invariant holds today and is unpinned** (verified 2026-08-09):
>   `authors_interface_manifest` has exactly one production call site,
>   `cycles/task_plan.py:394`, inside framing. **The architecture test does not exist** —
>   `tests/unit/cycles/test_plan_gate_seams.py` is cited as the *precedent for the shape*
>   and contains no authoring-mode coverage. Owed before the cut.
> - **1b, equivalence:** feed the **reference manifest** through authored mode's
>   post-approval path; the expansion, the derived contract, and every verification
>   artifact must be **byte-identical** to seeded mode's. Same input, same output,
>   different provenance. **NOT BUILT** (verified 2026-08-09): no test asserts this.
>   `tests/unit/capabilities/test_contract_derivation_reference.py` (M0a) names Guard 1b
>   as a *dependent* — "Guard 1b **requires** the reference manifest to produce
>   byte-identical downstream artifacts" — not as itself. Owed before the cut.
>
> 1a alone is not sufficient and the distinction matters: a structural test proves nothing
> *branches*, not that the transformation is the same. 1b is what isolates a provenance
> change from a transformation defect, and it is cheap — the golden/replay machinery from
> 1.5 already does exactly this comparison.

> **Guard 2 — the measurement cannot be tuned by the thing it measures.** The authored-mode
> FAY window is pre-registered (N, PRD, deploy hash, scoring discipline) before the first
> roll, unfiltered, on a frozen deploy. The hand-authored reference manifest is excluded
> from squad inputs (contamination discipline). **Verification at cut:** the pre-registration
> record is committed before roll 1, and the window's rolls are enumerated in it.

Seeded mode remains permanently (§5a) as the control configuration and the
replay/regression referent — not a legacy path to be retired.

### Work classes (release-claim protection, carried from 1.5)

- **Release-defining** — without it, 1.6 has not delivered its claim. Exits the slate only
  by delivery, proof it was already satisfied, invalid premise, or an **owner-ratified
  scope change** that updates the release claim and the ROADMAP language.
- **Enabling** — required only because a release-defining item depends on it.
- **Capacity-bound** — may land while the release is open; **cannot delay the cut**.
  Unfinished capacity items roll to the 1.7 pool with a milestone update.

| Class | Contents |
|---|---|
| Release-defining | M1–M6 (SIP-0103's phases + the failure taxonomy) · S1–S3 + S5 (Generalized Build minimum + blueprint governance) · the authored-mode FAY window · **B1** (the memory baseline — see "Owed to 1.8") |
| Enabling | M0a/M0b (equivalence guard + derive-at-seed; the derivation *proof* is already banked) · SIP-0093 completion (#194 — the authoring pattern SIP-0103 extends; **#762 moved to the queue front**, where its preflight block starts paying immediately rather than waiting on the rest of 93's completion) · SIP-0102 steps 3–4 (clean-room verdicts; #376) |
| Queue front (pre-work) | #762 · #766 · #770 — see "Queue front" above; cheap, not claim-proving, but they tax every roll |
| Capacity-bound | #668 (both halves) · #772 (rides M0's schema change) · #761 (A4.1) · #598 structural half · SIP-0092 M3 · #733 Slice B · SIP-0091 · SIP-0090 Phase 2 · SIP-0102 steps 5–7 · agent-comms delivery guarantees · ops riders |

**Scope warning, recorded at plan time.** The ROADMAP's 1.6 row lists five riders
(SIP-0091, SIP-0090 P2, SIP-0102 steps 3–7, SIP-0093 completion, agent-comms) alongside
two headlines. That is more than one release has held before. This plan classifies only
the two riders that *serve the headline claim* as enabling and pushes the rest to
capacity — SIP-0091 and SIP-0090 Phase 2 in particular are platform work unrelated to
authorship, and carrying them as commitments would let the release be held hostage by
work that does not prove the claim. **Removing them from the release-defining set is a
scope reading, not a scope change**; if the owner wants either as a commitment, that is
an owner-ratified scope change with a ROADMAP language update.

---

## Queue front — pre-work hygiene *(ahead of M0a; owner-ruled 2026-08-07)*

Three small fixes land **before** the headline tracks open. They are not release-defining and
they do not prove the claim; they are here because 1.6's output is measured in **cycle rolls**,
and each of these taxes every roll the release will run.

| Item | What it costs per roll today | Why now rather than later |
|---|---|---|
| **#762** — bind mode with no `plan_authoring_contributors` is a guaranteed plan rejection | a wasted launch; **cost three rolls at shk-6** before diagnosis | 1.6 runs authoring experiments, gate probes, and an **unfiltered** FAY window, where a roll lost to misconfiguration is expensive in a way it is not during development |
| **#766** — LangFuse prompt linkage is inert under the filesystem asset provider, and logs a vendor `ERROR` per agent per cycle | triage noise on every cycle; prompt→generation linkage silently absent from every trace | 1.6 is a release spent reading traces and triaging authoring failures — this degrades the instrument we will lean on hardest |
| **#770** — `update_sip_status.py` fails opaquely on drafts without frontmatter | a blocked promotion at the worst moment | 1.6 promotes the Stack Blueprint SIP **mid-release** (S3), so this bites again inside this line |

**This is deliberately not a 1.5.1 patch line.** The population since the v1.5.0 cut is five
items (these three, plus #761 already homed to 1.6 as A4.1, plus #772), none urgent, three of
them papercuts — below the bar the 1.4 patch lines set at 5–7 real fixes each, and not worth a
deploy window, shakedown, bump, tag, and ledger close. 1.6 also opens with **pure offline work**
(M0a is a fixture test; M0b is seed-time wiring), so a freshly-verified deployed baseline buys
nothing yet. Same fixes, same order of arrival, none of the release overhead.

**Trigger that would change this ruling:** the population reaching five or six *real defects*
while 1.6's first deploy window is still far out, or any one of them turning live-breaking.

---

## Track M — Squad-Authored Manifest (SIP-0103)

### Remaining sequence — **staged, recorded 2026-08-09 after the S-lane seam run**

**Scope confirmed unchanged**: 1.6.0 cuts on both headlines, S1–S3 + S5 release-defining. A
split into a manifest-only 1.6.0 with the stack at 1.6.2 was considered and **declined by the
owner**; recorded so it is not relitigated, and because the version arithmetic it required —
a patch carrying a headline feature SIP — contradicts the even/odd convention.

Track M, B1, and the S lane's five seam fixes are complete. **Everything touching code must
land before pre-registration, because V7 requires a frozen deploy.** Progress is reported
against these stage/step labels.

#### Stage 1 — finish the S lane *(the bulk)*

| Step | Work | Gate |
|---|---|---|
| **1a** | **Hardwiring sweep.** Enumerate every stack-#1 assumption in deliverable-facing modules and classify each: already-a-seam · needs-parameterizing · belongs-in-the-FastAPI-pack · not-on-stack-2's-path | every hit classified; the "needs" class filed |
| **1b** | Parameterization PRs for the "needs" class | each: FastAPI byte-unmoved, regression green |
| **1c** | **The Next.js stack** — expander, criteria pack, probe profile, environment contract, completeness test across all four per-stack registries | `expand()` yields a tree; `emit_contract_dict` yields a satisfiable contract |
| **1d** | **Bend register** — `docs/plans/stack-2-bend-register.md`, written *during* 1c | zero unexplained bends (S3's exit criterion). **Landed**: six findings, of which **one is a true bend** — the rest split into a schema defect, a cleared check, a field with no home, and two disclosures |
| **1e** | **VS** — a Next.js cycle end to end | gates S3 |

**Why 1a leads, and why it is not a new invention.** It is the S lane's missing **M0a**: a
measurement of the surface before anything has to cross it, and the fourth application of the
rails-before-mechanism rule this plan already names three times (SIP-0101 Slice 1, SIP-0096's
inert core, M0a). S1's framing — *"an identifier indexing four module-level dicts plus one
function"* — was accurate about `scaffold.py` and was used as though it described the system;
four further per-stack surfaces (#818, #823, #828, #829) were then found one at a time, by
accident, each while fixing the last. 1a closes the set instead of discovering it.

**Decision owed at 1c:** does stack #2 build the same `group_run` PRD? Recommended **yes** —
it keeps VS comparable to V5 and reuses `audit_delivered_app.py`.

#### Stage 2 — close the S headline *(decomposed 2026-08-10)*

> **This stage was three lines of prose while Stages 1, 3 and 4 had lettered steps, and the
> imbalance was backwards on the merits:** Stage 2 is where the release's S claim is actually
> *made*. Stage 1 got five steps because work was happening in it; Stage 2 got a paragraph
> because none was. "S3" read like a single task and is not one.

| Step | Work | Gate |
|---|---|---|
| **2a** | **The stack inventory.** One place answering "which stacks exist and what does each declare", with today's six registries as members | S3 has a subject rather than a scavenger hunt |
| **2b** | Draft the blueprint schema against **both** stacks | every field traced to a real declaration in each |
| **2c** | **Falsification pass** — remove or corrupt each field, confirm something breaks in at least one stack | a field whose removal breaks nothing is decorative and is deleted *before* the schema freezes, not after it accretes meaning |
| **2d** | **Bend register review** (`docs/plans/stack-2-bend-register.md`) | **zero unexplained bends** — one true bend to argue, plus a schema defect and a field with no home |
| **2e** | The two recorded disclosures + the `fullstack_fastapi_react` / `fastapi` vocabulary reconciliation S3 still owes | stated at promotion, never implied away |
| **2f** | **S5** — the admission rule recorded | a new blueprint field must be demonstrated on two stacks |
| **2g** | Promote the Stack Blueprint SIP | its acceptance gate — a second real stack — is met |

**Why 2a is here and not folded into #838.** #838 fixes a broken cycle; 2a is schema
preparation. Bundling them would hold a blocking fix hostage to a design question. But 2a is
what #838 exposed: **six per-stack registries, of which three are reached by an explicit field
on `ScaffoldStack` (`criteria_pack`, `probe_profile`, `dev_capability`) and two by naming
convention alone (`sandbox._CONTRACTS`, `BUILD_PROFILES`) — and both convention-bound ones are
where it broke.** Which registries got a pointer is not a design distinction; it is the order
the bugs arrived in.

**2c is the step most likely to bite**, and the raw material already exists. Measured
2026-08-10, two `ScaffoldStack` fields are populated by exactly one stack:

| field | `fullstack_fastapi_react` | `nextjs_ts` |
|---|---|---|
| `harness_entry_modules` | `('backend.main', 'app.main', 'main')` | `()` |
| `check_stack` | `fastapi` | `""` |

Under 2c's own rule each is either **a declared optional capability with its reason recorded**,
or **a FastAPI assumption wearing a general name**. Both have a defensible answer today —
Node module resolution has no test/app import boundary, and the typed-check evaluators are
Python implementations never verified against stack #2 — but "defensible" is what the
falsification pass exists to demand in writing rather than accept by assertion. Not answerable
until 2b exists.

#### Stage 3 — release-wide *(runs in parallel with Stage 1)*

| Step | Work |
|---|---|
| **3a** | **Guard 1a** architecture test — nothing branches on authoring mode below framing. The invariant holds today at one call site (`task_plan.py`); nothing pins it |
| **3b** | **Guard 1b** — reference manifest through authored mode, byte-identical downstream artifacts |
| **3c** | **Rider #376** (SIP-0102 3–4): the repair path discards final-state verification. Enabling — V5 took 2 corrections and the verdict field inherits the gap |
| **3d** | **#194** → capacity unless it fires |
| **3e** | Capacity roll → 1.7 pool with a milestone update |

#### Stage 4 — the measurement

| Step | Work | Note |
|---|---|---|
| **4a** | Decide the **worked example** — non-CRUD or keep | must precede V6; it changes what V6 measures |
| **4b** | **V6** viability run | gates V7 |
| **4c** | Decide **contract size per roll** in the window record | must precede pre-registration |
| **4d** | Pre-registration committed (N, PRD, deploy hash, scoring) → **freeze** | Guard 2 |
| **4e** | **V7** — the FAY window, unfiltered, **fix nothing until it closes** | the evidence |
| **4f** | **V8** confirmation shakedown | green |
| **4g** | Cut | — |

**The two open decisions, restated with their evidence.** 4a: a CRUD-shaped worked example
measured on a CRUD product flatters the convergence result — V4 roll 2's REST spine was
*patterned* from the example while its domain surface was derived. 4c: verification depth
varies with an authoring judgment (roll 1's 400-for-conflict bought 4 probes where roll 2's
409 bought 5; 29 executed checks on roll 2 against 57 on V5, same PRD), so without it a green
roll that shrank its own exam is indistinguishable from one that passed a hard one.

### Build order — **gates before author**

The M-numbers below are section identities, not a sequence. The build order is:

> **queue front (#762, #766, #770) → M0a → M0b → M3 → M2 → M6 → M1 → M4 → M5**

M0's collapse (below) made the original M1-first ordering wrong. The reasoning, which is
the same rails-before-mechanism rule this repo has now applied three times (SIP-0101
Slice 1, SIP-0096's inert core, and M0a here):

- **The gates are deterministic and testable against hand-made adversarial manifests
  today**, with no authoring stage, no LLM, and no deploy. The `success_status` defaults
  trap documented under M0 is a designed-failure probe that can be written this week.
- **M1 is the only piece whose output is a lottery.** Landing it last means it arrives
  against gates already proven to reject the classes we know about — so a failed authored
  manifest is attributable to the author rather than ambiguous between author and
  unproven gate.
- Ordering M1 first inverts that: every early gate defect would surface *as* an authoring
  failure, and the window's attribution (M6) would inherit the confusion.

M4 (the review path) follows M1 because there is nothing to ask about until something is
authored; M5 (provenance) is last because it stamps a pipeline whose shape is settled by
then.

### M0. Contract derivation — **premise corrected 2026-08-07; the proof is already banked**

> **PREMISE CORRECTION — this plan contradicts accepted SIP-0103 §5b Correction 1, on
> measured evidence.** The SIP states: *"contract v9 is a hand-authored artifact … no
> `derive_contract(manifest)` exists anywhere in the pipeline."* **Both halves are false.**
> The SIP stays as accepted (it is a design commitment on main, not a living document);
> the correction lives here, where the work is planned.

The deriver exists and always did: `squadops.capabilities.scaffold_contract.emit_contract_dict()`,
shipped as SIP-0098 phase 98.2 — *"the criteria are derived deterministically from the same
interface manifest the skeleton is expanded from, so verification is a fixed property of the
scaffold rather than a per-roll LLM lottery."*

Run against the artifacts themselves on 2026-08-07:

```
emit_contract_dict(InterfaceManifest.from_yaml(art_8becd104e9fc))  ==  yaml(art_4f368ea08799)
→ True   (exact dict equality; all six sections identical; 4 fill_files, 5 probes)
```

**Contract v9 is a pinned emission of manifest v4, not a hand-authored artifact.** M0's
exit criterion as originally written — reproduce v9 from v4, byte-equivalent or every diff
classified — is therefore **met with zero diffs, before any work started.**

#### What is actually missing: wiring, not intelligence

Bind mode loads the pinned contract from `contract_ref` *by design* — `handlers/cycle/base.py`
states it outright: *"bind mode loads the pinned contract from `contract_ref` instead of
regenerating it, so a criterion added to the expander would not appear until a re-seed."*
That is correct for seeded mode and **impossible for authored mode**, where no pinned
artifact exists yet because the manifest was only just written.

M0 therefore collapses to two small, deterministic pieces:

- **M0a — pin the equivalence as a standing guard.** A test over committed fixtures asserting
  `emit_contract_dict(v4) == v9`. This converts a one-off measurement into an invariant, so
  the deriver can never silently drift away from the contract the 1.4 evidence was measured
  against. Cheap, and the entire track now rests on it.
- **M0b — derive-at-seed.** When a cycle supplies a manifest and no `contract_ref`, derive
  the contract at seed time and pin it, so authored mode gets the same frozen-by-hash
  guarantee seeded mode has. No LLM, no new intelligence, fully testable offline.

The divergence taxonomy below is **retained deliberately**, not deleted as spent. It now
governs M0b (an authored manifest's derived contract vs what the scaffold actually emits)
and any future change to the deriver — the classes are what keep "we changed the contract"
from becoming an unexamined act.

**Every accepted divergence is classified, not merely justified.** "Justified" degrades
into a rubber stamp under schedule pressure; a required class does not. The taxonomy —
and note that v9 is the *incumbent*, not automatically the gold standard:

| Class | Meaning | Consequence |
|---|---|---|
| `normalization` | same semantics, different serialization (ordering, whitespace, defaulted field made explicit) | accept; pin the normal form so it never drifts again |
| `ambiguity_removal` | v9 left something implicit that derivation must make explicit | accept; record the resolution as the new reference |
| `derivation_defect` | the deriver is wrong | **fix the deriver** — never the record |
| `reference_defect` | the pinned reference is wrong and a deriver change found it | accept the new form **and** see below |
| `underivable` | the reference encodes intent the manifest cannot express | the manifest schema gap is named; the check moves to authored residue |

**The `reference_defect` class carries a retrospective obligation.** The 1.4 FAY window
(6/6, five consecutive) was measured *against v9*. A defect there is not merely a contract
note — it qualifies a published number, and the plan must record the qualification in the
same PR rather than absorbing it silently. This is unlikely and cheap to state; discovering
it later without a stated policy is neither.

Scope split by verified derivability (§5b):

| Layer | Disposition |
|---|---|
| Interface — `endpoint_defined`, `import_present`/`module_imports` from the skeleton | **derived today.** *Corrected 2026-08-09 — the error is inherited from SIP-0103 §5b Correction 1 verbatim, and the SIP carries it too:* `endpoint_defined` is emitted **once**, on the routes slot only — not per fill slot (measured: 1 occurrence across 4 `fill_files`). **`field_present` is not emitted at all**; the deriver's entire emitted vocabulary is `command_exit_zero`, `endpoint_defined`, `frontend_build`, `frontend_compiles`, `import_present`, `module_imports`, `tests_pass`. Deriving per-entity field checks from `entities` remains *possible* and unbuilt |
| Probe skeletons — method/path/status from declared `errors` + `success_status` | **largely derivable**; probe *payloads* and `json_has` values carry product intent → derive the shape, author the values in the same authoring stage |
| Suite/coverage expectations | **authored residue** — stays with the authoring stage |

Rider: **`success_status` becomes required-per-endpoint** (§5b Correction 2). Manifest schema
change ⇒ **manifest v5**; the version bump is expected here and nowhere else in the track.

**The empirical case is stronger than the SIP's, and it is a live latent defect.** Measured
2026-08-07: `success_status` is declared on **1 of 5** endpoints in v4. Where it is absent,
two components default *differently*:

- the deriver asserts a status — `ep.success_status or 201` for POST-to-collection
  (`scaffold_contract.py:267`), `or 200` for child routes (line 327);
- the scaffold omits `status_code=` from the route decorator entirely when it is undeclared
  (`scaffold.py:901`), so **FastAPI's own default (200) applies.**

For a POST-to-collection with no declared status, the contract asserts **201** against a
scaffold that emits **200** — an unwinnable contract, authored innocently. Today this is
masked *only* because the single endpoint reaching that branch (`POST /runs`) happens to
declare 201 explicitly. Nothing enforces that coincidence.

Two consequences:

1. This is the **first designed-failure probe for the M3 winnability gate**, and it is
   available immediately — a hand-made manifest omitting `success_status` on a POST-to-
   collection must be rejected as unwinnable before it ever reaches implementation.
2. It is a defect in seeded mode too, not only an authored-mode hazard: any future
   hand-authored manifest hits it. **Filed as #772** (2026-08-07), homed to 1.6 with the
   preferred resolution recorded as *fix by deletion*: making `success_status` required
   makes both defaults unreachable, so the underlying REST-semantics question — is the
   deriver presumptuous, or the scaffold under-specified? — is dissolved rather than
   answered. If the required-field change ever leaves scope, #772 says explicitly that the
   question comes back live and needs an owner ruling.

### M1. Authoring stage

A manifest-authoring task family opens the framing workload in authored mode. Inputs:
the PRD and the Stack Blueprint's closed vocabulary. Output: `interface_manifest.yaml`.

**The enumerated input contract is normative (§5c.1)** — the PRD, the blueprint's closed
vocabulary, in-cycle rejection context (#669), **and nothing else**. The reference manifest
is excluded. A declared extension point marks where cross-cycle memory recalls plug in
later, *with provenance*. Undeclared inputs are contamination by definition; declared ones
are capability.

Decomposition (single merger-authored vs multi-role proposers) is §6's open question 1,
resolved at the Gate-1 design review — informed by §5a's recommendation: **single author at
design time, multi-reviewer**, because a design is a coherence artifact and merging two
independently-authored designs produces neither author's coherence.

Budget seams already exist and are **not** reinvented (§5b Q4): the authoring stage
inherits `manifest_max_attempts` as its in-stage revision budget; gate rejections spend
`framing_max_rerolls`.

#### As built — #791, resolutions and three premise corrections

**§6 open question 1 is resolved: single author, and the reviewers are the gates.** §5a's
recommendation, with one amendment measured against main. The two things §5a assigns a QA
reviewer — *every view declares its anchors, every endpoint a probe-able status contract* —
are **already proven mechanically** by M3's `testid_coverage` and `status_declared`. Adding
an LLM reviewer on top would put judgment where determinism already holds, which is the
§5c.2 / #464 style-lottery class the plan-validation family exists to reject. So: one author
(dev, at a dedicated stage after `development.design_plan`), reviewed by M3's proofs and
M4's human gate, with `qa.define_test_strategy` reading the manifest downstream as a free
non-gating lane. Multi-role proposers remain the recorded fallback — that migration
direction has one; the reverse does not.

Three things the plan assumed, corrected against `d4c3f9a2`:

1. **Authoring already existed, in the wrong place and ungated.** SIP-0099 99.2 asked the
   dev *proposer* to emit the manifest as a second fenced block beside its plan tasks, and
   the merger re-emitted it (dev preferred, qa fallback). M1 is therefore a **relocation**,
   and the old path is deleted rather than left beside the new one.
2. **A framing-authored manifest never reached the implementation run.** The framing→
   implementation forwarding filtered promoted artifacts to
   `{document, control_implementation_plan}`, dropping `interface_manifest` — so the
   manifest was stored, gate-validated, promoted, and then silently not carried, leaving
   the implementation unscaffolded. Dormant because every cycle since ran bind mode, where
   the manifest rides `plan_artifact_refs` from creation (#496). Authored mode could not
   have worked without this fix.

   > **This disproves SIP-0103 §5a's foundation inventory, which the 2026-08-09 sweep flags as
   > the SIP's highest-consequence wrong claim:** *"an authored manifest propagates into the
   > entire verification stack with **zero new plumbing**."* The opposite was true — authored
   > mode was **dead on arrival** until #796, and the plumbing gap was invisible precisely
   > because every cycle since SIP-0099 99.2 ran bind mode. A bounding claim ("zero"), written
   > from an inventory of what existed rather than from a trace of the path, and load-bearing:
   > it is the sentence that made authored mode look like a provenance change rather than a
   > wiring project.
3. **The taught schema would have failed the new gates.** The authoring asset predated M2
   and M3 and showed no `source_prd`, `decisions[]`, `success_status` or `testids` — the
   #629 pattern, where the system holds the rule and the author is shown only the
   rejection. Closed the way #686 closed it for plans: a `manifest_authoring_rules`
   classification table keyed to the `PROOF_*` constants, bound by test to the managed
   asset, with derivation-owned proofs required to be **absent** so no author is taught to
   work around a defect that is ours.

M2/M3/M6 were pure modules with no callers until here; M1 wires all three — the gates as
the revision loop's in-stage verdict and as the framing gate's rejection, the taxonomy as
the outcome record. Wiring them surfaced one defect in M6's composition: both gates parse
independently, so an unparseable manifest was reported twice and counted as
`authoring_defect: 2` in a baseline measuring one. Fixed at the composition.

### M2. Schema gate (deterministic) — partially built

`InterfaceManifest.lint()` already rejects the parses-but-unexpandable class (no endpoints,
undeclared request shapes, route-without-view, unknown stack) at the SIP-0099 net. M2 is
the delta: required sections present, and the **decision-granularity** citation discipline
(`source_prd` + `decisions[].warrant`) — *not* per-entry citation, which §5b Correction 3
rules would bloat authoring for little gate value.

Two schema extensions land here:
- **`decisions[]` gains an `unresolved: true` form** (§5c.10) — the author surfaces a design
  question it declines to resolve rather than silently defaulting; any unresolved-critical
  entry lands in the HITL gate note as a question.
- **Every judgment call the schema cannot express mechanically must land in `decisions[]`
  with a PRD warrant** (§5c.4) — pagination, authz boundaries, idempotency, caching. Judgment
  becomes explicit, reviewable at the gate, and auditable later.

#### The lifecycle of an unresolved decision *(otherwise it propagates silently)*

Three rules, so an unresolved entry can never become an implementation surprise:

1. **Preserved, never consumed.** An unresolved entry stays in the manifest as part of the
   design record and its provenance. Approval does **not** silently drop it.
2. **Approval does not resolve it.** The operator approving a manifest approves the design
   *including its stated open questions*; resolution is a separate act that produces a new
   manifest version with a new hash (M5's immutability rule). Nothing may read "approved"
   as "all questions answered."
3. **Derivation may not depend on one.** If a derived check would depend on an unresolved
   decision, that is a **winnability failure (M3), not an approval question** — the gate
   rejects before a human ever sees it.

Rule 3 is the load-bearing one: it keeps the invariant in deterministic machinery rather
than in reviewer discipline, which is the difference between a rule and a hope.

#### The judgment ratchet *(the surface must shrink, not grow)*

§5c.4 defines *what* may be judgment — anything the schema cannot express mechanically.
What it does not do is create any pressure for that set to get smaller, so an
implementation can satisfy every deterministic gate while quietly relocating more and
more engineering reasoning into `decisions[]`.

The ratchet: **`decisions[] entries are counted by class in the window diagnostics, and a
recurring judgment class is a schema-gap signal**, not a standing accommodation. A class
that appears in most authored manifests is a candidate for promotion to a mechanical
field — adjudicated by the blueprint governance rule below, since promotion is a
blueprint-version change rather than silent drift.

### M3. Winnability gate (deterministic — the new validator family)

The authored manifest must be provably winnable before anything downstream spends on it.
Phase-1 depth is **deterministic closed-surface proofs only** (§5b Q2), each buildable from
an existing seam:

| Proof | Seam |
|---|---|
| `lint()` passes | exists (SIP-0099) |
| expander dry-run — `expand()` succeeds, `fill_slot_paths()` non-empty, paths under scaffold roots | exists, pure and cheap (the pf-26 wrong-root class, one level up) |
| derived-contract dry-run — every derived check passes `CHECK_SPECS` validation, #671 module-existence holds against the implied skeleton, no check dead-on-arrival per `is_check_applicable` | **depends on M0** |
| testid coverage — every route declares ≥ 1 testid | schema field exists |
| status completeness — **a collection POST** declares `success_status` | as built (#781) |

> **Correction 2026-08-09 — the status proof is narrower than this table originally said.**
> It read "per-endpoint `success_status`", which is the schema rider's shape, not the gate's.
> `cycles/manifest_gates.py::_status_findings` is *"deliberately narrow"* by its own
> docstring: only a **collection POST** (no `{` in the path) must declare a status. Child-action
> POSTs default to 200 on both sides and agree; GETs derive no status probe. Requiring it
> everywhere **would reject the reference manifest**, which declares it on 1 of 5 endpoints.
> This delivers #772's protection without waiting on manifest v5 — which is why the v5 bump
> is not in 1.6.

Deferred: semantic PRD coverage. The `decisions[].warrant` discipline plus M4's question path
carry that judgment in Phase 1; a mechanical coverage proof is not a Phase-1 blocker.

> **Omission found by the 2026-08-09 sweep — a normative SIP bullet this table dropped without
> recording it.** SIP-0103 §3.3's **third** bullet is *"interface self-consistency: endpoints/
> params/testids the manifest promises are mutually coherent … (the #565 `{id}`/`{run_id}`
> naming-prior class becomes an authoring-time check instead of a live-roll loss)."* M3 as built
> has no such proof — `cycles/manifest_gates.py` declares `parses`, `lint`, `expands`,
> `contract_derives`, `checks_live`, `testid_coverage`, `status_declared` (plus M2's `source_prd`
> and `decision_record`). Nothing checks path-parameter naming coherence.
>
> This is **narrower than the "semantic PRD coverage" the table deliberately defers** — it is a
> closed-surface proof over the manifest's own declarations, which is exactly the Phase-1 class.
> It was not deferred by a decision; it was lost between the SIP and this table.
>
> **DEFERRED — owner ruling 2026-08-09, filed as #820 with a named trigger.** §3.3's third
> bullet does not ship in 1.6. The disclosure obligation is discharged here and on the issue, so
> a §3.3 reader is not left inferring a proof that does not exist.

#### Why deferring interface self-consistency is defensible *(and where it stops being so)*

**What M3 does prove:** `PROOF_TESTID_COVERAGE` — every frontend route declares ≥ 1 testid
(`cycles/manifest_gates.py::_testid_findings`). Coverage, not coherence.

**What stays unproven:** that a path parameter for the same logical entity is named consistently
across endpoints; that declared testids correspond to anything the endpoints or views promise;
endpoint/param mutual coherence generally.

**The argument for deferring, which is stronger than "it hasn't fired":**

- The motivating instance was **PR #565 — *"rename group_run path param `{id}` → `{run_id}`"*** — a
  fix applied to the **hand-authored** reference manifest. The class fires when a *human* declares
  a name that fights the model's prior, and the implementation then writes the prior instead of
  the declaration.
- **Authored mode structurally shrinks that class**: when the squad authors the manifest, the
  declaration and the implementation are generated from the same prior, so they agree by
  construction rather than by discipline. V4 rolls 1 and 2 and V5 each derived `{run_id}`
  unprompted from behavioral prose — three rolls, zero occurrences.
- **It does not eliminate it.** Nothing forces cross-endpoint consistency, so an authored manifest
  could still declare `{id}` on one endpoint and `{run_id}` on another. The class is narrowed,
  not closed — which is exactly why this is a deferral with a trigger rather than a deletion.

**Named triggers that bring it back** (any one):

1. An authored manifest naming the same logical entity's path parameter two ways across endpoints.
2. Any live-roll loss or A4 `plan_defect` whose root cause names a manifest naming incoherence.
3. **The second stack introducing a second path-parameter convention.** Express-style `:runId`
   against the manifest's `{run_id}` means a translation seam that does not exist today, and a
   mismatch there is this same failure wearing different clothes. *Marked as a prediction, not a
   verified claim — the Node expander does not exist yet* (this plan's own citation rule: a claim
   about code that has not been written is labelled as such).

### M4. Manifest review — **question-gated, not review-gated** *(scope narrowed 2026-08-08)*

> **DIVERGENCE FROM ACCEPTED SIP-0103 §3.4, on owner ruling and V4 evidence.** §3.4 specifies
> *"a named gate between manifest acceptance and implementation: the operator approves the
> authored design the way `progress_plan_review` approves the plan."* **Every authored
> manifest is no longer reviewed.** The SIP stays as accepted — it is a design commitment on
> main, not a living document — and the correction lives here, the same treatment M0's
> premise correction got.

**What V4 measured.** V4 roll 2's framing bundle went through `progress_plan_review` and a
human approved it. The approval note discussed fill slots and criteria counts — facts the
deterministic gates had already proven. Meanwhile the manifest carried one genuinely
unresolved question (`expansion-gating`: *the PRD requires expansion only after core
stability but defines no checkpoint*) and **nothing surfaced it to the reviewer.** The design
was then implemented with 15/15 criteria verified, zero corrections, and a delivered app that
installs, builds, boots and answers every probe.

So the mandatory review contributed nothing, and the one thing a human uniquely held went
unasked. **A gate that gets rubber-stamped is worse than no gate: it manufactures the
appearance of review**, and a later reader cannot tell a considered approval from a reflex.

**The inversion.** The trigger becomes the *design's own question*, not the pipeline's
schedule:

| | shape |
|---|---|
| **Default** | **No gate.** The deterministic gates (M2 schema, M3 winnability) approve the design and the cycle proceeds. |
| **Blocks** | **Only an unresolved-critical decision** — the author declaring the PRD does not determine something and declining to guess. The gate note is the *question*, and answering it is the whole interaction. |
| **Everything else** | Readable after the fact from the artifact; never blocking. |

This is a narrowing of §3.4 rather than a contradiction: §5c.10 already has an
unresolved-critical entry *"land in the HITL gate note as a question rather than silently
defaulting."* M4 promotes that from a passenger on a mandatory review to the trigger itself.

**Iterative review, when it does fire** (§5c.6, unchanged): `RETURNED_FOR_REVISION` is a live
third state (#466) and rejection-context injection (#669) threads reviewer notes into the next
attempt. *(The word here was originally "already," which was false when written: V5 found that
`RETURNED_FOR_REVISION` stopped the sequence and needed a manual retry run. **#811 made it
true** — the revision now re-executes framing from `development.design_plan` with the notes and
the prior manifest, replaying the prefix it does not invalidate.)* Revision returns the manifest **with the prior artifact and the reviewer's
notes as authoring context — revise, don't re-roll** (the fay-6 new-dice lesson), spending
`manifest_max_attempts`. **Partial approval is deliberately not introduced**: approval stays
whole-artifact because the contract derives from the whole. Machinery is still nil — §5b
Correction 4 holds; a `task_flow_policy.gates` entry keyed on `after_task_types` plus CRP
defaults, now with a *conditional* firing rule.

#### What replaces the review as the design-quality signal

Removing a gate removes an observation, and design quality that nobody looks at drifts
unobserved. **FAY yield does not cover this**: V4 roll 2 flattened the reference's typed
`Participant` entity into an untyped list and still went green — a design regression yield is
structurally blind to.

The answer is **sampling, not gating**, carried by the four diagnostics §5c.7 requires:
structural diff against the human reference, revision/attempt counts, the gate-rejection
taxonomy (M6), and manifest size/surface counts. Those move when design quality moves,
without anyone reading a manifest. A design gets read when a number looks wrong — an operator
choice, not a pipeline stall.

> **Correction 2026-08-09 — this paragraph originally read "diagnostics §5c.7 *already
> requires*", which a reader takes as "already has". Two of the four had never been built.**
> Revision/attempt counts (M5, #803) and the gate-rejection taxonomy (M6, #785) existed; the
> structural diff and the size/surface counts did not. So the argument for removing a human
> gate was half-funded from the moment it was made — the same shape as the seeded control's
> retirement resting on two unbuilt guards, and the second instance of it in this document.
>
> Now built: `cycles/manifest_diagnostics.py` plus `scripts/dev/emit_manifest_diagnostics.py`.
> **Operator-run, never a pipeline stage** — the reference manifest is excluded from squad
> inputs (§4/§5c.1), so a diff computed inside a cycle would make it an input; an architecture
> test pins that nothing under `src/squadops` or `adapters/` can reach the module.
>
> It reproduces the case it was built for on the first run: against V4 roll 2 it reports
> `entities → only in reference: Participant` — the typed entity flattened into an untyped list
> by a roll that then went green on every probe. It also surfaces `/runs/:run_id` vs the
> reference's `/runs/:id`, which is #820's deferred naming-prior class showing up as a visible
> non-gating signal rather than a silence.

**The freeze moment moved, and §5a's wording no longer matches the code.** §5a's third
containment bound says the manifest hash-freezes and the contract derives *"the instant the
HITL gate approves."* Since #796 it derives at **authoring acceptance, mid-framing**, because
the plan authors need it to bind — without that, V4 roll 1's plan hit zero of nine fill slots.
Approval therefore gates whether *implementation proceeds*, not whether the contract exists;
a revision produces a new manifest and a new derived contract. Post-freeze determinism is
unchanged, which is what the bound was actually protecting.

### M5. Provenance + freeze

A `provenance` block on the manifest itself (§5c.5): authored vs seeded mode, authoring task
and cycle, attempt count, and classified revisions. Immutability is mechanical — the gate
approves *bytes* and `content_hash` freezes them.

> **Correction 2026-08-09 — the operator-edit record is not built, and neither is the path.**
> As built (#803), `capabilities/scaffold.py::Provenance` carries exactly `mode`, `cycle_id`,
> `task_id`, `attempts`, `revisions`. There is **no operator-edit field**, and no operator-edit
> code path exists anywhere to record. The immutability rule ("an operator edit is a new
> manifest version with a new hash") therefore describes an act the system cannot currently
> perform — it is a design commitment for whenever that path is built, not a live guarantee. Replay, regression, and memory read provenance from the artifact rather than from
cycle-history archaeology.

**Provenance records *why* it changed, not only where it came from.** Attempt count alone
says a manifest took three tries; it does not say whether those tries were a schema failure,
a winnability rejection, reviewer feedback, or the author's own refinement — and every
downstream consumer (replay comparison, the window's attribution, 1.8's memory) wants
exactly that distinction. Each revision therefore carries a **structured reason drawn from
the shared authoring failure taxonomy below** — one vocabulary, not a free-text field that
each reader parses differently.

**Manifest evolution stays out** (§5c.8). The freeze is what makes verdicts attributable:
every check, probe, and repair measures against one hash, and a mid-cycle moving target is
the #494 stale-binding class systemically. The named trigger for revisiting: a measured rate
of A4 `plan_defect` terminations whose root cause names an authoring-unknowable constraint.

### M6. The authoring failure taxonomy — **one artifact, three consumers**

Three separate needs in this plan turn out to be the same record, and building it three
times would recreate exactly the taxonomy-reconciliation problem the 1.8 reconciliation
exists to prevent (intention 2 — one failure-class vocabulary, not parallel ones):

| Consumer | Needs |
|---|---|
| M5 provenance | why each revision happened |
| B1 baseline | rejection classes and their recurrence, per cycle |
| the FAY window | which subsystem a failure is attributable to |

**Build it once, in M6, before the window opens.** Without it, the window's output
collapses into a single "manifest rejected" bucket, and a bucket cannot tell us whether
authored mode is limited by the *author*, the *schema*, the *blueprint*, or the *deriver* —
which is the entire question the release exists to answer.

The taxonomy keys off the vocabulary that already exists — `failure_ownership` (#730's
registry attrs), locus classification (#568), `FailureEvidenceCategory` — extended with
the authoring-specific dimension:

| Class | Meaning | Who fixes it |
|---|---|---|
| `authoring_defect` | the manifest is wrong; the schema, blueprint, and deriver are fine | the author (retry with rejection context is the right response) |
| `schema_gap` | the manifest could not express something the design needs | schema change ⇒ blueprint version |
| `blueprint_limitation` | the stack's closed vocabulary cannot express the design | blueprint governance (below) |
| `derivation_defect` | authoring was sound; the deriver mishandled it | M0's code |
| `prd_insufficiency` | the PRD does not determine the answer | `decisions[]`, `unresolved: true`, the HITL gate |

The last class is the one that most needs to exist: without it, a PRD that under-specifies
looks identical to a squad that cannot design — and those have opposite remedies.

---

## Track S — Generalized Build Capability

The S headline's SIP prescribes its own sequencing, and it does **not** start with acceptance.

### S1. Consolidate the five per-stack facts — no SIP required

Today "a stack" is an identifier indexing four module-level dicts plus one function with the
answer written inline. One of them — `fill_slot_paths` — hardcodes the FastAPI slot map behind
a guard that only checks whether the stack is *registered*, so a second stack would silently
inherit `backend/routes.py` as a fill slot and nothing would object.

Consolidate into one object carrying **today's fields**. Pure refactor, exact test:
`expand()` output byte-identical, contract `content_hash` and `interface_manifest_hash`
unmoved, both emission gates 6/6, regression unchanged. This removes the silent-omission
failure mode immediately and prejudges nothing.

### S2. Stack #2 — **AMENDED: Next.js + TypeScript** *(owner ruling 2026-08-09, superseding 2026-08-07)*

> **The 2026-08-07 ruling below — an Express-or-Fastify API with a typed React frontend — is
> superseded.** Its reasoning is retained unedited because the *criterion* still governs and
> the rejected alternatives still stand; only the selected instance changed. The trigger was
> the owner's observation that the original choice **barely changes the frontend at all**.

**Why the original selection was too narrow.** Express + typed React holds React, the component
model, `frontend/`, npm, vite, and the bundler-as-only-check all constant. Measured against the
hardwiring this repo actually carries, it exercises the backend axes and leaves the frontend
ones — `frontend_dir = workspace_root / "frontend"` (`cycles/acceptance_checks.py`, the
`frontend_build` evaluator) and the `npm run build`-in-a-subdirectory assumption — untouched.
The plan's own risk row warns about a near-twin validating nothing; the original pick was a
near-twin on one half.

**What Next.js + TypeScript breaks**, verified against source 2026-08-09:

| Hardwired assumption | Broken by |
|---|---|
| server code is Python, so the 9 `ast.parse` checks apply | TypeScript (`tsc --noEmit` becomes the hygiene tier) |
| boot is `uvicorn backend.main:app` | `next start` |
| **the app boots from source** | `next build` is required first — no build exists anywhere in today's probe path |
| tests under `backend/tests/`, Python import boundary | co-located, no equivalent boundary |
| build runs in `frontend/` via `npm run build` | one build at the project root |
| backend and frontend are separate trees | one tree |
| the manifest has an `api` half and a `frontend` half | both are routes; some return JSON, some markup |

**Corrections to claims made while deciding, recorded so they are not inherited:**

- **File-system routing does *not* break "endpoint discovery is static and declared up front,"**
  which was asserted twice during selection. Next discovers routes from the filesystem, but the
  expander still works from a manifest that *declares* paths and places files at derived
  locations (`POST /runs` → `app/api/runs/route.ts`). Declared-then-placed is what an expander
  does. That assumption stays on the unvalidated list.
- **The manifest maps onto Next.js better than the selection discussion implied**, which lowers
  the release risk that was repeatedly cited against it.
- `[run_id]` is a **third** path-parameter convention after FastAPI's `{run_id}` and Express's
  `:run_id` — #820's trigger 3 fires here regardless of which candidate had been chosen.

**What the owner released to make this possible.** The 2026-08-07 framing assumed a rigid
backend/frontend split. Ruled 2026-08-09: *"I am good with breaking the frontend vs backend
rigid thinking so long as the squad can compose an app with a viable stack — it doesn't have to
be structured as front end vs backend."* That, plus *"I don't want to force decisions to make
the manifest comfortable; if the manifest pattern needs to break down then so be it,"* converts
the manifest's two-section shape from a constraint on selection into **a thing under test**.

**The risk that remains is attribution, not mapping.** Next.js moves the most variables at once,
so a poor VS makes "the blueprint schema does not generalize" hard to separate from "the squad
cannot write server components correctly." M6's taxonomy is the instrument; **at VS, watch
attribution, not pass rate** — the same discipline V4 was given.

**Alternatives considered and rejected in this round** (the 2026-08-07 rejections below still
stand and are not relitigated):

- **NestJS + React-TSX in `apps/api`/`apps/web`.** A genuine backend framework, lower release
  risk, breaks every backend axis plus the backend-build one. Rejected because it preserves the
  split and the manifest's domain shape, which are two of the three things only a unified stack
  reaches. **Recorded as the fallback** if Next.js fails to land: it would still give S3 a second
  instance. Its decorator routing (`@Controller('/runs')`) is structurally analogous to
  FastAPI's, which would make a TypeScript `endpoint_defined` tractable — relevant to S4.
- **Express + server-rendered templates.** Breaks the frontend build cleanly, but almost nobody
  starts a new app with it in 2026; it fails the "viable stack to build with" criterion.
- **FastAPI + React-TS as a "pack combo."** Breaks roughly one thing: the frontend authoring
  language. Everything the hardwiring complaint is actually about — the AST tier, boot,
  boots-from-source, the import boundary, the test convention, the manifest shape — is on the
  backend and would go untouched. **The composability idea it came from is kept** (see below).

**The pack-combo idea, deferred deliberately.** The owner raised decomposing a stack into
independently-variable packs — `(backend, frontend)` — so `(fastapi, react_ts)` would be a
recombination rather than a new stack. Good idea, wrong order: deriving a composition model now
means generalizing from **one and a half** instances, which is weaker footing than the two the
Blueprint SIP already insists on. Once `(nextjs_ts)` lands, attempting a cross-combo is nearly
free and *is* the composability test, with real packs instead of an abstraction designed for it.
**Consequence for the build:** while writing stack #2's pack, record backend/frontend
entanglement in the bend register. Entanglement that cannot be separated later is cheap to
notice now and expensive to reconstruct.

---

*The original 2026-08-07 ruling follows, retained for its criterion and its rejections.*

An Express-or-Fastify API with a typed React frontend. The selection criterion was
cost-per-assumption-broken: stack #2 must differ from `fullstack_fastapi_react` along the
axes the blueprint SIP names as FastAPI-shaped, or it reveals nothing — but 1.6 already
carries two headlines and a measurement window, so the break must not drag the verification
machinery into the experiment alongside the schema.

**What it breaks — three of the four named assumptions:**

| Assumption | How a TS stack breaks it |
|---|---|
| `analysable_suffix: str` (singular) | `.ts` + `.tsx` — two analysable suffixes in one stack |
| `harness_entry_modules` (Python-style import boundary between tests and app) | Node module resolution has no equivalent boundary |
| `qa_test_namespace` (test ownership as directory prefixes) | co-located `*.test.ts` beside source is the convention, not an option |

**What it deliberately holds constant: HTTP.** Endpoints, probes, and the derived
verification contract keep working, so what is under test is the **blueprint schema** rather
than the whole verification stack. That containment matters because M0 is already changing
contract derivation inside the same release.

**Why the cost is low:** the Node toolchain is already in the tree — `agents/Dockerfile`
carries Node.js/npm for the frontend build check and vitest (#306, shipped 1.3.1), and the
sandbox's `EnvironmentContract` is already parameterized by image plus required tools. No new
language runtime enters the pipeline.

**Rejected alternatives, recorded so they are not relitigated:**

- **Go** breaks *more* — single-binary packaging, and tests living inside the package rather
  than in a directory — but costs a new toolchain in the agent image, the sandbox env image,
  the test runner, and the `command_exit_zero` allowlist that #707 already declares
  untrustworthy. Too much S-lane infrastructure for a release whose S lane must also write a
  two-stack schema. **Reconsider as stack #3**, where its packaging break is the point.
- **A Python CLI / non-HTTP stack** breaks the deepest assumption (slots derivable from
  declared entities and routes) but puts the probe machinery under test simultaneously with
  the schema. Wrong experiment for this release.

**The latent break this forces into the open.** `analysable_suffix: str` is *already* wrong
today: the current stack is `.py` backend plus `.jsx` frontend, and the typed checks are
hardcoded to `.py` — which is exactly why #668's `.jsx` half keeps deferring. Stack #2 does
not create that mismatch; it makes the schema answer for one that already exists.

### S3. Promote the Stack Blueprint SIP, schema written against two stacks

Its acceptance gate is literally the existence of a second real stack, because "generalising
from one instance produces the FastAPI contract with generic field names — which is worse
than no contract, because it looks authoritative and the second stack will quietly bend
itself to fit rather than reveal the mismatch." Promotion is therefore a **mid-release
milestone**, and the schema is reconciled across both stack vocabularies.

#### S3 exit criterion — the proof this step was missing

M0 proves derivation against a known-good reference and S1 proves consolidation by exact
byte-equivalence. S3 originally had neither: "the schema works for two stacks" is a
subjective claim, and *accommodating* two stacks is not the same as *modelling* them. The
proof is the inverse of the failure mode the SIP itself names:

1. **The bend register.** Every point where the TS stack had to adopt a convention it would
   not otherwise use — a directory layout, a naming rule, an entry-module shape — purely to
   satisfy the schema is recorded as a **bend**, with the field that forced it. Exit
   criterion: **zero unexplained bends.** A bend that survives must be argued as a genuine
   cross-stack convention, not as a concession, and that argument is reviewable.
2. **The falsification pass.** For each blueprint field, remove or corrupt it and confirm
   something *breaks* in at least one stack. A field whose removal breaks nothing is
   decorative — it is describing a fact no consumer reads, and it should be deleted before
   the schema is frozen rather than after it has accreted meaning.
3. **No single-stack fields by accident.** A field populated meaningfully by exactly one
   blueprint is either a genuine optional capability (**declared as such, with the reason**)
   or a FastAPI assumption wearing a general name. The schema must say which.

#### What S3 will NOT have validated — disclose at promotion, do not imply generality

Two gaps, both structural consequences of choices already made. Recording them here so the
promotion states them, rather than having a later reader infer a generality the schema does
not have.

**1. Criteria-family variation is untested by construction.** The SIP records that the
contract emitter's criteria families are **pack-parameterized, not universal**: a
server-rendered stack has no frontend build, so `vc-frontend-builds` is meaningless for LAMP
while HTTP probes and suite checks transfer untouched. A blueprint must therefore declare
*which criteria families the emission gate may draw from*.

**Stack #2 cannot surface this.** Node/TS was chosen to break three FastAPI-shaped
assumptions while **holding HTTP constant** (S2's containment argument, which still stands) —
and it also has a frontend build. So both stacks agree on precisely the axis the criteria
family question turns on. S3's schema will be written against two stacks that cannot
disagree about it.

Consequence: either the schema declares a criteria-family field it has **not** falsified
(and says so, per the falsification pass above, which would otherwise delete it as
decorative), or it omits the field and the first server-rendered pack is a schema change.
Both are acceptable; silently shipping the first while implying the second is not. The
honest resolution is a **declared, deliberately un-falsified field with the reason recorded**
— the `DECLARED_UNBUILT_CHECKS` pattern applied to a schema.

**2. The two stack vocabularies are still two.** The SIP names them: the manifest says
`fullstack_fastapi_react`, the acceptance checks branch on `stack != "fastapi"`, and
`resolve_check_stack()` bridges them. **S1 removed the duplicate declaration, not the drift**
— the mapping is now sourced from the one stack registry, so there is a single answer to
"which stacks exist", but a stack still has two names and S3 still owes the reconciliation
the SIP asks for. Recorded because "S1 consolidated the per-stack facts" could otherwise be
read as having closed this, and it did not.

Together these convert "works for two stacks" from a judgment call into a reviewable
artifact — which is the same move #730 made for typed checks, where declaration is required
and drift is guarded.

Riding here (ROADMAP's 1.6 S scope): the **QA-decomposition anchor's structural derivation** —
tasks declare produce-vs-verify and `expected_artifacts` derive from the blueprint's ownership
map, making the shk-1 dual-claim class *inexpressible* rather than merely rejected.

### S4 *(capacity)*. Migrate typed checks off hardcoded `.py`

Onto the blueprint's declared source language. This is where #668's `.jsx` territory and
#598's packaging criterion become expressible; both stay capacity-bound.

**Note the coupling S2 creates.** With a TS stack in the tree, "hardcoded `.py`" stops being a
latent inelegance and becomes a live correctness gap.

> **Correction 2026-08-09 — this section named the wrong failure mode, in the reassuring
> direction, and the real one is #818.** It said the typed checks "would **silently skip** the
> entire second stack," making S4 a disclosure obligation about a *narrower* enforced surface.
> Both halves are wrong, verified against source:
>
> 1. **They would not skip silently.** `fill_slot_signature`, `undefined_names`,
>    `endpoint_defined` and `module_imports` all declare `applicable_extensions={".py"}`, so
>    `is_check_applicable(name, "*.ts")` is **False** — which `cycles/manifest_gates.py:252`
>    turns into a winnability **rejection** and `cycles/task_plan.py:462` turns into a
>    **stripped check with a WARNING**. The repo already refuses to credit a check that cannot
>    run.
> 2. **The real failure is upstream of the checks and worse (#818).**
>    `capabilities/scaffold_contract.py:59` dispatches
>    `_routes_criteria if path == _ROUTES_PATH else _view_criteria`, with
>    `_ROUTES_PATH = "backend/routes.py"` hardcoded at `:36`. A TS stack's slots are `.ts`, so
>    **nothing matches and every slot — including the API routes file — derives view
>    criteria.** `endpoint_defined` is never *emitted*, so there is nothing for the guards in
>    (1) to catch. The second stack would not ship with a narrower enforced surface; it would
>    ship with an **incorrect contract that every gate accepts**.
>
> Consequence: **#818 is on the critical path ahead of the Node stack**, and S4 is no longer a
> disclosure obligation — it is the residual coverage question after #818 lands.

S4 proper — teaching the typed checks a non-`.py` source language — stays capacity, because
once #818 makes the emitter refuse a stack it has no criteria pack for, the remaining gap is
visible rather than silent.

### S5. Blueprint vocabulary governance — **who may add a field**

The plan repeatedly treats the blueprint as *the closed vocabulary that bounds authoring*.
A closed vocabulary with no admission rule is not closed: the path of least resistance,
every time authoring hits a limit, is to add a blueprint field — and the abstraction decays
into a union of stack-specific features while still looking general.

**Admission rule: a new blueprint field must be demonstrated on at least two stacks before
admission.** This is the SIP's own argument applied to its successors — if generalizing from
one instance produces FastAPI-with-generic-names, then *extending* from one instance does
the same thing one field at a time.

Consequences, stated so they are not surprises:

- A one-stack need is expressed as a **declared optional capability with its reason**, not as
  a general field. The schema says "this stack has X" rather than implying every stack does.
- A `blueprint_limitation` from the M6 taxonomy does **not** automatically authorize a new
  field. It authorizes the *question*, which this rule adjudicates.
- Judgment classes promoted out of `decisions[]` by the M2 ratchet enter through this same
  gate. The ratchet identifies candidates; governance admits them.

The rule can be waived, but only explicitly and with the waiver recorded on the field —
the #682 pattern, where a waiver discloses rather than rewrites.

---

## Generalization debt after 1.6 — **what stays unvalidated, stated plainly**

The S lane's headline is "Generalized Build Capability." Honesty about the release claim
requires saying *how* generalized, because holding HTTP constant (S2) is a deliberate
containment and not a completed generalization.

**Validated by 1.6** (two real instances exercise them): source-language plurality
(`.py`/`.jsx` vs `.ts`/`.tsx`), the test/app import boundary, test-ownership convention,
and the build/test command surface.

**Deliberately unvalidated after 1.6**, each with the stack that would settle it:

| Assumption still resting on one instance | What would test it |
|---|---|
| Fill slots derive from declared entities and routes | a non-HTTP stack (CLI, library, batch) — the deepest assumption, untouched here |
| The routing model is expressible as method + path | any non-REST transport (GraphQL, RPC, event-driven) |
| Endpoint discovery is static and declared up front | a framework with dynamic or convention-based routing |
| Packaging is a container with a long-running server | a single-binary or serverless target — **Go, the named stack-#3 candidate** |
| One deployable unit per application | anything multi-service |

**The standing stack-selection rule**, so future expansion is coverage-driven rather than
language-driven: **each additional stack must invalidate at least one assumption still on
this list, and the list is updated when it does.** A stack that adds a language while
breaking nothing on the list adds maintenance and proves nothing. This is why S2 chose
Node/TypeScript over a FastAPI near-twin, and it is why Go is queued rather than dropped —
its packaging break is a row above.

---

## Owed to 1.8 — the one intention this release owns

**B1. Record the pre-memory rejection-class recurrence baseline.** *(Release-defining, and
the only item here whose omission is permanent.)*

Cross-Cycle Memory's entire value claim is that recurrence of the same mistake falls. That
needs a baseline captured from the authored-mode window, **before memory exists**. Once memory
is live the baseline is unrecoverable and the claim becomes unmeasurable.

Concretely: durable per-cycle counts of rejection classes — plan-validation rejections and the
M6 authoring failure taxonomy — emitted as a first-class output of the authored-mode window,
read by nothing in 1.6. Cheap while building authored mode; impossible afterward.

**Two dimensions, not one.** Memory should reduce both how often a mistake recurs *and* how
expensively it is recovered from, so the baseline records both:

- **recurrence** — occurrences per rejection class, per cycle;
- **time-to-resolution** — attempts and re-rolls consumed before that class cleared.

The second is equally unrecoverable after the fact and equally cheap now, since the
instrumentation is already being added for M5 and M6. A memory implementation that halves
recovery cost without changing recurrence is a real win that a recurrence-only baseline
would score as zero.

Full rationale: `docs/plans/post-1-5-roadmap-reconciliation.md`, "Design intentions carried
forward," intention 5.

---

## Verification cadence — when a cycle is actually worth running

Most of this release is **offline and deterministic**: M0a is a fixture test, M0b is
seed-time wiring, M3/M2/M6 are gates provable against hand-made manifests. Running cycles
through that stretch burns budget to learn nothing. The first work that *requires* a live
cycle to mean anything is M1.

Cycles need a deployed image, so the cadence below is also the deploy cadence: batch the
offline work, deploy, run the verification that fits what just landed.

| # | Trigger | What runs | Kind |
|---|---|---|---|
| **V1** | queue front deployed | Two targeted **create probes**, no full cycle: a bind-mode create with no contributors must 422 (#762 live), the implementation-only replay shape must still be accepted (the false-positive check). Plus a boot check that #766's disclosure line appears exactly once and the vendor `ERROR` is gone | diagnostic |
| **V2** | **after M0b, before M1** | **Guard 1b** (reference manifest → byte-identical downstream artifacts) **+ a full seeded-mode control cycle** | diagnostic — **and it banks the control** |
| **V3** | M3 / M2 / M6 landing | **No cycles.** Adversarial hand-made manifests against the gates, including #772's `success_status` trap as the designed-failure probe | — |
| **V4** | M1 lands | **First authored cycles, unscored.** Several, expected | diagnostic |
| **V5** | M4 / M5 land | Integration shakedown — the full authored path with provenance stamping, B1 emitting, and **a manifest carrying an unresolved-critical decision, to prove the question-gate fires and the answer reaches the revision** | diagnostic |
| **V6** | before pre-registration | **Authored-mode viability run** — has this succeeded even once? | diagnostic; **gates V7** |
| **V7** | frozen deploy | **The authored-mode FAY window.** Pre-registered N, unfiltered | **evidentiary** |
| **VS** | stack #2 expands | **Track S's missing verification point** *(added 2026-08-09)* — does the Node/TS stack expand, derive a satisfiable contract, and carry a cycle end to end? S3's schema is written against two stacks, so one of them being unproven would make it a schema against one stack and a hope | diagnostic; **gates S3** |
| **V8** | at the cut | Confirmation shakedown on the integrated line. **The seeded control re-run is conditional** — run it if the window disappoints or something looks off, not as a checkbox | diagnostic |

### The rule that keeps these from blurring

> **A shakedown is diagnostic and you fix what it finds. A window is evidence and you fix
> nothing until it closes.**

V4–V6 are where reacting to what you see is the *point*. V7 is where reacting invalidates
the measurement. The 1.4 arc pre-registered its window precisely because those two collapse
into each other under pressure.

### V4's failures are the product, not a setback

The first authored cycles failing at the winnability gate **is the system working** — the
gate doing in seconds what would otherwise cost a full implementation to discover. The thing
to watch at V4 is not the pass rate. It is whether **M6's taxonomy can name which subsystem
to blame**: authoring defect, schema gap, blueprint limitation, derivation defect, or PRD
insufficiency. If every V4 failure lands in one undifferentiated bucket, M6 is not finished
and V7 will produce a number nobody can act on.

### Why V2 sits where it does

M0b changes *which contract a cycle runs against*, on the path **seeded mode uses too**. The
moment right after M0b is the last one where the pipeline is fully deterministic and any red
is unambiguously ours rather than ambiguous between our change and model variance. Banking
the seeded green there, and re-running it at V8, turns one observation at the cut into an
actual control with a clean baseline between the two. See "Protecting seeded mode" below.

### Why V6 exists

Pre-registering a window for a capability that has **never once succeeded** wastes the
window. The FAY methodology set its 1.4 bar at ≥4/6 because there was reason to believe it
was achievable; V6 is the cheap answer to *do we have reason to believe?* It is explicitly
**not part of the window** and its rolls are not counted — recorded here so a later reader
cannot mistake it for a filtered first attempt.

---

## Gates

Each gate names the verification that closes it.

**Gate 1 — design commitments and enabling proofs.** *(Verification: V1, then V2.)* SIP-0103 §6's open questions resolved
(authoring decomposition first among them); **M0's derivation proof is already banked** (measured
2026-08-07, zero diffs) — Gate 1 instead requires M0a's standing equivalence guard merged and
M0b's derive-at-seed landed; S1's consolidation merged; the manifest-v5 migration posture
recorded. **S2 is already settled** — Node/TypeScript,
ruled 2026-08-07 at plan time. *Exit:* no release-defining work starts against an unresolved
design question.

**Gate 2 — the authoring loop closes.** *(Verification: V3, then V4.)* M1–M4 land, with M6's taxonomy in place before any authored manifest is rejected (a rejection recorded without a class is data lost); an authored manifest passes schema and
winnability gates and runs the existing pipeline end to end with no mode branch below
framing (Guard 1's architecture test green). **M4's question-gate is exercised, not merely
present** — one manifest carrying an unresolved-critical decision must stop, surface its
question, and revise on the answer; a release where the path never fired has not shown it
works.

**Gate 3 — integration.** *(Verification: V5, then V6.)* M5 provenance and M6's taxonomy; S3 promotion with the two-stack schema (bend register + falsification pass) and S5's admission rule recorded; B1 emitting both dimensions;
enabling riders (SIP-0093 completion, SIP-0102 steps 3–4) landed. Deploy window with
loaded-module verification, per the 1.5 precedent.

**Cut gate.** *(Verification: V7, then V8.)*
1. **Core-claim gate:** M0–M6 and S1–S3 + S5 complete; B1 emitting both dimensions. Removal of any item requires an
   owner-ratified scope change.
   **One such change is on the record:** SIP-0103 §3.3's third bullet — the interface
   self-consistency proof — is **deferred to 1.7 (#820, owner ruling 2026-08-09)** with named
   triggers. M3 is otherwise complete. Recorded here because "M0–M6 complete" would otherwise
   read as covering a normative bullet that does not ship.
2. **Capacity roll:** unfinished capacity items → 1.7 pool with a milestone update.
3. **Full regression green**, and all three guard halves verified (1a no-branch architecture
   test; 1b reference-manifest equivalence; 2's committed pre-registration record).
4. **The measurement:** authored-mode FAY window — pre-registered N, unfiltered, frozen deploy.
   **Gate: FAY repeatably > 0 in authored-manifest mode**, banked as the authored-mode baseline
   that 1.8's memory and campaign work measure against.
5. **The offline guards pass** — M0a's equivalence guard (built), **plus Guard 1a's
   architecture test and Guard 1b, both of which must be *built* first** (see Guard 1;
   verified unbuilt 2026-08-09). Replay zero-diff is **dropped** — it never existed and
   inventing it at the tail of a release is new scope, not a guard. The seeded control is a
   **comparison instrument available on demand, never a checkbox** (owner ruling, reaffirmed
   2026-08-09 after the claim sweep): run it against the seeded pair when the window
   disappoints or a number looks off, so design is held constant and "design step or
   machinery?" is answered directly. It does not gate the cut.
6. **Confirmation shakedown** on the fully integrated line, green, per the 1.4/1.5 cadence.

### The seeded control — **conditional, not scheduled** *(revised 2026-08-09)*

> **SUPERSEDES the original "Protecting seeded mode" requirement**, which made a V2/V8 paired
> seeded control a cut-gate item. Owner-ruled after V5, on the argument below. The frozen pair
> survives as an **offline test fixture**; what is retired is spending *cycles* on it.

**The control's unique coverage is a strict subset of an authored cycle's.** Seeded and
authored runs differ only in the framing half — below framing they are one code path *by
construction*, which is Guard 1a, and #796 made it literal by having an authored cycle derive
its contract and become bind mode. Expansion, contract binding, plan validation, dispatch,
checks and corrections are exercised identically by both.

So a seeded run adds no coverage. It adds **lower variance on the shared part**: design held
constant means a yield change is attributable to code rather than to that roll's design. That
is precision-per-cycle, not reach — and with a multi-roll authored window there are already N
observations of the same machinery.

Two further facts, stated because they are what actually decided this:

- **The control has never fired.** V2 banked one seeded observation (43/43) and nothing has
  been compared against it. A detector that has never fired is either useless or means nothing
  regressed, and one observation cannot distinguish those.
- **It measures a configuration the release does not ship.** 1.6's claim is authored mode. A
  scheduled regression detector for the fill-in-a-supplied-design path spends the cut's budget
  proving the 1.4 capability still works.

#### What replaces it

| mechanism | status *(verified 2026-08-09)* | cost | what it catches |
|---|---|---|---|
| **M0a's standing equivalence guard** | **BUILT** — `tests/unit/capabilities/test_contract_derivation_reference.py` | offline | the deriver drifting from the pinned reference |
| **Guard 1b** — reference manifest through authored mode → byte-identical downstream artifacts | **NOT BUILT** | offline, milliseconds | transformation regressions, structurally, before any window |
| **Replay zero-diff** over the 1.5 green corpus | **NOT BUILT**, and never was | offline | stored evaluation rows re-evaluating differently under new code |

> **Correction 2026-08-09 — this table originally presented all three as existing, and two do
> not.** It also cited "(#734 method)" for the replay row; #734 is *"workspace-revision
> provenance — stamp revision identity on every acceptance verdict,"* which is a different
> thing. No replay-zero-diff-over-a-corpus script or test exists.
>
> **The retirement stands, and the correction does not weaken it** — because this table was
> never the load-bearing argument. The load-bearing argument is structural and survives the
> sweep intact: *the control's unique coverage is a strict subset of an authored cycle's,*
> since below framing the two are one code path by construction (Guard 1a, verified above —
> one call site, inside framing) and #796 made it literal by having an authored cycle derive
> its contract and become bind mode. A mechanism that is unbuilt cannot make a subset into a
> superset.
>
> What the correction *does* change is honesty about coverage in the meantime: until Guard 1b
> exists, nothing offline isolates a provenance change from a transformation defect. Guard 1b
> is small and worth building; the replay corpus is new scope at the tail of a release and is
> **dropped** rather than invented now.

All three are offline. That is where most of the control's value already lived; the cycles
were buying variance reduction on top.

#### The seeded cycle stays available as a diagnostic

**Retire the schedule, keep the capability.** The question a seeded run uniquely answers is
*"is it the design step or the machinery?"* — and that question only arises when a window
disappoints. If V7 comes back poor, one seeded cycle separates the two directly, because
design is held constant. Deleting the capability would remove the only instrument for that
moment, which is exactly when you least want to be building one.

So: **V8's seeded re-run becomes conditional.** Run it when the window disappoints or
something looks off; not as a checkbox at the cut.

#### The frozen pair is a fixture, not an anchor

`examples/03_group_run/interface_manifest.yaml` (content hash `bb472e267e53…`) and contract v9
(`tests/fixtures/reference_contract/…`) are pinned by exactly two sha256 constants in M0a's
test, one committed fixture, and two vault artifact ids. Their remaining job is offline: the
deriver guard, Guard 1b, and the gate tests.

**Consequence worth stating, since it was previously treated as a constraint:** re-basing the
pair is a fixture update — re-derive, re-pin two constants, re-ingest — not a measurement
event. The prohibition on the hash moving was always about it moving *incidentally* (a
provenance edit silently invalidating a binding, the #494 class), never about a deliberate
versioned re-base. That distinction unblocks #795 and #772, whose fixes move the hash.

### Non-gating diagnostics for the window (§5c.7)

FAY stays the gate — functional truth. Recorded alongside, non-gating: structural manifest
diff against the human reference (§5b Q3 — cheap and mechanical on a typed canonical surface,
and it stays out of both the gate and squad inputs), revision/attempt counts, the gate-rejection
reason taxonomy, and manifest size/surface counts. **"Maintainability" and "elegance" metrics
are declined** — no deterministic representation exists, and an LLM-graded elegance score is
exactly the evidence-quality laundering A6 forbids.

Design-quality heuristics may enter only as **advisory-lane checks with their own identity**
(the `plan_prose_contract_divergence` pattern — visible, non-gating, never laundering into
blocking), promotable only with a deterministic representation. Phase 1's design-quality
authority is **measurement plus a sampled read**, with the human gate reduced to answering
the design's own declared questions (M4's narrowing, 2026-08-08). §5c.2 assigned that
authority to the HITL gate; V4 showed a mandatory review contributing nothing while the one
question a human uniquely held went unasked, so the diagnostics above carry the weight and a
design is read when a number moves.

---

## Risks

| Risk | Why it is real here | Containment |
|---|---|---|
| ~~Derivation can't reproduce v9~~ **RETIRED 2026-08-07** | Premise was false — v9 *is* the deriver's output for v4, exact equality | Replaced by: *the deriver silently drifts from the pinned reference* → M0a's standing equivalence guard |
| **Authored chaos swamps the window** | An authored manifest can fail in ways a seeded one never could | Blueprint grammar + deterministic gates bound the space; free re-roll and hash-freeze at approval bound the blast radius (§5a) |
| **Stack #2 too close to FastAPI** | A near-twin would validate nothing | Settled at plan time: Node/TypeScript breaks three of the four named assumptions while holding HTTP constant (S2) |
| **The TS stack's break is shallower than hoped** | Holding HTTP constant is a deliberate containment, so the slots-derive-from-routes assumption goes untested this release | Recorded, not hidden: that assumption is stack #3's job (a non-HTTP stack), and Go is named as the packaging-break candidate |
| **Authored mode forks the pipeline** | The easy implementation is a second path | Guard 1's architecture test |
| **Rider creep** | Five riders were listed against two headlines | Work classes; only claim-serving riders are enabling |
| **Measurement drift** | A window tuned mid-flight proves nothing | Guard 2's pre-registration, committed before roll 1 |

## Rollback seams

One PR per issue keeps every behavior-changing item independently revertible by image swap.
The manifest **v5** schema change (M0's `success_status` rider) is the one versioned boundary:
additive-and-required-forward means old manifests must be migrated or rejected explicitly, not
silently accepted — decide which at Gate 1 and record it. Authored mode itself is
config-selected, so its rollback is a profile change, not a code revert.

## Evidence matrix

Instantiated at Gate 1 and maintained per landed item, per the 1.5 precedent. Every
release-defining item has a filled row before the cut; every behavior-stricter item's row names
the ruling that authorizes it.

> **Instantiated 2026-08-09 — it had been declared and left empty through fifteen landed items.**
> The sweep's second rule needs a vehicle, so the matrix gains one column: **the premise
> correction each build found, and whether it was propagated** back to this plan and the SIP.
> That column is the whole point. Filling it retroactively is what made the failure legible:
>
> **Six premise corrections were found at build time. One was propagated when it happened.
> Five were found only by this sweep, weeks later.** Every one of those five is a defect
> corrected elsewhere in this document today. The discipline was never missing — the
> *propagation step* was, and nothing made its absence visible.

| Item | Required proof | Live validation | Premise correction found at build | Propagated? |
|---|---|---|---|---|
| #762 preflight block | unit; middle condition load-bearing | V1 create probe | — | — |
| #766 prompt linkage | "can this call ever succeed", not "did it error" | V1 boot check | — | — |
| #770 SIP frontmatter | 11-draft real-input corpus | — | — | — |
| **M0a** #777 | byte equality **both ends**, no regen hatch | offline | **SIP §5b Correction 1 false** — the deriver exists; v9 is its output for v4 | ✅ PR #771 |
| **M0b** #779 | derive-at-seed; never overrides a supplied ref | V2 | — | — |
| **M3** #781 | 6 proofs vs adversarial manifests | V3 | **"per-endpoint `success_status`" would reject the reference manifest**; real rule is collection-POST only | ❌ → PR #819 |
| **M2** #783 | `decisions[]` parsed; hash pinned by test | V3 | **`decisions[]` was in the reference YAML but never parsed** — SIP §5c.4's "the field already exists" was true of the YAML, false of the model | ❌ → PR #819 |
| **M6** #785 | every `PROOF_*` has a class | V4 attribution | `prd_insufficiency` is not a gate failure | — |
| **M1** #791 | gates wired; old emitter deleted | **V4** | **SIP §5a's "zero new plumbing" false** — forwarding dropped `interface_manifest`, so authored mode was dead (#796) | ❌ → PR #819 |
| #796 | replay against stored artifacts (10 errors → 1) | V4 roll 2 green | — | — |
| **M4** #807 | question-gate fires on a real question | **V5** (fired, 2 questions) | documented "a manifest exists", implemented "this run produced one" | — |
| **M5** #803 | provenance is system-owned, never author-claimed | V5 (attempts=1) | **§5c.5's operator-edit record is not built, and neither is the path** | ❌ → PR #819 |
| **B1** #809 | both dimensions emitted | plan-validation half **never fired live** | — | — |
| #811 | replay restores the prefix a note cannot invalidate | owed | **SIP §5c.6's "#669 *already* threads reviewer notes into the next attempt" was false** | ❌ → PR #819 |
| #812 | machine/principal vocabularies cannot collide | owed | **`decided_by` was a hardcoded `"system"` literal, not from the token** — 140 human approvals mislabelled | ⚠️ issue only |
| **S1** #816 | `expand()` byte-identical; both hashes unmoved | offline | — | — |
| **#818** | FastAPI contract byte-identical after parameterization | **VS** | *(this sweep is its origin)* | ✅ PR #819 |

**Standing rule this instantiates:** a PR that corrects a premise updates this row **in the same
PR**. Not the issue alone — the issue is where the correction is discovered, this matrix is where
it becomes visible to the next person reading the plan. A row whose correction column says ❌ is
a known-stale claim somewhere in this document.
