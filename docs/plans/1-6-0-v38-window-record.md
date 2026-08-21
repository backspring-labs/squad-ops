# V38 Model-Comparison Window — Record

**Pre-registration:** `1-6-0-v38-model-comparison-preregistration.md` (in force at the §3
freeze, `5d66f80f`). **Arm A:** V7 (amended 4/6, `1-6-0-v7-fay-window-record.md`). **Arm B:**
six counted rolls on `full-38` (qwen3.8:27b, Ollama 0.32.14) recorded here. No pass/fail
bar; texture is the instrument. This file lives on a branch until the window closes (§6).

## Shakedown — NON-COUNTING (declared per §2.6 before launch)

Bar: the cycle reaches a verdict without a NEW harness-attributable mechanical failure.
Watching for the model-swap failure surface: structured-output compliance, fence discipline,
thinking behavior (#998 class), emission shape under the 0.32 thinking routing.

| Field | Value |
|---|---|
| Cycle | `cyc_cc83a907f09e` (run `run_0a037698a5c5`), launched 2026-08-20, config hash matches pin |

### Shakedown #1 outcome (cyc_cc83a907f09e, deploy 5d66f80f) — findings, both fixed

Framing 34 min (vs 54–73 on 3.6); implementation failed in 17 min. Findings: (1) squad-output
texture — dev named-imported next/link's default export, repeated across 3 self-eval rounds;
(2) **harness×model**: analyze_failure emitted a mid-object-truncated JSON once (703 tokens,
uncapped, 0-for-3 reproducible), parser rejected loudly, correction ran decisionless, run
collapsed; (3) **harness**: qwen3.8:27b had no model-registry entry → completion clamp never
fired → arm B ran at capability ceilings (12,000) arm A never had, an undeclared inter-arm
delta. Owner ruled fix-refreeze-shakedown-open; #1008 merged (registry clamp parity 8,192 +
one bounded JSON re-ask across the three JSON impl handlers); §3 re-frozen at `f7a5e0a2`.
In-cycle throughput on 3.8: 22.6–34.4 t/s (vs 10.5–10.9 on 3.6).

## Shakedown #2 — NON-COUNTING (declared per §2.6 before launch)

Same bar: reach a verdict with no NEW harness-attributable mechanical failure. Additionally
watching: recurrence of the truncation (now survivable via re-ask — a fired re-ask is a
logged observation, not a failure) and the clamp taking effect.

| Field | Value |
|---|---|
| Cycle | `cyc_bc85a4b81808` (run `run_59b59cf49f05`), launched 2026-08-20, hash matches pin |

### Shakedown #2 outcome — BAR MET; declaration; WINDOW OPENS

Framing 32 min (gate: one question → §7.3(c) verbatim, agent decision); implementation
failed 19:02 UTC, "Max correction attempts (3) exhausted," `rejected`.

**The bar was "reach a verdict with no NEW harness-attributable mechanical failure" — MET:**

- No truncation recurrence; the #1008 re-ask never needed to fire; every analyzer/decision
  parse succeeded.
- The clamp held on capability tasks (eve capped at exactly 8,192).
- The machinery cycled correctly through a builder failure → builder repair, and qa failures
  → dev-routed corrections (locus correct: the probes said the APP was wrong).
- Every failure was **app-semantic, squad output**: duplicate join accepted (200 ≠ 409),
  leave broken (404 ≠ 200) — which is the quantity the window MEASURES, not a precondition.

**Declared under §2.6 (not fixed):** repair handlers bypass the per-model completion clamp
(a dev repair emitted 12,314 tokens) — pre-existing and **symmetric across both arms** (V7's
repairs ran the same uncapped path and self-limited), so it does not bias the comparison.
Filed #1011 for the post-window queue.

**Texture preview, recorded:** shakedown #2's delivered app **fails its own probes at boot**
(duplicate-join and leave) — the first non-working delivered application of the entire arc,
after 9/9 working under 3.6. Non-counting, but the first observed instance of a failure
class arm A never produced.

## WINDOW OPEN (2026-08-20, deploy `f7a5e0a2`)

All §2 preconditions hold. Six counted arm-B rolls follow, §5.1 rules inherited, no bar,
texture as instrument, §6 freeze in force from here.

## Arm B rolls

| Launch | Cycle | §5.1 | Score |
|---|---|---|---|
| 1 | cyc_02e9af402c82 | COUNTED | not functional |
| 2 | cyc_032043b05440 | **VOID** (host power loss) | — |
| 3 | cyc_410f3a9257f8 | COUNTED (slot 2) | **FUNCTIONAL** |
| 4 | cyc_5267fb2ead60 | COUNTED (slot 3) | **FUNCTIONAL** (zero-correction) |
| 5 | cyc_60407deffa98 | COUNTED (slot 4) | **FUNCTIONAL** (converged on correction round 3 of 3) |
| 6 | cyc_83577bc3052b | COUNTED (slot 5) | **FUNCTIONAL** (zero-correction) |

### Roll 1 — cyc_02e9af402c82 — COUNTED, not functional

| Field | Value |
|---|---|
| Framing | 38 min; gate auto-approved |
| Implementation | `run_9733f845dedd` — failed 20:47 UTC (63 min), max corrections (3) exhausted |
| Verdict | `rejected` — 32 executed / 27 passed; failed: create probe (**200 ≠ declared 201**) + 3 downstream probes (cascade: `{run_id}` never captured) + `tests_pass` |
| Correction rounds | 3 — locus-correct dev-chain repairs (suite executed and failed → subject implicated); patch verification passed each round, retests stayed red |
| Boot audit (separate fact) | **FAIL — identical cascade. The delivered app genuinely violates its contract** (create returns 200, not 201) |
| Manual interventions | none |
| Tokens (impl, completion, by role) | neo 119.9k · eve 58.1k · max 14.8k · data 10.7k · bob 8.4k — total ~212k |
| Wall-clock | 1h41m total (fastest full roll of either arm) |

Texture, corrected twice as triage deepened — final attribution (#1012, #1013):

1. **The initial red is FRAMING-rooted, not implementation-rooted.** The manifest declares
   `success_status: 201`; the implementation plan's own dev criterion says *"returns 200"*.
   Neo built his brief faithfully; the contract judged him by the manifest. A framing-
   internal contradiction — authored by 3.8 in one session — with no gate that checks
   manifest↔plan consistency (#1013). A V7 green framing, checked as contrast, said 201 in
   both places. The status-discipline model claim now rests only on shakedown #2's 409
   (taught correctly, missed anyway — genuine slip).
2. **Recovery was then prevented by the machinery**: rounds 1–2 emitted the 201 fix
   (stored, patch-verified) and it vanished by round 3 (#1012 — re-dispatch blind to the
   accepted repair, or round-3 regression; unadjudicable from banked evidence, fourth
   instance of the evidence-dropped family). The final additive suite was contract-correct
   (201 on create), so the suite was satisfiable — the app the suite saw was not the
   repaired one.

So roll 1's counted red = 3.8 authoring self-contradiction (measured stack, model side)
× correction-loop state loss (harness, symmetric). Both named, per the standing rule.

### Launch 2 — cyc_032043b05440 — VOID (host power loss mid-run)

| Field | Value |
|---|---|
| Framing | `run_c3c0c8872424`, 38 min (20:49–21:27 UTC); gate approved 21:29 UTC, §7.3(c) text verbatim, recorded as an agent decision |
| Implementation | `run_d0a0ed285029` — started 21:29 UTC; reached correction round 3 of 3; **no verdict** |
| Terminated by | **DGX Spark hard halt, 2026-08-20 22:08:53 UTC (18:08:53 ET)** — 26 s after the round-3 qa dispatch. Journal stops mid-Ollama-generation, no panic, no shutdown records, nothing above UFW noise. Box down 24 min; boot 22:32:55 UTC |
| Progress at halt | 15 tasks complete through checkpoint 15 (define_done, 8 develop, builder.assemble, 2 full correction rounds); 2 plan deltas |
| Manual interventions | none before the halt; run and cycle cancelled afterward to clear the zombie |
| Disposition | **VOID** per the ruling below — neither counts nor resets. Arm-B tally unchanged |

**§5.1 ruling — external host failure is VOID (owner, 2026-08-20).** §5.1 as inherited
names three buckets: *void* (never reaches `qa.test`), *reset* (a **new** mechanical suite
failure attributable to the harness), *counted* (everything else). A host power loss fits
none: the roll did reach `qa.test`, and the crash is not a harness defect. Ruled: **a roll
destroyed by an external host failure before it reaches a verdict is VOID** — recorded and
re-launched, neither counting nor resetting.

The alternative, resuming from checkpoint 15, was rejected on instrument grounds, not
convenience. §5 criterion 3 is *zero manual intervention*; unlike gate approval — a
pre-registered constant applied verbatim to every roll under §7.3(c) — a resume is
roll-specific and cannot be applied uniformly. A resumed roll could honestly be recorded as
a red but could **not** be scored functional if it went green. An instrument that can only
produce reds in one direction is not an instrument. Voiding costs the roll's compute and
keeps the six counted rolls comparable.

#### Observations banked from the voided roll (non-scoring, per §6 reporting-only)

A void does not score, but its evidence is real and two findings sharpen claims already in
this record.

1. **The #1013 framing contradiction RECURRED — two rolls for two.** Roll 2's framing got
   *create* right (manifest, plan and criterion all say 201). It carries the identical
   defect one endpoint over: the manifest declares `success_status: 201` for
   `POST /api/runs/seed` and the derived contract probes `vc-probe-api-runs-seed` for 201,
   while the implementation plan's dev brief for that same route says *"Return 200 with the
   created sample runs."* Neo built the brief; the probe failed `status 200 != expected 201`
   — roll 1's mechanism exactly, on a different route. Roll 1's record could only call this a
   single observation; it is now a **recurring authoring failure mode of the measured stack**,
   and the missing manifest↔plan consistency gate (#1013) is confirmed load-bearing.
2. **#1012 is now ADJUDICABLE, and the earlier framing of it was too weak.** Roll 1 recorded
   the vanished repair as *"re-dispatch blind to the accepted repair, or round-3 regression;
   unadjudicable from banked evidence."* Roll 2 settles the disjunction:
   - 21:36:21 UTC — dev's original seed route stores `Response.json(created, { status: 200 })`.
   - 21:56:35 UTC — **round-0 repair stores `status: 201`** (`art_759c337e35b9`). Patch
     verification returned `unverifiable / no_typed_criteria`; behavioral retest decides.
   - 21:57:06 UTC — the `retest-…-00` path returned FAILED in **31 seconds**.
   - 21:57:06 → 22:01:35 UTC — a **fresh, full** `qa.test` then ran 4.5 min against the app
     *after* the 201 was stored, and the round-1 analyzer read the seed endpoint as **still
     returning 200**.
   - 22:08:03 UTC — round-1 repair stores `status: 201` again; its retest also fails.

   The fix is on disk in the vault and a full retest four minutes later measured the
   unfixed behavior. That observation stands. **The general mechanism I drew from it does
   not — see the correction under slot 2**, which ran the same patch → `patch_verification`
   → retest path and converged. What survives here is narrow and factual: on *this* run, a
   stored repair was followed by a full retest that reported the pre-repair behaviour. What
   does not survive is the inference that the accepted repair never reaches the assembled
   tree as a rule.

   Two adjacent facts recorded, not chased: the `retest` path returned in 31 s where a real
   `qa.test` takes ~4.5 min, so it may not assemble the tree the same way; and round-0's
   repair switched the seed route to a `NextResponse` import, the plausible source of the
   `frontend_build: failed` that appears only in round-1's retest reason.

Neither finding is fixed during the window (§6). Both are pre-existing machinery, symmetric
across arms; the framing contradiction is measured-stack, model side.

#### Post-halt state verification before relaunch

Confirmed before launching the replacement: all seven container images match the §3 frozen
deploy `f7a5e0a2` byte-for-byte (the reboot restarted containers, it did not rebuild —
freeze intact); zero unreleased focus leases; agent queues drained, including one stale
`eve_replies` message (RabbitMQ redelivered the un-acked qa task when eve reconnected at
22:33 UTC, eve ran it and replied FAILED into a queue with no consumer — purged).

### Launch 3 — cyc_410f3a9257f8 — COUNTED slot 2 — **FUNCTIONAL**

Replacement for the voided launch 2. Launched 2026-08-20 23:52 UTC. **Arm B's first
functional roll.**
Config verified identical to roll 1 before launch — `applied_defaults`,
`execution_overrides`, `task_flow_policy` all byte-equal, `resolved_config_hash`
`d4d4f662…` matching the §3 pin. Preconditions at launch (§2.7): zero unreleased focus
leases, nothing in flight, agent queues drained, seven deploy images matching `f7a5e0a2`.

| Framing | `run_8893cd3f5dc0`, 33 min (23:52–00:26 UTC); PRD hash `f744843d…` matches the §3 pin |
| Gate | approved 01:49 UTC, §7.3(c) text applied — **verified byte-identical to the banked launch-2 note by direct comparison**, recorded as the same agent id |
| Implementation | `run_48e4c90d7efa`, 01:49–02:15 UTC — **25 min**, 1 correction round |
| Verdict | **`accepted`** — 36 executed / 36 passed, zero failed; all five behavioural probes green |
| Boot audit (separate fact) | **PASS** — installs, builds, boots, answers all 5 contract probes over real HTTP, and the UI reaches every path it requests (28 files assembled, image `squadops-sandbox-env:fastapi-react-1.4-dev`) |
| Manual interventions | none — the gate is a §7.3(c) pre-registered constant, not an intervention |
| Tokens (impl, completion, by role) | neo 54.2k · eve 12.3k · bob 6.0k · max 4.9k · data 4.5k · nat 0 — total ~81.9k |
| Wall-clock | implementation 25 min (the comparable figure); total not comparable — see the gate-latency note below |
| **Score** | **FUNCTIONAL** (§5: accepted + audit passes + zero intervention) |

**Framing consistency audit — PASS (first clean framing of three under 3.8).** Every status
the implementation plan states matches both the manifest and the derived contract probes:
create 201/201/201, join 200/200/200, join-duplicate 409 (probe) / 409 (plan), leave
200/200/200, blank-name 400/400. No endpoint is declared two ways. This framing also
declares **five** endpoints where launch 2 declared six — it omits the dev-convenience seed
route, which is a scope choice, not a defect: scaffold coverage is measured against declared
endpoints, so 5/5 is self-consistent. Recorded before the gate decision, so the audit
cannot be read as post-hoc.

**Measurement note — gate latency contaminates total wall-clock, not implementation
wall-clock.** This gate sat open **1h23m** (framing done 00:26 UTC, approved 01:49 UTC)
because no watcher was armed after launch. Roll 1's gate auto-approved (~0 latency) and
launch 2's was approved in ~2 min. Gate latency is operator availability, not squad or
machinery behaviour, so **the comparable §4 figure for this roll is implementation
wall-clock; total wall-clock is not comparable to roll 1's 1h41m** and must not be quoted
against it. Remedy applied for the remaining rolls: gate approval is now fired by an armed
watcher using the text read directly out of the banked decision row, which both removes the
latency and makes a §7.3(c) rule-1 deviation mechanically impossible.

**Texture — a clean red that the loop actually fixed.** Round 0's failure was **purely
app-semantic**, the quantity this window measures: join-duplicate returned 200 where the
contract requires 409 (no duplicate check implemented) and leave returned 404 for a name
that had just joined. Because this framing *passed* the consistency audit, the dev's brief
did specify 409 and 200 — unlike roll 1 and launch 2, the squad was told correctly and still
missed it. That is a genuine model-side observation, not a framing artefact.

**Same failure pair as shakedown #2** (duplicate join accepted, leave broken). Two
independent samples of one signature is a texture finding rather than a one-off, and it is
the class the record flagged as one arm A never produced.

**CORRECTION — the launch-2 mechanism claim was too strong.** Launch 2's entry inferred that
an accepted repair "lands in the vault and does not reach the tree the suite assembles."
Slot 2 refutes the general form. It ran the **same** path — `correction_path: patch`, the
same `patch_verification` gate, the same ~30 s retest — and produced
`patch_verification status=passed checks=8` followed by
`patch_retest status=SUCCEEDED passed=True reason=Repaired suite passed`. The repair reached
the tree, the retest saw it, the roll converged in one round and the delivered app passes an
independent boot audit. Two further discriminators I had reached for also fail: the patch
*path* is not the differentiator (all three rolls took it), and typed-criteria presence is
not either (roll 1 had `checks=7 status=passed` and still failed its retest).

So the honest state of #1012 is **narrower than launch 2's entry claimed**: on two rolls a
stored repair was followed by a retest reporting pre-repair behaviour, and on a third the
same machinery worked. A live alternative that the evidence does not exclude — and which the
#971/#995 evidence-dropped family already predicts — is that the fault is in **what the
analyzer is shown** rather than in what the tree contains. Unresolved; it needs a code read
of the retest tree-assembly and analyzer-evidence paths, which is post-window work (§6).

**Verification-integrity disclosures (SIP-0096), recorded not buried:** one non-required
check, `acceptance:frontend_compiles`, is `unverified / missing_tooling` — disclosed, not
credited. And `criteria_verified` lists 12 of 14: the two compile criteria for
`app/api/runs/route.ts` and the join route are absent from the verified list although
nothing failed. Both are the repaired files. Worth a look at whether repair re-storage drops
a file's compile-criterion credit — flagged, non-blocking, reporting-only through the
window.

### Launch 4 — cyc_5267fb2ead60 — COUNTED slot 3 — **FUNCTIONAL, zero-correction**

Arm B's first **first-attempt** green: accepted with no correction round at all.

| Field | Value |
|---|---|
| Framing | `run_b3c402429df4`, 32 min (02:16–02:48 UTC) |
| Gate | **auto-approved** by `system:no_open_questions` at 02:48 UTC — the manifest declared no unresolved decisions. Valid under §7.3(c) rule 2, which states an auto-approving roll is neither treated differently nor disadvantaged; roll 1 approved the same way. Zero latency, and no operator decision exists to disclose |
| Implementation | `run_211e7b08a003`, 02:49–03:05 UTC — **16 min, ZERO correction rounds** |
| Verdict | **`accepted`** — 30 executed / 30 passed, zero failed, zero `required_unmet`, **zero `unverified`** (a cleaner sheet than slot 2, which disclosed one) |
| Boot audit (separate fact) | **PASS** — installs, builds, boots, answers all 5 contract probes over real HTTP, UI reaches every path it requests (31 files assembled) |
| Manual interventions | none |
| Tokens (impl, completion, by role) | neo 30.0k · eve 11.3k · bob 6.8k · max 3.0k · data 0 · nat 0 — total ~51.1k |
| Wall-clock | implementation 16 min; total 49 min — **comparable**, since the gate auto-approved and carries no operator latency |
| **Score** | **FUNCTIONAL** |

**Framing consistency audit — PASS, and more specific than slot 2's.** Create 201, join 200
with 409 on duplicate, leave 200 with 404 for a missing participant; every status matches
across manifest, plan and probes. This framing additionally *teaches the failure slot 2 fell
into*: it spells out case-insensitive, whitespace-trimmed duplicate comparison in the dev
brief. Slot 2's framing said only "duplicate rejected" — and slot 2's dev shipped no
duplicate check at all, costing a correction round. Recorded as an observation, not a
conclusion: **one paired sample is not evidence that brief specificity causes the
difference**, and the honest read is that authoring dice and specificity are confounded
here. Worth watching across the remaining rolls rather than claimed now.

**Running framing-audit tally: 2 consistent (slots 2, 3) / 2 contradictory (roll 1,
launch 2).** The gate that would catch the contradictory half still does not exist (#1013).

**Cost texture:** ~51.1k completion tokens against roll 1's ~212k — a quarter, for a
functional result instead of a rejected one. data and nat spent nothing in implementation,
which is expected on a path with no correction round (analyze_failure never runs).

### Launch 5 — cyc_60407deffa98 — COUNTED slot 4 — **FUNCTIONAL**

Ran unattended overnight: the operator's SSH session dropped at ~03:0x UTC when the client
Mac closed, and the roll reached its verdict with nobody watching. Triaged after the fact
from banked state. **This is not an intervention — it is the absence of one**, and the §5
criterion is satisfied more strictly here than on any prior roll: no operator was present to
intervene even had one wanted to.

| Field | Value |
|---|---|
| Framing | `run_aaf9088aef95`, 31 min (03:05:53–03:36:50 UTC); PRD hash `f744843d…` and `resolved_config_hash` `d4d4f662…` both match the §3 pin |
| Gate | **auto-approved** by `system:no_open_questions` at 03:36:50 UTC — zero latency, valid under §7.3(c) rule 2, as on roll 1 and slot 3. No operator decision exists to disclose |
| Implementation | `run_6387016a969c`, 03:36:51–04:24:54 UTC — **48 min, 3 correction rounds**, converged on the last one |
| Verdict | **`accepted`** — 27 executed / 27 passed, zero failed, zero `required_unmet` |
| Boot audit (separate fact) | **PASS** — 30 files assembled; installs, builds, boots, answers all 5 contract probes over real HTTP, and the UI reaches every path it requests (image `squadops-sandbox-env:fastapi-react-1.4-dev`, contract `6357b2cbf288`) |
| Manual interventions | none |
| Tokens (impl, completion, by role) | neo 43.4k · eve 22.7k · max 8.0k · data 5.6k · bob 3.0k · nat 0 — total ~82.7k |
| Wall-clock | implementation 48 min; total 1h19m — **comparable**, since the gate auto-approved and carries no operator latency |
| **Score** | **FUNCTIONAL** |

Deploy freeze re-verified at triage: all seven container images still match the §3 `f7a5e0a2`
ids exactly (`34126b76ff90` / `865aa7fa2677` / `17c4c315cb98` / `8f21700fb42b` /
`30004c6c1aaf` / `7a3852e0e66b` / `f7833405d0d4`); zero unreleased focus leases; agent queues
drained.

**Framing consistency audit — PASS.** Create 201, blank-field 400, GET unknown id 404, join
200 with 409 on duplicate, leave 200 with 404 for an unknown participant — every status
matches across the interface manifest, the implementation plan's dev brief, and the derived
contract probes. Five endpoints declared, five covered. Post-hoc-ness is moot on this roll:
the gate auto-approved with zero latency, so no operator decision could have been informed by
an audit either way.

**The slot-3 "specificity" observation is CONTRADICTED — and that is the finding.** Slot 3's
entry noted that its framing spelled out case-insensitive, whitespace-trimmed duplicate
comparison in the dev brief where slot 2's said only "duplicate rejected", and slot 2's dev
then shipped no duplicate check at all. It flagged the pairing as confounded with authoring
dice and said so explicitly. **Slot 4 breaks the pairing.** Its brief carries the same
specificity slot 3's did — *"validate non-empty name, reject duplicate case-insensitive with
409"*, plus a manifest `decisions` entry warranting the choice — and neo shipped **no
duplicate-participant detection anyway**. The analyzer's own words at 04:18 UTC: *"The join
route handler fails to implement duplicate-participant detection."* Three correction rounds
to recover it. Brief specificity did not prevent the miss. The honest read is now the
sceptical one slot 3 pre-registered: specificity and dice were confounded, and the dice were
doing the work.

**The duplicate-join miss is now three independent samples** — shakedown #2, slot 2, slot 4 —
across framings that taught it vaguely, specifically, and specifically again. That is a
model-side texture finding on `qwen3.8:27b`, not a framing artefact.

**First roll of either arm to converge on the final correction round.** Rounds 1 and 2 each
produced a repair whose retest still failed (*"Repaired suite still fails (exit 1)"* at
03:59:56 and 04:13:04); round 3's repair was followed by a retest that saw it —
`qa_test_handler suite: framework=vitest executed=True exit_code=0 tests_passed=True
test_files=17`. Roll 1 spent the identical 3-round budget and ended `rejected`.

**#1012 — no new evidence either way, and the ambiguity is worth naming.** Rounds 1–2 here
are shape-identical to roll 1's vanished repair (stored repair → retest reporting the failure
unfixed) but are equally consistent with a repair that was simply insufficient; the two are
not separable from banked state without the tree read §6 already queues. What this roll does
show is that the machinery was **not globally blind on it** — round 3's repair demonstrably
reached the retest. Running count stands at two rolls where a stored repair was followed by a
pre-repair retest, and two (slot 2, slot 4) where the same path worked.

**`correction_policy_override: rewind -> patch` fired on rounds 2 and 3**
(`work_product_rewind_with_unspent_repair`). max chose `rewind` both times after repeated
failure — *"Two prior repair attempts have already failed"* — and policy forced `patch`
regardless. Patch then converged. Recorded as machinery behaviour, symmetric across both
arms, no bearing on the comparison.

**`patch_verification` reported `unverifiable / no_typed_criteria checks=8` on all three
rounds — designed, not a defect.** The #870 file-owned gate resolved 8 criteria owning the
repaired files, found nothing it could reject on, and the failed task (`qa.test`) carries no
typed criteria of its own, so the structurally-unevaluable verdict stands and the behavioural
retest decides (`src/squadops/cycles/patch_verification.py:481`). It differs from slot 2's
`passed checks=8` only in which criteria the failing task owned — not in machinery health.

**Verification-integrity disclosures (SIP-0096), recorded not buried:** one non-required
check, `acceptance:frontend_compiles`, is `unverified / missing_tooling` — disclosed, not
credited, same as slot 2. And `criteria_verified` lists **10 of 15**: the five absent are all
compile criteria, for `app/api/runs/route.ts`, `.../[run_id]/route.ts`,
`.../[run_id]/join/route.ts`, `app/page.tsx` and `app/runs/new/page.tsx`. Nothing failed.
This **sharpens slot 2's flag rather than repeating it**: all five dropped criteria belong to
files the round-3 repair rewrote, but the repair rewrote **eight** files and the other three
(`.../leave/route.ts`, `app/runs/page.tsx`, `app/runs/[run_id]/page.tsx`) kept their credit.
So repair re-storage is associated with dropped compile credit but does not always cause it —
a narrower claim than slot 2's entry implied. Flagged, non-blocking, reporting-only through
the window.

### Launch 6 — cyc_83577bc3052b — COUNTED slot 5 — **FUNCTIONAL, zero-correction**

Arm B's second first-attempt green, and its cheapest and fastest roll.

| Field | Value |
|---|---|
| Framing | `run_0220f24b8f49`, 33 min (09:51:03–10:23:45 UTC); PRD hash `f744843d…` and `resolved_config_hash` `d4d4f662…` both match the §3 pin |
| Gate | **auto-approved** by `system:no_open_questions` at 10:23 UTC — zero latency, valid under §7.3(c) rule 2 (fourth auto-approval of the window: roll 1, slots 3, 4, 5). No operator decision exists to disclose |
| Implementation | `run_654b61665fed`, 10:23:46–10:51:07 UTC — **27 min, ZERO correction rounds** |
| Verdict | **`accepted`** — 30 executed / 30 passed, zero failed, zero `required_unmet`, **zero `unverified`** (matching slot 3's sheet; slot 2 disclosed one) |
| Boot audit (separate fact) | **PASS** — 29 files assembled; installs, builds, boots, answers all 5 contract probes over real HTTP, and the UI reaches every path it requests (image `squadops-sandbox-env:fastapi-react-1.4-dev`, contract `6357b2cbf288`) |
| Manual interventions | none |
| Tokens (impl, completion, by role) | neo 22.0k · eve 14.6k · bob 5.0k · max 1.6k · data 0 · nat 0 — total ~43.2k (framing's trailing `assess_readiness` at 10:23:45 excluded — it belongs to run 1) |
| Wall-clock | implementation 27 min; total 1h00m — **comparable**, auto-approved gate, no operator latency |
| **Score** | **FUNCTIONAL** |

Launch preconditions held (§2.7): zero unreleased leases, nothing in flight, queues
drained, seven images matching `f7a5e0a2`. Launched 09:51 UTC as the first roll of the
resumed-operator chain (the overnight roller script died with the operator's SSH session;
this and slot 6 are launched by explicit per-step operator commands, watcher-driven, same
§7.3(c) mechanics).

**Framing consistency audit — PASS (third consecutive).** Create 201, blank-field 400, GET
unknown id 404, join 200 / 409 duplicate (case-insensitive) / 404 unknown run / 400 blank,
leave 200 / 404 unknown participant / 400 blank — every status matches across manifest, dev
brief, and derived probes; the test-strategy section enumerates the identical ten cases.
Scope choice, not a defect: the runs list renders at `/` directly (3 frontend routes, no
`/runs` redirect split — prior framings declared 4). Self-consistent; the UI data-path audit
measures against declared routes, and passed. Running tally: **3 consistent (slots 2, 3, 5)
/ 2 contradictory (roll 1, launch 2)**; the #1013 gate still does not exist.

**The duplicate-join note, kept honest:** this brief carried the same case-insensitive-409
specificity as slots 3 and 4, and this dev implemented it correctly first-attempt — where
slot 4's dev, given the same words, missed it entirely. Consistent with slot 4's conclusion:
specificity does not determine the outcome; the dice do. Sample stands at 3 misses
(shakedown #2, slot 2, slot 4) across 5 counted-or-shakedown briefs.

**The dropped-compile-credit flag is REFRAMED by this roll — repair re-storage is not the
mechanism.** `criteria_verified` lists 12 of 14; the two absent are the compile criteria for
`app/api/runs/route.ts` and the join route, with nothing failed. Slot 2 associated this
signature with repair re-storage (its dropped criteria were the repaired files); slot 4
narrowed it (all five dropped were repaired files, but three other repaired files kept
credit). **Slot 5 had zero repairs and drops the same class of criteria anyway.** So the
association was coincidental — repaired files are simply API-route files, and API-route
compile criteria appear to drop credit through some path independent of repair. Three rolls
(2, 4, 5), seven dropped criteria, all of them `vc-compiles-*` for API routes or pages,
never a probe or suite criterion, and never a failure — a bookkeeping gap in compile-credit
recording, not an acceptance defect. Flagged for the post-window queue (#/6): worth one code
read of how per-file compile credit is recorded at storage time. Reporting-only through the
window.

### Launch 7 — cyc_cac1e479a462 — COUNTED slot 6 (final) — IN FLIGHT

Launched 10:54 UTC; framing `run_bcd02690fcbc`, 31 min (10:54:39–11:26:09); gate
auto-approved by `system:no_open_questions` (fifth auto-approval of the window); hash
`d4d4f662…` matches the pin. Implementation `run_d826c8de6d97` under way. Preconditions
held at launch (§2.7): zero leases, nothing in flight, queues drained, images = `f7a5e0a2`.

**Framing consistency audit — recorded IN FLIGHT, before the verdict.** No contradiction:
no status is declared two ways anywhere across manifest, plan, and probes; error contract
(400/404/409) identical to prior rolls; duplicate-join taught explicitly (case-insensitive,
409); frontend scope = slot 5's 3-route choice (list at `/`). **But one new species of
finding: the manifest declares join `success_status: 201` — the first framing of either arm
to do so (all prior said 200) — and the dev brief is SILENT on join's success status** (it
fully specifies the error statuses and says only "adds the participant and updates the
count"). The derived probe demands 201, so the contract will enforce a fact the brief never
states. Not a #1013 contradiction — a framing *omission* on a contract-enforced fact,
adjacent to the context-completeness class. Named now so that a red rooted in join 200≠201
cannot be read as a post-hoc attribution. Audit tally awaits the roll's outcome for how to
count this one: consistent-with-omission is a category §5.1 does not yet distinguish.

---

**Arm B tally: 4 functional / 5 counted** (launch 2 void — does not count, does not reset).
Slot 6 in flight — the final counted roll.
