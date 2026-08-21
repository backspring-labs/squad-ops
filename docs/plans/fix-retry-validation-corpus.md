# Fix-Validation Retry Corpus

**Purpose:** map banked cycles (failed AND control-greens) to the post-window fixes they
validate via `squadops runs retry` — which re-runs the implementation against the cycle's
completed framing, holding the authored recipe constant so a machinery change is
attributable to the fix, not to fresh authoring dice. Grows per V38 roll; finalized at
window close for the fix-program conversation.

**Post-window status (2026-08-21):** v1.6.1's first batch is MERGED AND DEPLOYED — #1017
(failed retest report persisted), #1014 (emission-side ownership veto), #1011 (base-path
completion clamp) — and **#1012 is CLOSED by offline adjudication** (code read + sandbox
replay, see the issue's closing comment): the repair DOES reach the retest tree
(materialization is last-write-wins with patched files written after sources), the stored
trees replay green, and the red retests failed inside the UNSTORED additive tests —
collateral breakage from broad re-emissions, then correct rejected-candidate exclusion.
Several C-rows' questions are therefore answered without any retry; rewritten below. The
retry program becomes the validation arm of 1.6.2 (#1013, #1015, #761, #1021, #1022).

**Retryability caveat (#880), now load-bearing:** `runs retry` works only when the prior
run was cancelled while RUNNING. That is C6's condition exactly; C1–C5's implementation
runs FAILED, so they need the `runs resume` path (or a #880 fix) — verify per candidate
before scheduling.

**Rules:** every retry is a declared diagnostic, never a window roll; nothing here amends a
banked figure. Prefer mechanism-level observables (yes/no facts about machinery behavior)
over outcome-level (green/red — still subject to implementation dice). Retries run under
the cycle's own squad profile, so each arm validates against its own model.

## Candidates

### C1 — V38 arm-B roll 1 · `cyc_02e9af402c82` · FLAGSHIP (dual-fix subject)
Framing: **internally contradictory** (manifest 201 vs plan 200 for create — #1013), so
"solid" is exactly what it is not, and that is its value. Failed: dev faithfully built the
plan's 200; contract judged 201; then **the landed 201 repair vanished by round 3**
(#1012; #994 family). Also exercised: evidence gaps (#971/#995).
**Retry value, rewritten post-adjudication:** (a) after the **consistency gate** (#1013):
retry must be *refused at plan validation* — the gate's acceptance test; (b) ~~repair
threading~~ **ANSWERED OFFLINE** — the repair reached the tree; the loop's non-convergence
is the collateral-breakage mechanism, so the live watch becomes **#1015**: post-minimality,
the repair should be a one-file patch that converges; (c) with 1.6.1 already deployed, any
red retry additionally validates **#1017** (failed retest report banked, naming the failing
test) and **#1014** (no qa-owned file stored from a dev repair; veto log line), and every
repair validates **#1011** (completion tokens ≤ 8,192).
Note: a machinery-only retry on this framing fails by design — the framing is the defect.
Retry path: impl run FAILED → needs `runs resume` semantics (#880 caveat above).

### C2 — V7 attempt-1 roll 1 · `cyc_8b569ce34074` (void, framing solid)
The original #994 exhibit: correct accepted repair (`force-dynamic`), develop re-dispatch
discarded it, then timeout + thinking-cap zero-emission (#998). Boot audit PASSED — app
worked. **Retry after #994 fix, watch:** accepted repair survives re-dispatch; after #998
fix: cap-exhaustion classified distinctly. (3.6 arm — validates the fix under the incumbent.)
**Still valid post-#1012-closure:** #994 is the REWIND path (develop re-dispatch discarding
an accepted repair) — a different mechanism from the closed patch/retest question, and
still open. C2 remains its subject.

### C3 — V7 attempt-2 slot 1 · `cyc_6495d9870587`
Additive-suite network-call class (#877 family): suite fetched a nonexistent server, 3
qa repairs no convergence; detector-flaggable self-mocking file never flagged in-cycle
(#1002). App passed audit. **Retry after additive-containment fix (now filed: #1022), watch:** the network
call rejected deterministically at emission with a named finding (not vitest noise);
after #1002: `inspected` present in banked rows.

### C4 — V7 attempt-2 slot 4 · `cyc_2913ae7abd67`
Second sample of C3's class (independent framing). Same watches; two-sample coverage
guards against fixing to one framing's shape.

### C5 — V38 shakedown #2 · `cyc_bc85a4b81808` (non-counting; framing solid)
Pure app-semantic failure under 3.8 (join-duplicate 200≠409, leave 404) with clean
machinery; **first non-working delivered app of the arc**. **Retry after status-discipline
prompt teaching, watch:** initial-emission declared-status conformance (outcome-leaning;
weaker, but the cleanest 3.8 subject for it). Also the repair-clamp fix (#1011): repair
emissions bounded ≤ 8,192.

### C6 — V38 arm-B launch 2 · `cyc_032043b05440` (VOID — host power loss) · **#1015 flagship**
Framing carries the #1013 contradiction on **one** endpoint only (`POST /api/runs/seed`:
manifest + probe 201, dev brief 200) — everything else consistent — so the run isolates a
**single one-line defect** and the whole correction loop is spent on it. That isolation is
what makes it a better repair-threading subject than C1, whose cascade muddied attribution.
**Banked facts, re-read under the adjudication:** round-0 repair stored `status: 201`
(`art_759c337e35b9`, 21:56:35 UTC); a fresh full `qa.test` ran 4.5 min *after* that store and
the analyzer still measured 200. The pre-adjudication inference ("the repair reaches the
vault, not the tested tree") is now REFUTED as a general claim: the retest tree receives
the repair (write-order + replay, #1012's closing comment), the retest rejected the
candidate on collateral breakage, and the fresh `qa.test` correctly excluded the rejected
candidate — both banked facts are the designed behavior of a rejected repair. What made
this roll red is the broad re-emission, which is exactly #1015's subject, and the isolated
one-line defect is what makes C6 its cleanest flagship.
**Retry value, rewritten post-adjudication:** (a) ~~does the stored 201 reach the retested
tree~~ **ANSWERED OFFLINE — yes** (write-order proof + green replays; the fresh qa.test
measuring 200 afterward is the provenance rule correctly excluding a REJECTED candidate);
(c) ~~31 s vs 4.5 min~~ **ANSWERED — designed**: the retest is execute-only (no LLM
authoring), same runner. What remains, and makes C6 the **#1015 flagship**: the isolated
one-line defect means a minimal post-#1015 repair should converge in one round — repair
emission file count (expect 1, was 7–8) and round count are the observables; plus (b)
unchanged: after the **consistency gate** (#1013) — retry must be refused at plan
validation, the second independent framing for that gate's acceptance test.
Expected retryable: its implementation run was cancelled **while `running`** (the zombie
clear), which is the condition under which `runs retry` works (#880). Unverified until tried.

### Controls (must STILL pass after fixes — regression guards)
- **V7 slot 3 · `cyc_6b2af126b68d`** — the repair-then-pass green (#1001's live proof).
  A post-fix retry regressing this to red = the fix broke convergence.
- **V7 slot 2 · `cyc_5fb50579c418`** — zero-correction green; fastest clean path. Guards
  the happy path against fix side-effects.

### Excluded, with reasons
- V7 attempt-2 launch 3 (`cyc_16bbfe29464f`) — framing NOT solid (plan validation rejected
  it at the gate); retry would re-reject identically. Correct behavior; nothing to validate.
- V38 shakedown #1 (`cyc_cc83a907f09e`) — framing usable but its implementation era
  predates #1008; superseded by C5 for every 3.8 mechanism.

## Fix → candidate matrix (running)

| Fix | Status | Validated by | Mechanism observable |
|---|---|---|---|
| ~~Repair-state threading (#1012)~~ | **CLOSED — adjudicated offline**, no retry needed | — | repair reaches the tree (write-order + replay); non-convergence = collateral breakage |
| Rewind discards accepted repair (#994) | open | C2 | accepted repair survives develop re-dispatch on the REWIND path |
| Repair minimality/targeting (#1015) | 1.6.2 | **C6 (flagship)**, C1 | repair emission = 1 file (was 7–8); one-round convergence on the isolated line |
| Manifest↔plan consistency gate (#1013) | 1.6.2 | C1, **C6** | retry refused at `system:plan_validation` (two independent framings) |
| Failed retest report persisted (#1017) | **DEPLOYED (1.6.1)** | any red retry | failed retest's `test_report.md` in the vault, failing tests named |
| Emission ownership veto (#1014) | **DEPLOYED (1.6.1)** | C1, C6 | veto log line; no qa-owned file stored from a dev repair |
| Repair clamp (#1011) | **DEPLOYED (1.6.1)** | C5, C1, any repair | repair completion_tokens ≤ 8,192 |
| Failure-signature subject (#761) | 1.6.2 | any multi-round retry | REPEAT vs SHIFTED distinguishable per round |
| Compile-credit bookkeeping (#1021) | 1.6.2, read-first | slot-5 replay (banked; no retry needed) | dropped `vc-compiles-*` credited or disclosed, never silent |
| Additive-suite containment (#1022) | 1.6.2 | C3, C4 | deterministic named rejection at emission |
| `inspected` provenance (#1002) | open | C3, C4 | inspected list on authenticity rows |
| Failed-task evidence banking (#971/#995) | #1017 slice landed; rest open | C1 (+ any red retry) | attempt history & additive-suite files queryable post-run |
| `execution_evidence` persistence (#999) | open | any retry with fills | assertion strength queryable |
| Status-discipline teaching | unscheduled (model-side) | C5 (+ arm-B rolls TBD) | initial-emission status conformance |
| ~~`retest` vs full `qa.test` tree assembly~~ | **ANSWERED** — execute-only by design | — | — |
| Regression guards | standing | Controls | still green, still zero/one-round |


*(Arm-B counted rolls join as they land, tagged by mechanisms exercised. Voided rolls are
admissible here — a void does not score, but its banked evidence is as good as any.)*
