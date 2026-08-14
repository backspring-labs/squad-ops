# Implementation Plan — Deterministic Verification Scaffolding with Semantic Fill Slots

**SIP:** `sips/proposed/SIP-Deterministic-Verification-Scaffolding.md` (rev 2, PR #885)
**Status:** plan drafted ahead of acceptance; the owner's pull-in trigger fired 2026-08-13 (roll 17 — third consecutive roll where the app passed its probes and build while the freshly generated qa suite failed on new mechanical mistakes).
**Ordering principle:** sequencing and exit criteria only, no dates. Each phase lands as its own PR with incremental commits; nothing merges without the owner.

## Why now (one paragraph, then the ledger reference)

The generated test suite is the last artifact whose boilerplate — imports, function-call shapes, file placement, response-field paths — is re-invented by an LLM every roll. Across rolls 9–17 that layer produced a different small mistake nearly every generation, while every deterministic layer added this release stayed reliable and the apps themselves converged. The SIP moves the boilerplate into the scaffold (pre-written, frozen, derived from the same manifest facts the probes already use) and leaves the qa author only the judgment content: assertion bodies. The full failure catalog is in the SIP's §3; the roll-by-roll record is the v1.6 ledger.

## Phase 0 — Acceptance mechanics (owner + maintainer)

The SIP's acceptance evidence section (§10.4) currently requires a *closed* Stage 1e ledger. Implementing before 1e closes therefore needs a pre-acceptance amendment, made in the open per the SIP's own discipline:

- Amend §10.4: the baseline corpus is the **open** 1e ledger through roll 17 (the trigger the owner named — repeated mechanical suite deaths despite the guidance and routing fixes — is the amendment's evidence).
- Owner accepts: `update_sip_status.py` assigns the number; body H1/Status synced by hand (known papercut).
- Exit: SIP numbered in `sips/accepted/`, amendment section in the SIP itself (not only here — plans are superseded at the cut; the SIP is permanent).

## Phase 1 — Scaffold emission (the generator; the bulk of the work)

Extend the nextjs_ts stack expansion (`stack_nextjs_ts.py` / the `expand()` seam) to additionally emit a test scaffold:

- One scaffold suite file (e.g. `__tests__/api.test.ts`), scaffold-owned, containing one **behavior shell** per contract-derived behavior (create → declared success status, blank rejection → the derived rejection status, not-found → declared 404, one per declared endpoint). Every shell carries: imports resolved against the actual expanded tree (bracket directories included), `beforeEach(reset)`, the invocation call pre-written (`new Request(...)`, the `{ params }` argument for dynamic routes), the declared-status assertion, and a **fill slot** for domain assertions with a stable `slot_id` bound to the criterion/probe id it derives from.
- A **scaffold manifest** artifact: frozen file list, per-file spine hashes computed with slot bodies elided, and the slot table (`slot_id` → file, region, bound criterion).
- **Derivability rule enforced in code**: any element the generator cannot derive from the manifest/tree/criteria pack is demoted into the slot, never frozen as a guess.

Exit criteria:
- Byte-equivalence pin: reference manifest + generator → byte-identical scaffold (the same test shape that pins the app scaffold).
- The scaffold **with empty fills collects cleanly** under `vitest run` in the agent image (extends the existing frozen-harness proof).
- Stack #1 contract and manifest hashes unmoved; stack #1 emits no test scaffold (opt-in is per-stack and explicit).
- Mutation checks: removing a derivation source (e.g. an endpoint's declared status) changes the scaffold deterministically or fails generation — never silently guesses.

## Phase 2 — The validity gate (rails before the author sees it)

At seed time, before any qa authoring: verify every import resolves, every referenced handler exists in the expanded tree, every asserted status exists in the contract, and the empty-fill scaffold collects. A failure **fails run setup loudly** (the same posture as a missing build profile) — it must never consume an LLM correction round.

Exit: mutation tests — break each derivation, assert run setup fails with the named cause.

## Phase 3 — `qa.test` fill mode (the author's new surface)

When the workspace carries a valid scaffold:

- eve's envelope presents the scaffold with its slots plus a **semantic brief**: the list of behaviors the deterministic layer already covers (derived free from the slot table), framing her job as residual semantics — state effects, cross-operation behavior, edge cases. Richer brief content is follow-on work, per the SIP.
- eve emits **slot fills only** (plus optional additive test files under the existing rules: declared dependencies, in-process execution, no frozen-file edits). The merge of fills into scaffold files happens deterministically on the framework side.
- Structural consequence to pin in tests: zero-byte emissions, invented fence paths, and wrong placement can no longer produce a broken suite — a bad fill degrades one slot.

Exit: envelope test (slots + brief present), fill-merge round-trip test, and a test demonstrating a garbage fill emission still yields a collecting suite with only that slot failing.

## Phase 4 — Region-level enforcement (the spine stays frozen)

Whole-file freezing exists (SIP-0100 §2.4); slots inside frozen files need region-level verification:

- On every stored emission touching a scaffold file: recompute the slot-elided spine hash; a frozen-region mutation is rejected and restored, with a structured scaffold-violation signal riding the existing enforcement-carry transport.
- No repair path — any role, any locus — may edit frozen regions. This closes at region level what the ownership veto (#886) closed at file level, and it is required for honesty: without it, spine integrity would rest on prompt compliance, which is the lottery this SIP exists to end.

Exit: mutation tests — a fill emission that rewrites an import or invocation is restored and signaled; the repair path cannot mutate the spine.

## Phase 5 — Failure attribution and routing

`tests_pass` evidence rows carry slot ids, so failures split into the SIP's four classes with distinct routing:

- **scaffold-invalid** → generator defect, run-setup failure (never an LLM round);
- **app-contract** (a frozen shell's status assertion fails) → dev repair — and a shell failure and its bound probe's failure deduplicate on the shared criterion id (one defect, one round);
- **fill failure** → qa repair, slot-scoped;
- **infrastructure** → environment triage.

Exit: routing tests per class; the shell/probe dedupe test; the run report's per-layer counts (scaffold-derived, authored fills, additive tests, unique findings by layer — the SIP §6 evidence).

## Phase 6 — Live validation

Deploy, then roll. Success reads per the SIP's own criteria:

- The validity gate is green on every scaffold emission (structural criterion, checked every roll from here on).
- The roll's suite cannot die mechanically; whatever fails is attributable by layer.
- **1e credit is unchanged by this SIP**: a green roll still boot-validates via `audit_delivered_app.py` before Stage 1e closes — shells prove manifest-consistency, not intent, and the SIP says so (§4/§6). The N=6 zero-mechanical-death window keeps accruing across subsequent rolls; it is the SIP's promotion evidence, not 1e's gate.

## Scope boundaries

- nextjs_ts only; stack #1 untouched until its pack opts in (all-or-nothing opt-in per the SIP §8).
- Follow-on work stays out (SIP §12): inference-generated semantic briefs, the full QA evidence schema, the promotion workflow, cross-stack scaffolds.
- No changes to probes, `tests_pass` credit semantics, or SIP-0096.

## Roll policy while building

No new rolls until Phase 3 deploys — each roll costs ~2.5h against odds this work exists to change. Roll 17 stays failed-and-resumable as a fallback specimen; if the owner wants lottery draws in parallel, resuming it is cheap and independent of this plan.

## Phase → effort shape (not dates)

P1 large (generator + manifest + pins) · P2 small · P3 medium (envelope + merge path) · P4 medium (region hashing + enforcement wiring) · P5 medium (routing + evidence) · P6 = a roll. P1→P2→P3 are strictly sequential; P4 and P5 follow P3 and can interleave; the minimal honest deploy for a roll is **P1–P4** (P5's attribution improves convergence but existing qa-side repair routing already works).
