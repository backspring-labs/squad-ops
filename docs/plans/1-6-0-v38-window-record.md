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
| 3 | cyc_410f3a9257f8 | counted slot 2 | *in flight* |

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
   unfixed behavior. So #1012 is **not** "the repair was never emitted" and not a
   round-3 regression: **the accepted repair lands in the artifact vault and does not reach
   the tree the suite assembles.** Roll 1's clause should be read as superseded on
   mechanism by this entry.

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

### Launch 3 — cyc_410f3a9257f8 — counted slot 2 — IN FLIGHT

Replacement for the voided launch 2. Launched 2026-08-20 23:52 UTC, `run_8893cd3f5dc0`.
Config verified identical to roll 1 before launch — `applied_defaults`,
`execution_overrides`, `task_flow_policy` all byte-equal, `resolved_config_hash`
`d4d4f662…` matching the §3 pin. Preconditions at launch (§2.7): zero unreleased focus
leases, nothing in flight, agent queues drained, seven deploy images matching `f7a5e0a2`.

| Framing | `run_8893cd3f5dc0`, 33 min (23:52–00:26 UTC); PRD hash `f744843d…` matches the §3 pin |
| Gate | approved 01:49 UTC, §7.3(c) text applied — **verified byte-identical to the banked launch-2 note by direct comparison**, recorded as the same agent id |
| Implementation | `run_48e4c90d7efa`, started 01:49 UTC |

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

---

**Arm B tally: 0 functional / 1 counted** (launch 2 void — does not count, does not reset).
