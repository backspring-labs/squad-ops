# Open-Issue Sweep — 2026-08-21 (post-1.6.0 cut, post-V38 window)

Successor to the 2026-08-04 sweep for the 1.6.x / 1.7 populations. Taken against 76 open
issues immediately after the v1.6.0 cut, the V38 window close, and the v1.6.1 first batch
(#1017 #1014 #1011 deployed; shakedown in flight at sweep time). Assignments follow the
release-cadence convention: patch lane = small/urgent fixes and the correction-loop/
framing hardening the measurement windows earned; 1.7 = the odd-minor stabilization slate
under its assigned identity (*every port is actually a port*), feature-free by rule;
feature-shaped work → the 1.8 lane regardless of how fix-like it reads.

**Sequencing pins (evidence-backed):**
- **#972 jumps the queue** — the regression script's silent-no-ruff exit produced a false
  green at the v1.6.0 cut itself (caught only because the pipe-masked exit was re-run).
- **#880 jumps the queue** — `runs retry` being broken by construction gates the
  fix-validation retry program (`fix-retry-validation-corpus.md`), which is the validation
  arm for the entire 1.6.x line.
- The 1.6.x lane touches no executor/port boundary and 1.7's slate touches little of the
  correction loop — the two lanes can run without coordination tax.

## 1.6.2 — the slated core + three additions

| Issue | Rationale |
|---|---|
| #1013 | manifest↔plan consistency (+ completeness of contract-enforced facts in briefs) gate — framing-internal defects cost 2 counted V38 rolls; deterministic, at the existing `system:plan_validation` seam |
| #1015 | repair minimality / analyzer-scoped targeting / attempt counter — carries the prevention burden from #1012's closure (collateral breakage in broad re-emissions is the adjudicated mechanism) |
| #761 | `tests_pass` signature subject/reason — REPEAT vs SHIFTED; feeds #1015-C; signature-level sibling of the shipped #1017 |
| #1021 | compile-credit accounting gap — read-first; slot-5 replay is the banked zero-repair reproducer |
| #1022 | additive-suite containment — every V7 counted red was an unconstrained additive test; gate-not-guidance (guidance half #877/#879 proven insufficient by C3) |
| #972 (add) | lint gate silently absent without venv — bit the 1.6.0 cut |
| #880 (add) | retry-by-construction fix — unblocks the corpus retry program |
| #1002 (add) | `inspected` provenance — same detectors/seam as #1022 |

Decision-needed, 1.6.x-eligible: **#933** (fill-mode vs plan-authored qa deliverable) — its
issue thread is already decision-ready with two named fix sites; needs an owner ruling,
then it slots wherever the ruling implies.

## 1.6.3 — correction-loop evidence completion (the #971/#995 class)

| Issue | Rationale |
|---|---|
| #971 | persist failed-task emissions — the additive-suite files whose absence forced #1012's offline replay; provenance care required (failed emissions must never enter workspace views — the #1017 precedent) |
| #995 | timeout mid self-eval banked as zero-chars, erasing real history |
| #998 | thinking-cap exhaustion indistinguishable from generic emission failure |
| #999 | `execution_evidence` computed then never persisted |
| #994 | rewind path discards an accepted repair — distinct from the closed #1012 (patch path); corpus C2 is its banked subject |
| #969 | qa.test_repair missing-brief (fill protocol + execution model) — same fix shape as pf-31's repair-mixin threading |
| #968 + #788 | one bounded slice: deterministically reject analyzer claims naming nonexistent files/symbols — also the safety rail #1015-A's narrowing rule leans on; the full analyzer-verification question stays open beyond the slice |
| #947 | qa self-eval fill-blindness — 68% of the qa task wall clock spent emitting a file the guard discards |
| #924 (evidence half) | record the discarded reasoning-channel emission; the budget-behavior half belongs to 1.7's #927/#410 cluster |

## 1.6.4 — framing / scaffold determinism

| Issue | Rationale |
|---|---|
| #772 | contract/scaffold default success-status disagreement → unwinnable contract; slot-6's omission cousin |
| #795 | `error_contract.shape` declared, read by nothing; scaffold hardcodes a different envelope |
| #913 | shells pin status but not response-body paths — re-invented per fill |
| #939 | no unresolved-name guard for the nextjs_ts stack (`undefined_names` is .py-only) |
| #668 | DOM testid enforcement layer — the same gate-not-guidance argument as #1022, fay-14 lineage |
| #930, #901 | trivia riders (boot logs wrong model; temperature-without-top_p config seam) |

## 1.7.0 — stabilization slate, confirmed live against the ROADMAP identity

- **Boundary/vocabulary leaks:** #377, #381, #305, #559 (residual `task_type ==` sites),
  #922 (three meanings of "capability" — before packs freeze the word), #225 (joi id)
- **Composition-root cluster (design gate before code):** #301, #154, #286
- **Provider neutrality / Atlas groundwork:** #410, #927, #929, #944 (delete the dead
  LLMRouter in passing), plus #924's budget half
- **Wide infrastructure mechanics:** #576, #577, #574, #575, #567, #579, #578, #300,
  #330, #560, #352, #353, #581
- **Packaging fidelity:** #198, #582, #637, #598
- **CI/test debt:** #237 (py3.12), #242, #157, #176, #580
- **Explicit deferrals landing here:** #820 (SIP-0103 §3.3 self-consistency proof),
  #376 with SIP-0102 migration steps 3–7 (in-cycle final-state verification)
- **Design work routed to its own review, not a slate:** #557 (post-retest governance
  review — SIP drafted), #414 (correction-budget reserve design)

## Feature-shaped — 1.8 lane, not fix packs

#950 (plan-gate review packet), #949 (feedback-scoped restart boundary), #194 (SIP-0093
B′ revision loop), #80 (cycle lineage fields — wanted BY the scorecard, so it ships with
the scorecard), #316 (request-profile taxonomy — moved with Campaign per the ROADMAP).

## Verify-then-close

- **#822** — the S2 nextjs_ts stack landed 2026-08-10 and SIP-0105's acceptance gate is
  met; the thread carries stage-tracking residue. One read to confirm no live remainder.
- **#936** — "every documented fill fails," yet nine window rolls filled successfully;
  either fixed en route (close with the fixing commit named) or the appendix drifted back
  (then it joins 1.6.4).

## Supersession

For the 1.6.x and 1.7 populations this sweep supersedes the 2026-08-04 sweep's
assignments. The 08-04 sweep's standing rules (ops-rider quota, defer-with-named-trigger)
remain in force unchanged.
