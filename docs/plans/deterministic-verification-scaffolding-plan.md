# Implementation Plan — Deterministic Verification Scaffolding with Semantic Fill Slots

**SIP:** `sips/accepted/SIP-0104-Deterministic-Verification-Scaffolding-with.md` (accepted 2026-08-14 with the Phase 0 §10.4 amendment; rev 2 was PR #885)
**Plan revision:** 2 — design-review feedback incorporated (PR #892).
**Ordering principle:** sequencing and exit gates only, no dates. Each phase lands as its own PR with incremental commits; nothing merges without the owner.

## Why now

The generated test suite is the last artifact whose boilerplate — imports, function-call shapes, file placement, response-field paths — is re-invented by an LLM every roll. Across rolls 9–17 that layer produced a different small mistake nearly every generation, while every deterministic layer added this release stayed reliable and the apps themselves converged. The SIP moves the boilerplate into the scaffold and leaves the qa author the judgment content: assertion bodies. The failure catalog is the SIP's §3; the roll-by-roll record is the v1.6 ledger.

## Execution shape

**Gates 1–4 are the architectural proof** (the LLM cannot mechanically rewrite the scaffold); **Gate 5 is the observability/convergence layer**; **Gate 6 is empirical validation**. Strictly sequential: `P0 → P1 → P2 → P3 → P4 → P5 → P6`. P5 *design/schema* work may proceed during P4; no P5 runtime lands before P4 is proven (P5 consumes the enforcement signals P4 produces). No experimental roll before the minimum validation boundary — **P1–P4 deployed and proven** — is met; cheap local/deterministic validation runs continuously throughout.

## Phase 0 — SIP amendment + acceptance (blocking gate; owner + maintainer)

The SIP's acceptance evidence (§10.4) requires a *closed* Stage 1e ledger; this plan proposes implementing while 1e is open. **One ruling resolves it, made in the SIP, not here:** amend §10.4 in the open (baseline = the open 1e ledger through roll 17; the amendment's evidence is the owner-named trigger — repeated mechanical suite deaths despite the guidance and routing fixes), then accept normally (`update_sip_status.py` assigns the number; H1/Status synced by hand).

- **This plan never overrides the SIP.** If the owner declines the amendment, the plan shelves until 1e closes.
- Exit: amended SIP numbered in `sips/accepted/`, amendment recorded in the SIP itself (plans are superseded; the SIP is permanent).

## Phase 1 — Gate 1: the deterministic artifact

**First commit is the scaffold contract, not the generator** — otherwise the generator becomes the de facto specification:

- scaffold manifest schema; file/region ownership model; `slot_id` schema and provenance; frozen-spine hash definition (canonicalization stated); derivability source precedence (manifest → criteria pack → expanded tree; the generator never reconciles disagreements by inference); scaffold version + generator version.
- The manifest records the structural facts violation diagnosis needs, not hashes alone: generator version, scaffold version, source manifest / criteria-pack identity, expanded-tree hash, per-file frozen regions, slot ids with region bounds, bound criterion/probe ids. A hash mismatch must be attributable to generator drift vs. workspace mutation vs. producer edit.

Then implement emission against that contract: one behavior shell per contract-derived behavior (imports resolved against the actual expanded tree, `beforeEach(reset)`, the invocation call with `{ params }` for dynamic routes, the declared-status assertion, a fill slot per shell). **Lifecycle is explicit: expand → emit → validate → persist → expose to qa.test** — an unvalidated scaffold never becomes the run's current qa artifact, so nothing downstream needs an invalid-scaffold special case.

P1 owns **generation correctness**: deterministic output, authoritative derivation, manifest production.

Exit (Gate 1):
- Byte-equivalence: reference manifest + generator version → byte-identical scaffold and manifest.
- Derivability mutations: removing a derivation source changes output deterministically or fails generation — never a guess.
- Stack #1 contract/manifest hashes unmoved; no stack-1 scaffold (opt-in explicit).

## Phase 2 — Gate 2: the executable artifact

P2 owns **execution readiness** — proving the generated artifact can execute before any author sees it:

- imports resolve; referenced handlers exist; asserted statuses exist in the contract; the empty-fill scaffold collects under the stack's runner;
- **collection is not sufficient**: every shell's invocation is *executed against the walking skeleton* and must complete without a mechanical crash (assertion failures against stub handlers are expected and ignored by the gate; a `TypeError`/unresolved-symbol crash is a gate failure); slot boundaries are structurally valid; bound criterion identity survives into the emitted file.
- **The decisive negative test:** internally consistent inputs plus an injected generator defect (e.g. the manifest and tree agree a route exists, the generator emits the wrong import path) must be caught here as `scaffold-invalid` — the gate detects generator bugs, not merely missing inputs.

A validity failure fails run setup loudly and never consumes an LLM round.

Exit (Gate 2): the mutation corpus above, including the consistent-inputs/broken-generator case.

## Phase 3 — Gate 3: the bounded agent surface

**The merge contract is defined before implementation** (or P3 becomes another mini code-generation pipeline): slot id is the only addressing mechanism; one fill per slot; duplicate slot ids rejected; a malformed fill cannot alter bytes outside its slot; fills cannot introduce imports or dependencies into frozen regions; merge is deterministic and reproducible; merged output gets its own evidence/hash record.

- **Missing-slot rule:** a required slot receives a valid fill or an explicit `not_applicable` disposition with a reason. A missing fill is never silent success — it renders as a failing state attributed to the fill layer.
- **Fill validation before execution:** each fill parses, occupies only its slot, carries no forbidden imports/dependencies, no frozen-structure mutation, no external-server access. Deterministic rejection is cheaper than a qa repair round.
- The semantic brief is **coverage inventory only** — the list of behaviors the deterministic layer covers, derived from the slot table. No generated coaching, no semantic test planning (SIP §12 follow-on).
- Additive test files remain allowed under existing rules.

Exit (Gate 3): fill-merge round-trip determinism; the negative corpus (garbage fill degrades one slot and the suite still collects; oversized/duplicate/misaddressed fills rejected); slot containment proven. **P4 does not begin until this gate passes** — region enforcement must not debug an unstable fill protocol.

## Phase 4 — Gate 4: enforcement against adversarial producers

Region-level verification on every stored emission touching a scaffold file, with two protected classes:

1. **Frozen-spine mutation** — slot-elided spine hash mismatch → rejected, restored, structured scaffold-violation signal on the existing enforcement-carry transport.
2. **Slot-boundary manipulation** — moving delimiters, enlarging a region, nesting or duplicating slots, injecting statements adjacent to a slot. Slot markers are frozen structure under the canonicalization; the mutation corpus covers each of these explicitly.

No repair path — any role, any locus — may modify frozen regions or slot boundaries.

- **Hash-sufficiency boundary stated now:** hash-based enforcement is accepted when the adversarial mutation corpus is fully caught by the chosen canonicalization; AST-level verification remains the named escalation *on evidence* (a mutation the corpus shows hashing misses), not an undefined future.
- **The adversarial-producer end-to-end test** (the architectural claim's single strongest check): one fixture attempts, in turn — changing an import, changing the invocation strategy, modifying a status assertion, moving a slot, adding a dependency, pointing at a live server, rewriting another test file — and each attempt lands in its expected failure class deterministically.

Exit (Gate 4): the adversarial corpus, hash-sufficiency demonstrated against it, restore-and-signal proven on the repair path. **Gates 1–4 together establish the core invariant: the LLM cannot mechanically rewrite the scaffold.** This is the checkpoint before any expensive roll.

## Phase 5 — Gate 5: evidence and convergence (observability layer, not a prerequisite)

Pipeline kept explicit and separate: `observation → classification → correlation → owner → repair route`.

- Evidence rows carry slot ids; classification lands each failure in the SIP's four classes (scaffold-invalid / app-contract / fill / infrastructure); ownership is assigned from classification; routing consumes ownership.
- **Correlation, not causal equivalence:** a shell failure and a probe failure sharing a criterion id are *correlated* for the router — grouped, both observations retained — never auto-collapsed into one defect. Different criterion ids are never auto-merged.
- Run-report counts preserve the fields the future promotion model needs (slot/category, assertion type, unique finding, probe redundancy, defect class, cycle/stack identity) — schema preserved, workflow not built (SIP §12).
- No change to `tests_pass` credit semantics or SIP-0096.

Exit (Gate 5): routing tests per class; correlation tests (grouped, not collapsed); report fields present.

## Phase 6 — Gate 6: empirical validation

Deploy, then roll. The structural success criterion, stated falsifiably:

> All known scaffold-owned mechanical surfaces are deterministically validated and mutation-protected; any remaining mechanical failure is, by definition, a **new uncovered surface** and is classified and added to the enforced set.

The N=6 zero-mechanical-death window measures whether reality matches that claim. **Window protocol, fixed now:**

- only rolls generated with the final Gate 1–4 behavior count;
- partial or hand-assembled scaffolds do not count; resumed runs carrying pre-SIP artifacts do not count;
- a roll that never reaches qa (unrelated failure) neither counts nor resets;
- a new mechanical suite failure resets the window and names the uncovered surface;
- **from roll 3 (owner ruling 2026-08-15, SIP §13a): a roll counts only if its delivered app also passes `audit_delivered_app.py`, including the UI data-path check.** Roll 1 satisfied every other signal — verdict accepted, 36/36 checks, five probes, eight shells, `frontend_build`, and the boot audit — with a UI in which nothing worked; a human found it, no layer did. Rolls 1–2 are grandfathered (authored before the #902 guidance fix). The two criteria are recorded separately per roll and never collapsed: the mechanical claim spans all six, the audit claim rolls 3–6.

**These rolls carry a second obligation, which changes nothing about this one.** Owner ruling
2026-08-15: 1.6's Stage 1e is credited at **roll 3**, and rolls 3–6 also serve 1.6's **V6**
viability run (`docs/plans/1-6-0-authorship-plan.md`). Both are *reads* of this window's
outcome — the §10.2 criterion, the §13a audit condition, and the reset rule are untouched, and
V6's diagnostic licence does **not** extend here: a fix prompted by what V6 sees waits for the
window to close like any other. These rolls are P6 rolls first. They are explicitly **not**
1.6's V7 FAY window, which needs a frozen deploy — this one's is not, since #902's guidance fix
lands at roll 3.

**The semantic-value end-to-end test rides this phase**: a crafted defect the scaffold and probes cannot catch (behavior the contract does not pin — e.g. a state effect across operations) must be caught by a valid fill. The acceptance evidence the SIP wants is the pair: mechanical/contract errors caught deterministically, and a semantic defect caught only by the authored layer — proof the system has not reduced qa to consistency checking.

**1e credit is unchanged**: a green roll still boot-validates via `audit_delivered_app.py` before Stage 1e closes — shells prove manifest-consistency, not intent. Roll 1 made that sentence concrete: it *was* manifest-consistent and its app was unusable, so the audit now carries the UI data-path check (#903) and, from roll 3, gates the window itself.

## Scope boundaries

- nextjs_ts only; stack #1 untouched until its pack opts in (all-or-nothing, SIP §8).
- Deferred per SIP §12 and *not quietly re-entered here*: inference-generated semantic briefs, the full qa evidence schema, the promotion workflow, cross-stack scaffolds, the Cycle Data Store loop.

## Roll policy while building

No experimental roll before the P1–P4 boundary is deployed and proven. Local/deterministic validation (unit suites, in-container collection runs, adversarial corpus) runs continuously through every phase. Roll 17 stays failed-and-resumable as a fallback specimen, independent of this plan.

## Effort shape (not dates)

P1 large (contract + generator + manifest + pins) · P2 medium (skeleton-execution gate + negative corpus) · P3 medium-large (merge contract + fill validation + envelope) · P4 medium (canonicalization + adversarial corpus) · P5 medium (classification/correlation/report) · P6 = rolls. Strictly sequential with the P3→P4 rollback gate; P5 schema design may run during P4.
