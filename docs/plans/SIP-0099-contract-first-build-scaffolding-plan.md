# Plan: SIP-0099 Contract-First Build Scaffolding

## Context

SIP-0099 splits the build into three tiers — deterministic stack scaffold, deterministic
app skeleton expanded from a typed **interface manifest**, LLM-filled bodies in fixed slots —
so the model only generates what depends on what the app does. The full design lives in
`sips/accepted/SIP-0099-Contract-First-Build-Scaffolding.md`. This plan pins the phase
decomposition (the SIP itself has scope + open questions, not phases), what the Phase-0.5
spike already delivered, per-phase surfaces and verification, and the interleaving with the
SIP-0098 plan — the two ship as one Lane M contract surface for 1.4.

**SIP:** `sips/accepted/SIP-0099-Contract-First-Build-Scaffolding.md`
**Sibling SIP + plan:** `sips/accepted/SIP-0098-Verification-Contracts-Contract-Owned-Acceptance.md`,
`docs/plans/SIP-0098-verification-contracts-plan.md`
**Arc:** v1.4 (even minor), Lane M Scaffold headline.
**Acceptance already banked:** the SIP's self-declared gate — hand-written group_run
manifest → expander → skeleton builds+boots → fill-only cycle boot-built by hand — was met
by the Phase-0.5 spike (PR #429 + attempts 3.5–3.14; apps good since 3.8).

**Vocabulary guard:** "interface manifest" (entities/endpoints/routes — this SIP) is NOT the
implementation manifest (task decomposition, dev-authored). Never shorten either to
"manifest" in code or docs.

## What the spike already delivered (do not re-create)

- **The expander** — `src/squadops/capabilities/scaffold.py`: `InterfaceManifest` (typed
  dataclasses + parsers) and `expand(manifest) -> list[{path, content}]`, pure, no I/O.
  Spark's two scaffold-contract gaps closed in PR #429 review. This is spike-grade code in
  the right shape (pure module, no port/NoOp/factory — correct per the SIP: it is domain
  logic, not a vendor integration); 99.1 canonicalizes rather than rewrites it.
- **The hand-written group_run interface manifest** and the 15-artifact skeleton set used by
  attempts 3.5–3.14 (pre-ingested and seeded via `execution_overrides` — the spike-style
  delivery that 99.3 replaces with executor-side expansion).
- **Fill-only dev scoping via plan/PRD instruction** — proven behaviorally but not yet a
  system property; 99.3 makes it one.
- **Empirical schema validation** — the manifest shape survived six rolls and three clean
  fills; open question 1 ("manifest schema shape — keystone") is substantially answered by
  field evidence.

## Lane routing

All phases are **Mac lane** (expander/capabilities, framing artifacts + fragments, executor
setup seam — all Mac-owned surfaces). SIP-0099 has **no Spark measurement phase of its own**:
its at-scale field validation is subsumed by SIP-0098 phase 98.5 (the yield baseline runs
the full production path — framing-emitted interface manifest → executor expansion → bind
mode). The skeleton CI gate is deliberately Spark-independent (plain runners).

## Phases

### 99.1 — Expander canonicalization + skeleton CI gate (Mac; unblocks 98.2)

- Canonicalize `scaffold.py`: freeze `InterfaceManifest` as schema v1 (the spike shape);
  hang invocation off the profile seam per SIP §4 — `BuildProfile.expand(manifest)`
  delegating to the pure module (thin dispatch, template logic stays in `scaffold.py`);
  content-hash the emitted interface manifest artifact (SIP-0098's contract binds
  `interface_manifest_hash` to it).
- Check in the hand-written group_run interface manifest as the CI fixture.
- **Skeleton CI gate** (new `ci.yml` job, node + python toolchains on plain runners): expand
  from the fixture manifest → frontend `vite build` passes → backend imports and boots.
  This is the SIP's own acceptance surface and the gate SIP-0098 phase 98.2 emits into.
  (CI is x86_64 vs aarch64 dev — acceptable here; plain toolchains, no GPU/agents.)
- **Tests:** exact-content unit assertions on `expand()` output (feed manifest, assert files
  parse); malformed-manifest rejection cases; hash determinism.
- **Verification:** pure unit + deterministic CI. No cycles.
- **Exit:** skeleton gate green in CI; 98.2 unblocked.

### 99.2 — Interface manifest in framing (Mac)

- Extend the framing artifact with the typed interface contract: schema in the cycles domain
  (single-sourced with 99.1's `InterfaceManifest` — one schema, two consumers), emission in
  `_plan_authoring_service.py`, and the interface section surfaced in the gate package so
  the operator reviews *"are these the right 5 endpoints and 3 routes?"* as structured data
  at `progress_plan_review`.
- Role ownership within multi-role authoring (SIP-0093 pipeline): dev domain proposes the
  interface section, strategy guidance may constrain it, governance merge emits the
  canonical copy. (Pinned as the default; confirm at phase review.)
- Plan validation (both existing nets) rejects malformed/incomplete interface sections with
  #473 recorded semantics. Manifest present → scaffolded mode; absent → today's behavior
  (data-driven, no flag — same rule as SIP-0098 §6.6).
- Fragment edits follow the anchored-hash discipline.
- **Verification:** fixture tests through the real `execute_cycle` / plan-authoring entry
  points; **lite** cycles on Mac — a 7b framing squad emitting a typed interface section is
  organic fault injection for the validation net (lite, never smoke — no builder tail in
  smoke).
- **Exit:** a lite cycle's gate package shows a schema-valid interface manifest; malformed
  emissions record rejections; manifest-less cycles regression-green.

### 99.3 — Executor materialization + fill-only develop (Mac)

- **One generic call at the executor setup seam** (`_execute_sequential`'s existing
  `_materialize_run_root` / `_seed_prior_artifacts` / D3 pre-resolution block): if build run
  + interface manifest present → `BuildProfile.expand` → store as artifacts → seed. A few
  delegating lines only — template logic never enters the god-file (#290 rule; the
  decomposition boundaries of SIP-0097 apply).
- Expanded files ride the existing rails: vault → seed/pre-resolve →
  `develop._materialize_artifacts`. No new adapter.
- **Fill-only scoping as a system property:** dev fragments state scaffold-owned/fill-only
  discipline (fill bodies into slots; never rewire imports/routes/entries). Mechanical
  *enforcement* of frozen surfaces is deliberately NOT built here — it is SIP-0098's
  `frozen:` contract section (99.3 materializes; 98 verifies; no duplicate enforcement).
- Replaces spike-style skeleton delivery (pre-ingested artifact refs) — the 15-ref
  `execution_overrides` recipe becomes obsolete for scaffolded profiles.
- **Verification:** unit tests on the seam (manifest present/absent × build/non-build runs);
  one **lite** end-to-end cycle on Mac: framing emits manifest → executor expands →
  skeleton lands in dev workspace → fill-only develop runs. Byte-identical regression test
  for manifest-less cycles.
- **Exit:** production path (no hand-seeding) produces a skeleton-seeded fill run on lite;
  SIP-0098 98.5 may baseline against this path.

### 99.4 — Follow-on profile templates (non-gating, post-1.4-headline)

`python_cli_builder` and `static_web_builder` template sets per SIP §5. Explicitly not
gating the 1.4 headline; scheduled on amortization evidence (the per-*system* value thesis:
a template set pays for itself across every project on that stack). Each new profile ships
with its own CI fixture manifest + skeleton gate job and (per SIP-0098) its own
verification contract.

## Interleaving with the SIP-0098 plan (recommended Mac-lane order)

```
98.1 (contract schema+linter)      — unblocked now, pure
99.1 (expander canon + CI gate)    — unblocks 98.2
98.2 (contract emission + CI gates)
99.2 (interface manifest in framing)
99.3 (executor materialization + fill-only)
98.3 (bind-mode orchestration)     — may start before 99.3 using spike-style seeding;
                                     must be re-verified on the 99.3 path before 98.5
98.4 (probe runner)
98.5 (Spark: PRD v0.4 split + shakedown + N=5 yield baseline on the FULL production path)
```

The one hard cross-coupling beyond 99.1→98.2: **99.2 and 99.3 must land before 98.5** — the
yield baseline measures the production pipeline, not a hand-rigged spike path.

## Readiness couplings

1. SIP-0096 behavioral acceptance is landed and field-proven (prerequisite named by the
   SIP's own Targets line) — satisfied; no action.
2. All SIP-0098 plan couplings apply unchanged (#433/#434 before 98.5, rebuilds before
   rolls, #470 concurrent-safe, no hand-shepherded spike rolls).
3. Merge cadence: phase-per-PR off main, merged before the next phase branches.

## Open decisions (resolve at the flagged phase)

1. **New-component registration** (SIP open Q2): for v1, adding a component mid-cycle is out
   of scope — the correction loop operates on bodies; interface changes require a manifest
   amendment upstream of expansion. Revisit with 98.5 evidence if corrections keep wanting
   interface changes. Decide finally at 99.3 review.
2. **Template versioning** (SIP open Q3): v1 rule — templates and pinned dependency versions
   live with the expander; any template edit re-runs the skeleton gate and the SIP-0098
   contract gates (bare-skeleton + reference-fill). Formal version markers deferred until a
   second profile exists.
3. **Interface-section role ownership** (99.2 pin above): confirm dev-proposes /
   governance-merges at 99.2 review.

## Out of scope

- Verification mechanics of any kind — SIP-0096 owns evidence integrity; SIP-0098 owns
  criteria/contract, including frozen-surface enforcement and behavioral probes.
- Where builds/tests execute — SIP-Externalized-Build-Sandbox (composes cleanly; the
  skeleton gate runs on plain CI runners regardless).
- Universal manifest for novel architectures (SIP §6 non-goal; CRUD-shaped apps first).
- Opinionated app design in templates (invariant substrate only — the "identical regardless
  of what the app does" test).
