---
title: Deterministic Verification Scaffolding with Semantic Fill Slots
status: proposed
author: jladd
created_at: '2026-08-13T00:00:00Z'
---
# SIP: Deterministic Verification Scaffolding with Semantic Fill Slots

## Status
Proposed (rev 3 — §10.4 Stage-1e baseline amended at Phase 0; rev 2 design-review feedback in PR #885)

**Targets:** acceptance decision in the open, against the 1e ledger through roll 17 — per the §10.4 amendment (2026-08-14); implementation in whatever feature window the owner assigns. The change is qa-surface-scoped and stack-opt-in (§8), so it can ride as an even-minor feature or land per-stack.
**Builds on:** SIP-0100 (scaffold ownership, fill slots, the frozen harness — this SIP is its test-side counterpart), SIP-0098 (verification contract; shells derive from the same manifest facts as the behavioral probes), #818 (criteria packs — the per-stack seam, including its asymmetric-default ruling), #877 (execution-model guidance — the experiment whose measured result motivates this), #866 (context completeness), #884 (the cross-role suite rewrite this SIP's frozen spine bounds).

## 1. Abstract

**SquadOps should not spend LLM inference on deterministic test mechanics the framework can derive, verify, and freeze. The framework owns the proven mechanical spine; the agent owns the remaining semantic uncertainty. Proven semantic patterns can subsequently be extracted into deterministic verification primitives (§9).**

The qa suite is the last build artifact whose *mechanical* layer — imports, file placement, invocation form, response-envelope paths — is invented fresh by an LLM every roll. The v1.6 stack-#2 ledger (§3) shows that layer to be the dominant cause of run death, that guidance shrinks the invention space but does not close it, and that every deterministic verification layer added this release has been reliable while the authored mechanical layer failed a new way almost every roll. This SIP applies the release's proven pattern — *scaffold the interface deterministically; the LLM fills judgment only* (SIP-0100) — to verification: the walking-skeleton expander emits a deterministic test scaffold whose shells carry the invocation mechanics and contract-derived assertions pre-written and frozen, and `qa.test` becomes a fill task that supplies domain assertions only. This is a verification-integrity change, not a code-generation convenience: it converts `tests_pass` from a monolithic LLM-authored verdict into layered evidence with per-layer ownership (§5, §6).

## 2. The QA architecture invariant

> SquadOps deterministically materializes all QA mechanics that can be derived from authoritative project facts. The QA agent supplies semantic judgment that cannot be deterministically derived.

**The deterministic layer owns:** test files and placement; imports; harness lifecycle/reset; invocation mechanics; the required-minimum behavior inventory; contract-derived status assertions; dependency discipline; the execution strategy (in-process, serverless).

**The agent layer owns:** domain assertions; edge-case selection; state-transition and cross-operation semantics; assertions not represented in the contract; additional tests; PRD interpretation.

Future QA work extends this boundary; it does not renegotiate it per-roll.

## 3. Problem statement — the mechanical-failure ladder

Every entry is a run-terminating or round-burning failure of the suite's *mechanics*, not its judgment (all `group_run`, stack #2 unless noted):

- **Roll 9** (`cyc_a92eaa4f4052`): suite imports `supertest` — not in `package.json`; collection death.
- **Roll 13** (`cyc_732b773cf323`): suite calls `.get()` on a `Record` (a `Map` assumption about an invisible const shape — #875) and sides with a self-contradictory probe on status.
- **Roll 14** (`run_02cc78b7acbe`, original): live-`fetch` suite against `localhost:3000` — no server exists under `vitest run`; two rounds repaired the crash, not the strategy; run terminated (#877).
- **Roll 14 resume attempts** (post-#877, clean-workspace attempt): a zero-byte emission; a `../`-prefixed fence path; dynamic-route handlers invoked **without the `{ params }` context argument the supplement explicitly teaches**; the error envelope read at an invented path; a probable wrong-module import.
- **#884**: the repair-locus fallback let a dev-role repairer rewrite the suite with no qa guidance — reintroducing live-fetch verbatim. A frozen mechanical spine bounds this class structurally: slot-level repair cannot change invocation strategy (§4.3).

Two structural facts sharpen the cost:

1. **The mechanics tail persists through guidance.** #877 fixed the *strategy* — post-fix suites import handlers and invoke in-process — but the tail (`params` arg, envelope path, module choice) still killed the attempts. This repeats the #871 bounding lesson: `nextId`'s arity was shown and still misused. Teaching shrinks the invention space; only removing the authorship closes it.
2. **The runs these failures kill are otherwise green.** Roll 14's app passed 38/39 checks and, on the clean-workspace attempt, every contract probe over real HTTP. Each mechanical death burns a ~20-minute 27B generation round, and #435 rightly caps correction chains at two rounds. To be explicit about what this evidence does and does not show: it demonstrates that repeated mechanical *authorship* is net-negative; it says nothing against the semantic layer's value, which this SIP preserves and gives cleaner room to operate (§6).

## 4. Design

### 4.1 Scaffold emission

`expand()` for a participating stack additionally emits test-scaffold files, **once per run at seed time** (the #881 ruling: seeding is a run-start act; there is no mid-run regeneration, so fill preservation across regeneration does not arise within a run — across runs, fills are re-authored like all task output). Emission is deterministic: same manifest facts + same expanded tree + same generator version ⇒ **byte-identical output** (§4.4 pins this M0a-style). The scaffold's content hash is recorded in cycle evidence.

Each scaffold file contains **behavior slots** — one per contract-derived behavior (create → declared success status; blank rejection → the derived rejection status per #874's rule; not-found → declared 404 mapping; one per declared endpoint). A behavior slot is a deterministic unit of required coverage, **not necessarily one physical test function**: the generator may emit whatever test topology the behavior needs. Each slot carries a stable **`slot_id`** bound to the contract criterion / probe id it derives from — giving a durable mapping from scaffold → authored fill → failure evidence → correction target (the criterion-stamped-probe-row precedent, SIP-0098 §6.4).

**Derivability rule (normative):** every pre-written element — import path, invocation call, `{ params }` shape, status assertion — MUST be derivable from authoritative facts (manifest, expanded tree, criteria pack). An element the generator cannot derive is **demoted to fill content, never frozen as a guess**. This is #874's lesson stated as law: the scaffold must not relocate hallucination from the LLM into the generator.

### 4.2 The frozen/mutable contract (normative)

| Surface | Status |
|---|---|
| Scaffold file paths and placement | **Frozen** |
| Imports | **Frozen** |
| Harness lifecycle (`beforeEach(reset)`) | **Frozen** |
| Invocation calls (`new Request(...)`, `{ params }` form) | **Frozen** |
| Contract-derived status assertions | **Frozen** |
| Test structure outside slot bodies | **Frozen** |
| Slot bodies (domain assertions) | Mutable — the qa author's surface |
| Additive test files beside the scaffold | Permitted under §4.6 bounds |

Without this table, "fill mode" is not actually deterministic; with it, the boundary is checkable.

### 4.3 Enforcement

SIP-0100 §2.4 freezes whole files; this SIP introduces **region-level** freezing (mutable slots inside frozen files), which needs its own mechanism:

- The generator emits a **scaffold manifest**: the frozen file list, per-file **spine hashes computed with slot bodies elided**, and the slot table (`slot_id` → file, region, bound criterion).
- Verification recomputes spine hashes on every stored emission touching a scaffold file and **rejects any mutation of frozen regions before the suite executes** — the same restore-and-signal posture as 2.4, at region granularity. (Slot-elided hashing is the v1 mechanism; AST-level structural verification is the named escalation if hashing proves too coarse.)
- **Scaffold self-repair is prohibited** (the #884 clause): no repairer — qa, dev, or any locus fallback — may modify frozen regions. A scaffold mismatch surfaces as a structured scaffold defect routed to the scaffold/manifest owner (§7), never to an LLM repair round.

### 4.4 The scaffold validity gate

Rails before mechanism (the M0 pattern, applied a fourth time): before any qa authoring, the emitted scaffold must pass a deterministic self-check —

- every import resolves against the expanded tree; every referenced handler exists;
- every invocation signature is derivable (dynamic segments present, `{ params }` keys match the declared path parameters);
- every asserted status exists in the contract;
- the scaffold **with empty fills collects cleanly** under the stack's runner (the frozen-harness proof, extended to the whole scaffold);
- byte-equivalence: a standing test pins that the reference manifest + generator produce byte-identical scaffold output (the M0a guard shape).

A validity failure **fails run setup loudly** — per the #845 precedent, an unscaffolded verification story is not a degraded run, and it must never consume an LLM correction round.

### 4.5 `qa.test` in fill mode, with a semantic brief

When the workspace carries a valid scaffold, `qa.test` becomes a fill task: the author receives the scaffold and emits **slot fills only**. Alongside the slots, the envelope carries a **semantic brief** enumerating what the deterministic layer already covers (derived for free from the slot table), framing the author's job as *residual semantic coverage*: state effects, cross-operation semantics, edge cases, PRD-derived properties the contract cannot express. (A richer brief that proposes semantic *opportunities* requires inference to generate and is follow-on work, §12.)

Emission failure modes that killed whole attempts — zero-byte files, invented fence paths, wrong placement — become structurally impossible for the spine; a bad fill degrades one slot, not the suite.

### 4.6 Additive tests (bounded)

The author may add whole new test files beside the scaffold. Normative bounds: declared dependencies only (#448); the same in-process execution model — no live-server assumptions (#877's rule); no mutation of frozen scaffold files; subject to the same harness verification as today. Additive tests are the author's judgment surface, not an escape hatch around §4.2.

## 5. Failure taxonomy and ownership matrix

`tests_pass` evidence splits into four distinct classes — the distinction drives correction routing and prevents a deterministic defect from being attributed to the application:

| Failure | Class | Owner / route |
|---|---|---|
| Scaffold import unresolvable, invocation underivable, scaffold won't collect | **scaffold-invalid** | generator defect; fails run setup (§4.4), never an LLM round |
| Frozen shell executes; app violates the declared contract | **app-contract** | dev repair — and a shell status failure and its bound probe's failure are **the same defect observed twice**: the correction router deduplicates on the shared criterion id rather than burning a round on each |
| Authored slot assertion wrong or failing | **fill failure** | qa repair, slot-scoped |
| Harness/runtime cannot execute | **test-infrastructure** | environment triage, not a work-product round |
| Wrong import / invocation signature / status assertion in a *frozen* region | scaffold-generation defect (impossible unless enforcement failed — a §4.3 violation) |
| Live-server assumption or undeclared dependency in a fill or additive test | prohibited-fill violation — qa repair with the violation named |
| Zero-byte or unextractable emission | emission failure (#566 path), not a suite-execution failure |

## 6. The independence boundary, measured

The shells derive from the manifest — the same source as the app scaffold and the probes. The honest boundary claim: **the scaffold determines what gets mechanically exercised; the author determines which semantic properties beyond the declared contract get asserted.** Shell-level green is *consistency* evidence (implementation ↔ manifest); *intent* evidence (implementation ↔ PRD) lives in the fills and additive tests, which remain an independent PRD reading.

So the claim is falsifiable rather than qualitative, the run report tracks per layer: scaffold-derived behavior count and coverage; authored-fill assertion count; additive test count; failures detected only by fills; failures detected redundantly with probes. These counts are the evidence base for §9's promotion decisions and for evaluating whether the authored layer is earning its inference spend.

## 7. Source-of-truth precedence

- The **manifest / verification contract** defines expected behavior.
- The **expanded tree** defines available implementation surfaces.
- The **generator never reconciles disagreements by inference.** If the manifest declares an endpoint the tree lacks (or any authoritative facts disagree), scaffold generation fails as a **manifest/scaffold contract failure** — evidence-bearing, routed to the scaffold/manifest owner, never a best-effort scaffold and never an LLM repair target. (By construction the tree is `expand(manifest)`, so disagreement implies generator-version drift or a mutated workspace — the failure message names which.)

## 8. Stack scope, opt-in, migration

- **This SIP is deliberately stack-#2-scoped** in its concrete design (route handlers, `Request`, `{ params }`, HTTP statuses). The architectural pattern — *deterministic verification scaffolding with semantic fill slots* — generalizes (component-harness scaffolds, pytest-fixture scaffolds, queue-worker injection scaffolds), but generalizing from one instance produces generic-field-name contracts (the Stack Blueprint's own acceptance lesson); other stacks get designs when they get instances.
- **Opt-in is an explicit `ScaffoldStack` declaration and all-or-nothing.** A stack whose facts cannot support every §4.1 derivation **refuses** rather than emitting a partial scaffold — #818's asymmetric-default ruling applied: silently-wrong has no safe default. No cross-stack default changes; stack #1 is untouched until its pack opts in.
- **Migration:** opting in affects future cycles only. No historical or active workspace is regenerated (no cosmetic mutation of terminal state).

## 9. Promotion: semantic → deterministic (principle only)

Repeated, proven agent-authored patterns are candidates for extraction into the deterministic layer (scaffold shells or probes). The conservative rule is normative:

> Only promote behavior into the deterministic layer when its derivation can be **proven from authoritative facts**. Frequency of generation is never sufficient — promotion by observation alone would relocate probabilistic behavior into a nominally deterministic generator.

Promotion is evidence-driven (recurrence, stable semantics, deterministic derivability, no loss of independent coverage — measured via §6's counts). The promotion *workflow* and its lifecycle are follow-on work (§12); the learning loop this implies is the Cross-Cycle Memory SIP's territory meeting this one, and is deliberately not re-invented here.

## 10. Acceptance evidence and exit criteria

1. **Structural (every roll):** the §4.4 validity gate passes on every scaffold emission, and the byte-equivalence pin holds. Reference stack-#1 contract and manifest hashes unmoved (the M0a guard).
2. **Longitudinal:** **N = 6 consecutive stack-#2 rolls with zero run-terminating mechanical suite failures**, attribution per the §5 taxonomy in the run ledger. N is set *now*, matching the observed baseline window (4 mechanical deaths across ~6 rolls); the owner may adjust it at design review — before results exist, not after.
3. **Economics:** correction rounds and generation-minutes attributable to qa mechanics, before vs. after — the §3 cost claim (~20 min of 27B per mechanical round) captured as a metric, demonstrating the intervention removed the spend and not just the label.
4. **Stage 1e baseline (amended 2026-08-14 — owner ruling at Phase 0 of the implementation plan):** the baseline corpus is the **open** Stage 1e ledger through roll 17 — the roll-by-roll failure attributions §3 cites. As proposed, this item required a *closed* 1e ledger ("acceptance is a reading of a closed ledger, not a retrospective interpretation of a live one"). The owner amended it to accept in the open. Evidence: the trigger the owner named for acting — repeated mechanical suite deaths *despite* the execution-model guidance (#877) and the repair-locus fixes (#884) — has already fired within the recorded ledger; waiting for 1e to close adds rolls to the baseline without changing the attributions this SIP reads. The closed-ledger safeguard is retained in equivalent form as Gate 6's window protocol (implementation plan): any new mechanical failure mode observed after this baseline — before or after 1e closes — names its uncovered surface, joins the §5 matrix, and resets the N=6 window.
5. **Non-goals:** replacing the probes (they remain the boot-and-HTTP layer); capping authored tests; changing `tests_pass` credit semantics (SIP-0096 untouched).

## 11. Alternatives considered

- **More guidance** — tried three times, measured (#877): strategy converged, mechanics tail persisted. Rejected as the complete answer; guidance stays, governing the fills.
- **Correction loops absorb the tail** — each mechanical death burns a ~20-minute generation round, #435 caps chains at two, and #884 shows the repair path can make it worse. Rejected.
- **Probes only, no authored suite** — loses the independent PRD reader and domain-semantics coverage. Rejected; §6 measures the layer instead of deleting it.
- **Author the suite from the PRD with no manifest access** (maximal independence) — maximizes divergence detection but reintroduces every mechanical failure this SIP kills. Rejected for the spine; independence lives in the fills.

## 12. Follow-on work (named, not designed here)

- Semantic-brief enrichment (inference-generated coverage opportunities).
- The QA evidence schema formalizing §6's counts.
- The promotion workflow and lifecycle (EXPLORATORY → OBSERVED → CANDIDATE → DETERMINISTIC), integrated with the Cross-Cycle Memory SIP.
- Cross-stack scaffold designs, one per stack instance, under the §2 invariant.
- Cycle Data Store queries over §6 evidence (which semantic patterns find defects; which are redundant with probes; which mechanics still consume rounds).
