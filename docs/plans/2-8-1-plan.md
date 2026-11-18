# 2.8.1 plan — the 2.8 demonstration's follow-ups, fixed small

**Status: ADOPTED (2026-11-18).** After the 2.8.0 cut the Spark proposed three items, a verification and one finding to measure. The owner answered "I agree with the 2.8.1 items proposed". This plan says how each is built and verified, and what it leaves out.

**What 2.8.1 is.** A patch on the 2.8 line (CLAUDE.md, #281: urgent or small fixes, either lane). Each item is something the 2.8.0 windows met:
- a defect in what 2.8 shipped;
- a gap in what its evidence covers;
- the squad's most frequent return.

None changes a design beyond a numbered SIP amendment it names.

**The claim it makes:**

> **What the Roblox line reports is what happened, and the squad's scenarios are written to the rules the gate
> applies:**
> - a cycle a Campaign ended reads as ended, and an abort cancels only a cycle still running;
> - a Studio channel change is visible to the worker's pin;
> - the scenario-writing skill carries the coverage, reachability and broken-build rules, replay-tested;
> - the Campaign-level repair (§10 row 8) is exercised on a played product;
> - the API's stall after a gate entry is measured, and fixed if small.

---

## 1. The items

### 1. A cycle a Campaign ended at the gate reads as ended (#3201) — the Spark lane

- **The defect:** `cycle_status_of` (`api/routes/cycles/mapping.py:204`) reads runs and workload progress, never `cycle_ends`.
  - A cycle ended `rejected_at_gate` has a completed proposal workload and pending later workloads, so rule 3 reads it `ACTIVE`.
  - Rehearsal 3's abort then cancelled `cyc_929c449744f1`, which had ended 40 minutes earlier, and left the cycle that was actually paused alone.
- **The fix:** a cycle with a `cycle_ends` row reads as ended, and as what. That's the one reading #2214 asked for, extended to a Campaign's own endings.
- **Verified by:** a wiring test entering at the abort route, with a cycle ended `rejected_at_gate`. It's absent from `cancelled_cycles`, and the cycle route reads it as ended.

### 2. A Studio channel change is visible to the pin (#3206) — the MacBook lane

- **The gap:** on 2026-11-18 Roblox's updater moved the MacBook's Studio from `production` to `zluauordereddensehashmapcontrol` at the same version. The proof reads the version and the tool list only, so the pin couldn't see the move. Amendment 12f made the channel a window-opening check by hand.
- **The fix:**
  - the qualification proof and each result's `ran_with` carry Studio's channel, read from its startup log;
  - a claim on a Studio whose channel differs from the proof's is refused, as a version difference is (R5.21);
  - a numbered SIP-0117 amendment.
- **Verified by:** a test at the runner with a Studio whose channel differs from the proof's (refused by name), and a requalification run on the Mac that records the channel.

### 3. The scenario-writing skill carries the gate's rules (#3199) — the MacBook lane writes it, the Spark replays it

- **The evidence:** 7 of 11 proposal versions were returned across rehearsal 3 and the counted run (the record's §3 and §4).
  - **Checks that passed on broken work:** a format-only clock, a counter attribute standing in for the text, a lobby half with no floor half.
  - **Checks that failed on working work:** a wait on a value nothing sets, and an exact match on a value that changes each second.
- **The fix:** `play-scenario-authoring/SKILL.md` gains, with worked examples (the issue and its comments):
  - **coverage:** every sentence of the item is read by some criterion;
  - **reachability:** wait and observe only what the game sets today or the footprint adds, and prove the unreachable headless;
  - **the broken build:** the named check fails on the obvious broken version, and passes on any correct one;
  - **timing:** a band from a start the criterion states, with margin on both edges.
- **Verified by:** a skills replay under a new cases version before the profile requires the changed skill (SIP-0116 §7, §17p). The cases are the window's returned shapes, and they're judged by their expectations. The held working-work lesson (`pat_0e0dfc199afe0bed@2`) is withdrawn once this ships, since the skill supersedes it.

### 4. The Campaign-level repair on a played product (verification) — both lanes

- **The gap:** the 2.8.0 cut record §5. Both rehearsals that reached §10 row 8 were paused by `max_elapsed_s` before the repair launched. The diagnostic's repair was the run's in-run correction.
- **The run:** a diagnostic Campaign whose candidate the run itself can't correct. The cut lands where the run's correction can't see it, or its in-run repair budget is 0, so the cycle ends `rejected` or `blocked_unverified` and the Campaign routes row 8 or row 12. It runs with `max_elapsed_s` set so the repair launches. It's pre-registered as an amendment before it runs, with D1–D4 restated for the Campaign's repair cycle.
- **Needs:** about an hour of the Mac, in an attended window the owner names.

### 5. The API's stall after a gate entry (#3218) — the Spark lane, measured first

- **The finding:** 17 worker requests went unanswered, about 13–16 s after a gate entry or a Campaign transition, and each was answered at the next poll.
- **The work:**
  1. measure the runtime-api's latency on `/api/v1/workers/*` around a ruling;
  2. find what holds the loop;
  3. fix it in 2.8.1 if it's small, otherwise place it.

---

## 2. Order

Sequencing, not dates.
1. #3201 and #3218's measurement (the Spark), alongside #3206 (the MacBook).
2. #3199's skill text (the MacBook), then its skills replay (the Spark).
3. The row-8 diagnostic, on a deploy carrying 1–3, in an owner-named window.
4. The cut: one shakeout pair on the final deploy, and the cut record says what the evidence doesn't cover.

## 3. Left out, and where it goes

- **#3200** (a candidate's setup failure the baseline didn't have, routed to the run's own repair) is an attribution design change, so a SIP-0117 amendment. The next feature line.
- **#3205** (a replay an API client can run, and the supervisor principal's `memory:read`/`memory:draft`) is a new route plus an auth-boundary change, so the owner's ruling. The next feature line.
- **The Roblox improvements raised after the cut** go in as issues for the 2.10 plan: play actions that reach a named place, a reading compared across steps, a map of the place for the proposer, a screenshot per play, and a headless harness for client scripts. Faster plays through a reused Studio session go to 2.9, as a performance refactor.
