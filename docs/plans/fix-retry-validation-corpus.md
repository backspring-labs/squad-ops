# Fix-Validation Retry Corpus

**Purpose:** map banked cycles (failed AND control-greens) to the post-window fixes they
validate via `squadops runs retry` — which re-runs the implementation against the cycle's
completed framing, holding the authored recipe constant so a machinery change is
attributable to the fix, not to fresh authoring dice. Grows per V38 roll; finalized at
window close for the fix-program conversation.

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
**Retry value, two-stage:** (a) after the **consistency gate** (#1013): retry must be
*refused at plan validation* — the gate's acceptance test; (b) with the gate waived, after
the **repair-threading fix**: does the re-dispatched qa see the accepted repair, and does
the loop converge on a probe-named fix? (c) post-evidence-fix: attempt history banked.
Note: a machinery-only retry on this framing fails by design — the framing is the defect.

### C2 — V7 attempt-1 roll 1 · `cyc_8b569ce34074` (void, framing solid)
The original #994 exhibit: correct accepted repair (`force-dynamic`), develop re-dispatch
discarded it, then timeout + thinking-cap zero-emission (#998). Boot audit PASSED — app
worked. **Retry after #994 fix, watch:** accepted repair survives re-dispatch; after #998
fix: cap-exhaustion classified distinctly. (3.6 arm — validates the fix under the incumbent.)

### C3 — V7 attempt-2 slot 1 · `cyc_6495d9870587`
Additive-suite network-call class (#877 family): suite fetched a nonexistent server, 3
qa repairs no convergence; detector-flaggable self-mocking file never flagged in-cycle
(#1002). App passed audit. **Retry after additive-containment fix, watch:** the network
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

### C6 — V38 arm-B launch 2 · `cyc_032043b05440` (VOID — host power loss) · **cleanest #1012 subject**
Framing carries the #1013 contradiction on **one** endpoint only (`POST /api/runs/seed`:
manifest + probe 201, dev brief 200) — everything else consistent — so the run isolates a
**single one-line defect** and the whole correction loop is spent on it. That isolation is
what makes it a better repair-threading subject than C1, whose cascade muddied attribution.
**What it already proves without any retry:** round-0 repair stored `status: 201`
(`art_759c337e35b9`, 21:56:35 UTC); a fresh full `qa.test` ran 4.5 min *after* that store and
the analyzer still measured 200. The repair reaches the vault, not the tested tree — the
disjunction C1 left open ("blind re-dispatch **or** round-3 regression") resolves to the
former.
**Retry value:** (a) after the **repair-threading fix** (#994/#1012) with the #1013 gate
waived — does round 0's stored 201 reach the retested tree? A single mechanism-level
yes/no on an isolated one-liner; (b) after the **consistency gate** (#1013) — retry must be
refused at plan validation, a *second independent framing* for that gate's acceptance test
(C1 is the first; two framings guard against fixing to one shape); (c) the `retest` path
returned in 31 s where a real `qa.test` takes ~4.5 min — retry is the cheapest way to see
whether that path assembles the same tree.
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

| Fix | Validated by | Mechanism observable |
|---|---|---|
| Repair-state threading (#994/#1012) | **C6 (primary)**, C1, C2 | accepted repair visible to subsequent dispatch — C6 isolates it to one line |
| Manifest↔plan consistency gate (#1013) | C1, **C6** | retry refused at `system:plan_validation` (two independent framings) |
| Failed-task evidence banking (#971/#995) | C1 (+ any red retry) | attempt history & retest detail queryable post-run |
| `execution_evidence` persistence (#999) | any retry with fills | assertion strength queryable |
| `inspected` provenance (#1002) | C3, C4 | inspected list on authenticity rows |
| Additive-suite containment | C3, C4 | deterministic named rejection at emission |
| Status-discipline teaching | C5 (+ arm-B rolls TBD) | initial-emission status conformance |
| Repair clamp (#1011) | C5, C1 | repair completion_tokens ≤ 8,192 |
| `retest` vs full `qa.test` tree assembly | C6 | retest assembles the same tree a full run does |
| Regression guards | Controls | still green, still zero/one-round |


*(Arm-B counted rolls join as they land, tagged by mechanisms exercised. Voided rolls are
admissible here — a void does not score, but its banked evidence is as good as any.)*
