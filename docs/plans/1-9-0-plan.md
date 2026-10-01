# 1.9.0 plan — the close of the 1.x line

**Status:** adopted, rev 8 (2026-10-01): rev 3 adopted at merge, with the rulings made after adoption in §7a and during the set in §7b. Written on the owner's word at the
1.8.2 cut ("let's cut 1.8.2 and write 1.9.0 plan"). The 1.8.2 counted rolls answered the question
this plan was held for: **no 1.8.3 opens** (the 1.8.2 plan §3.10; the pre-registration §10, deploy
A′).

**What 1.9 is.** The odd minor after the 1.8 line: **feature-free by rule**, and the home for the
structural refactor deliberately quarantined out of feature releases (CLAUDE.md, *Versioning*). It
closes the 1.x line. Its exit criterion is 2.0's entry condition (`docs/ROADMAP.md`, v1.9 row):

> **one named, extracted cycle-completion boundary through which Campaign observes terminal state
> and requests continuation.** Campaign does not begin by decomposing the executor.

---

## 1. What the 1.8.2 line says this release has to be

| what 1.8.2 showed | evidence | what it says about 1.9 |
|---|---|---|
| **A cycle can be left running unattended.** The chain read YES on every row. A cancel ends its wait in 6 s. A crash or a hang ends as a typed fact. | pre-registration §10 A′ d4; #1699 fixed by #1700 | **the four unattended properties are the regression bar** for an extraction that moves the run spine they live in |
| **No 1.8.3:** no qa task failed by its wait, and no contentless emission went unrecovered, across six counted rolls | §10, "§3.10: no 1.8.3" | **#1697 is 1.9's first item**, before #1507 (the 1.8.2 plan §3.10) |
| **N unmet a third time,** with dev × Next.js empty | SIP-0107 §46q | the flip (step 7) is a **2.0 decision**. 1.9 builds nothing for it, but repairs what the next count needs (#1716, #1724) |
| **Two diagnostic seams unreached on A′, by the owner's rulings:** the dev lane, whose fault the task's own self-evaluation reverts, and F1's designed rewind | §11h, §11i; #1716, #1723 | an **instrument line**: the diagnostics must reach their seams on a deploy carrying §12a's loop |
| **The driver's record has blind spots:** a dead executor read as live (#1714); a fault that did not bite recorded as "never ran" (#1718); a re-take's verification and identity absent (#1724); a self-evaluation pass that writes a new file leaves no revision form (#1724) | the issues, each with its trace | the driver is hardened **before** 1.9's set, so the set that proves the extraction reads cleanly |
| **Readouts depend on container logs, which a rebuild wipes.** Prefect holds the marker lines durably, back to 2026-04-25, but not one for one (measured, §7a item 2). | #1719 discussion (the evidence comment); #1745 | the driver reads Prefect's stored logs where a rebuild has replaced the container. That is hardening, with no new API surface |
| **A cycle's lineage names only the runtime's commit.** On A′, every cycle recorded `8e2c2e87` while the agents ran `ccc9475d`'s images. | #1720 | #80's named follow-ons are debt. The placement is decision 1 |
| **Dropped from 1.8.2 by its §3.9:** item 12 (the convergence replay), #1039 and the ops rider | the cut record | re-placed here by name (§5) |

---

## 2. Why this release, on the roadmap

**2.0 is Campaign: the inner of two loops** (`docs/plans/post-1-8-2-roadmap-reconciliation.md`).
The squad evolves an app across a roughly ten-hour campaign, and frontier models evolve the framework
from how campaigns perform. Campaign lands through a completion boundary it can observe: a cycle has
ended, with this outcome. It requests continuation there, rather than inside the executor's two
largest methods. **Building that boundary is 1.9's job.** Campaign's own mechanics — brownfield
cycles, Nat's increments, accumulated acceptance, the gate policy, calibration, the evidence
package — are 2.0's (#1705–#1711, #1692).

**The refactor is quarantined here** for the reason the odd minors exist: a regression on 1.9's set
must be unambiguously the refactor. So 1.9 carries **no feature** and **no correction-path
behaviour change** beside the extraction. #1697 changes the round index the correction path keys
on, which is why it lands **first and alone**, verified before the extraction starts.

---

## 3. The content

### 3.1 First: #1697 — a run-unique repair and retest id

Two repair dispatches in one run can share a task id, because the round index does not advance past
a refunded round. It cost two readings on 1.8.2 (§11d, §11f). It is shared by the budget, the
refund lines and the driver's joins, which is why 1.8.2 kept it off deploy A′.
- **Lands alone,** with its own wiring test at the correction runner's entry.
- **Verified before #1507 starts,** by replaying the stored runs where two dispatches shared an id:
  A′ d3 (`repair-run_97f19dba-00-qa.test_repair`) and d6 (`repair-run_99242d1e-00-qa.test_repair`).
  Each must now read distinct ids, with the refund joined to its own dispatch.

#### Result (2026-09-29): read on both; #1507 may start

#1697 merged as PR #1733 (`0739af1d`). The runtime API was rebuilt from it, and only that image
changed; the agents kept A′'s images, whose fault hook reads the round index unchanged.

**Re-run, not replayed.** SIP-0101's replay could restore only checkpoint 6: every later
checkpoint lists `corr-`/`repair-` ids, which the replay's id translation refuses by design. That
skips about 9 minutes of a 66-minute run, since framing still runs live. The driver can neither
launch a replay nor read one. So both diagnostics were re-run through the driver on 1.8.2's
configs, with only their name, records directory and pre-registration changed
(`var/1-9-0-logs/1-9-0-1697-*.yaml`). The records are under `var/verification_sets/1-9-0-1697/`.

| run | outcome | the prediction |
|---|---|---|
| `redelivery`, `cyc_cfc00ce6ebd8` | accepted, 20/20 | its two rounds are `-00-s00-` and `-00-s01-`; `repeated_round_ids` is empty; the two refusals name two distinct ids (A′: one id, twice) |
| `own-frame-then-prose-repair`, `cyc_b39af3354b8b` | accepted, 21/21 | `-00-s00-` and `-00-s01-` for diagnosis and repair; each refund names its round; **L4 reads YES** (A′ d6 read UNASKABLE, and was held only by the owner's ruling, §11f of 1.8.2); L7 reads YES |

**It found two defects of #1733's own, both in the driver, both fixed before this reading:**
- **#1742:** the `refunded_rounds` collector matched the old refund line literally, so the
  redelivery record read two logged refunds as none. The own-frame run's launching driver was
  stopped in framing, before its gate or any record, and the fixed driver re-attached by the
  reference recipe. Its record carries a `reattached` block.
- **#1744:** the retest readout joined rounds by index alone. Since the ids carry a sequence,
  #1698's guard no longer set same-index rounds aside, so a refunded round and its re-take merged
  and read regressions against the wrong baseline. It didn't touch these two runs: neither
  retested a patch.

**The instruments read live on the same runs:** #1724's re-take verifications (each re-take
indexed by its own dispatch and joined to its final evaluation), and #1718's DID NOT BITE form in
the marker samples.

### 3.2 The headline: #1507 — the executor's completion boundary

It is extracted under the 1.7.5 map's rules (`docs/plans/1-7-5-recovery-extraction-map.md`): one
reason to change per unit, behaviour held equal, and each slice a merge on its own evidence. In
order:
1. **`_reject_invalid_plan_before_workload_gate` (301 lines)** goes first, alone. It is framing-gate
   policy, not the run spine (#1507).
2. **`execute_run` (325 lines):** provisioning, checkpoint restore, dispatch, gate handling and
   finalisation, extracted by concern.
3. **`execute_cycle` (396 lines):** run sequencing and the cycle's terminal state. **This slice
   names the completion boundary:**
   - one seam where the cycle's terminal outcome is known;
   - a typed, read-only view of it (verdict, `RunTerminalDecision`, assessment reference);
   - one place a continuation request would enter.

   It is **named and exercised, with no Campaign caller**: a unit and a wiring test show a cycle's
   end reaching it on every terminal path (accepted, rejected, `blocked_unverified`, cancelled,
   failed, a rewind's run death).

**The exit criterion is the ROADMAP's, verbatim.** The boundary's name, contract and every terminal
path through it are written into the plan's cut record.

### 3.3 The instruments, before the set

Driver-side, with the exception of #1716. They land before 1.9's deploy, so its set reads cleanly:
- **#1714:** the #1699 guard excuses a run that started before the runtime's current process.
- **#1718:** the fault hook's DID-NOT-BITE lines are parsed, with the correct unaskable reason.
- **#1724** (narrowed to the driver's part; §20 and the counting rule are #1727): the record carries each re-take's verification (the suite line and the final
  typed-check evaluation, with its `workspace_revision_id`), and each self-evaluation pass that adds
  or re-emits a file.
- **#1696:** the marker self-check checks each sample line.
- **The driver reads `docker logs` for its loop texture, and Prefect's stored logs when a rebuild
  has replaced the container since the cycle's window** (#1745; corrected by §7a item 2 from
  "Prefect first"). Prefect is a fallback, not a copy: it misses the lines a process logs as it
  dies and the redelivery refusal, and the record names those holes rather than reading them as
  absent. That ends "a rebuild destroys the texture" (#1719 discussion).
- **#1716:** the dev-lane fault survives the task's own self-evaluation. It is applied to what the
  task hands on, and the marker comment is taken out of the code the model reads.
  - This is a diagnostic change in `src/squadops/capabilities/handlers/fault_injection.py`, and
    changes nothing for a normal cycle.
  - It is needed so the next N count can supply dev × Next.js at all.
- **#1723:** the question is investigated, not "fixed". The investigation renders round 0's analyzer
  request on both lines, and says whether the rewind is variance or a change in what the analyzer
  sees. A change to the correction path's behaviour is out of 1.9 (§2); if one is indicated, it is
  a 2.0 item.
  - **Answered and closed:** variance in the correction decision on equivalent input. Its two
    design questions are #1757 (2.0), and the reason the requests could not be compared, the
    framework's own 10,000-character cap on stored generation text, is #1756 (§7a item 10).

### 3.4 The named debts

Each is one PR, with its own test, behaviour-neutral unless it says otherwise:
- **#353:** the prompt manifest hashes are stamped at build, not hand-maintained.
- ~~**#1031:** the manifest-authoring design primer.~~ **Moved to 2.0** (§7a item 8): it is not
  behaviour-neutral, since it changes what the framing sequence authors.
- **#1448:** the routes stop reading their ports from a process-global registry.
- **#1522:** a repair whose retest reduces failures without passing is not discarded wholesale. This
  is a correction-path behaviour change, so it lands **after** the extraction's set reads, or moves
  to 2.0 (decision 3).
- ~~**#414:** the correction budget's allocation is severity-aware. Also a behaviour change, with the
  same rule as #1522.~~ **Moved to 2.0** (§7b item 1): the gate it was held on, measured, does not
  support the reserve, and what the one instance needed is a verdict-path rule.
- **#567:** the fenced parser's CommonMark recognition engine. Its precondition was "after Scoped
  Code Revision settles what a repair emits" (decision 2). **Gated on a replay** (§7a item 9): the
  new engine over every stored real emission. Identical recognition lands it before the deploy, as
  neutral in effect; any difference makes it a behaviour change, and it moves to 2.0.
  **Outcome (2026-09-29): the gate cannot run, so #567 moves to 2.0.** No complete model emission
  is stored anywhere: the vault keeps extracted files, and LangFuse cuts each generation at 10,000
  characters (#1756). The reasoning is on #567.
- **#1754** (filed 2026-09-29, §7a item 6): a run paused by admission is read as completed, and the
  re-rolls cancel it. Fixed **before the deploy**: it is a defect in the boundary §3.2 names, and
  not on the correction path.
- **#1701:** the duplicate "Failed to transition … cancelled" warning.
- **#1691:** `rebuild_and_deploy` syncs prompts before it starts agents.

### 3.5 Dropped from 1.8.2, re-placed

- **Item 12, the convergence replay:** scoped against whole-file, as the 1.8.2 plan §3.2 item 12
  specifies. It is driver-side and runs overnight on the idle box, with its predictions registered
  before it runs. Its reading informs 2.0's flip decision.
- **#1039,** the docs site design pass: prose and assets, never a cut blocker.
- **The ops rider:** #1177, #176 recipe 2, #1176, #1408 and #1412. This is its fifth plan, and
  decision 4 asks whether to run it or retire it. **Ruled (§7a items 3–5):** #176 recipe 2 is the
  first cycle on the 1.9 deploy; #1176's accept-rate replay runs on the idle box before the deploy;
  #1177, #1408 and #1412 are retired as not scheduled. **Outcome (2026-09-29):** #1176 closed with
  its reading (on `qwen3.8:27b` a carried trace reached the model and cut a repair's re-reasoning to
  0.07–0.17 of the attempt it repaired, against 0.30–0.46 without; every repair was accepted in both
  arms). #176 closed: the 1.9 deploy's first cycle, `cyc_3d28edb8333e`, completed.

### 3.6 The cut criterion: three gates

| gate | criterion |
|---|---|
| **implementation** | #1697, then the three #1507 slices, merged, with the completion boundary named, and every terminal path shown reaching it by a wiring test. §3.3's instruments merged before the deploy. The named debts that land do so by §3.4's rules. |
| **experimental** | **Behaviour held equal across the extraction**, read on 1.9's set (§4):<br>• L1 holds on every counted roll;<br>• functional yield at 1.8.2's level or better (six of six accepted);<br>• the `unattended-chain` diagnostic reads YES on every row of the 1.8.2 claim;<br>• `redelivery` and `compile-loop` read as predicted;<br>• #1697's prediction reads (distinct ids, refunds joined to their own dispatch). |
| **evidence** | every record three-state; readouts from the durable log store; the records attached to the Release after the credential scan; hygiene at the cut (step 8); what the cut evidence does not cover, stated |

### 3.7 Merge discipline

- **One reason to change per PR.** Each #1507 slice is a merge with its tests, and main is read green
  after it.
- **No correction-path behaviour change merges between #1697 and the set's reading.** #1522 waits, by
  §3.4 (#414 moved to 2.0, §7b).
- **Nothing merges between opening the release PR and merging it** (CLAUDE.md, *Release cut*).

### 3.8 Capacity: what drops first, and what cannot

When the line runs long, it sheds in this order, and each drop is recorded in the cut record:
1. the ops rider → retired or 2.0 (decision 4)
2. #1039 → 2.0's idle-box time
3. #567 → 2.0
4. #1522 → 2.0 (a behaviour change; §3.4). #414 has already moved (§7b).
5. the convergence replay (item 12) → 2.0, stated as the flip decision's missing input

**What cannot drop, because it is the line's claim:** #1697; the three #1507 slices and the named
completion boundary; the instruments §3.3 needs for the set to read (#1714, #1718, #1724,
the Prefect log reading); and the set itself.

---

## 4. The verification set

One deploy, after #1697, the extraction and §3.3's instruments have merged. Its pre-registration
carries 1.8.2's rules and adds the extraction's predictions before the first launch.
- **The diagnostics that exercise the run spine:**
  - `unattended-chain`, the four unattended properties across K cycles, with a cancel, a crash and a
    hang;
  - `redelivery`;
  - `compile-loop`;
  - `false-criterion`;
  - `own-frame-then-prose-repair`, which is #1697's shape, on both stacks;
  - `dev-lane-fastapi-react` and `dev-lane-nextjs`, on #1716's redesigned fault.
- **The counted set:** four FastAPI+React rolls and two Next.js+TS rolls, as 1.8.2. **Behaviour held
  equal is the claim.** The bar is L1 on every roll, and functional yield at 1.8.2's.
- **N is read as texture,** costing no rolls (decision 5). It becomes the fourth count 2.0's flip
  decision reads, with dev × Next.js supplied by #1716's fault and re-takes countable under #1724.
- **The shakeout loop and its exit, carried from 1.8.2's §6:** a pass on one deploy with no new seam
  finding, a budget of three rounds, and non-execution counted beside failure.

---

## 5. Re-placements by name: nothing silently carried

**A plan places whole issues. An issue the plan would only partly address is split when it is
placed,** so each placed issue closes in the release that owns it (CLAUDE.md, *Close issues from
PRs*). This is the guard against #80's failure, where named follow-ons lived only in a closed
issue's prose and were never filed. Applied here: #1724 and #1722 were narrowed to their 1.9 scope,
and their 2.0 halves filed as #1727 and #1728.

**43 issues on 2026-09-29, each placed once:** the 40 open that morning, plus #1727 and #1728 split
from them, plus #1732 filed at the 1.8.2 cut. **After rev 3, every open issue sits on 1.9 or 2.0.**

- **In this release (26), each closable in 1.9:**
  - **firm closes (13),** planned with no drop path:
    - the line's claim (§3.8): #1697, #1507, #1714, #1718, #1724;
    - also planned: #1696, #1716, #353, #1031, #1448, #1701, #1691, #1732 (the records tarball's
      checksum is stable across builds, which 1.9's own cut needs);
  - **conditional closes (13),** each on a decision in §7, the drop order in §3.8, or a
    precondition:
    - #1720 and #1722, decision 1;
    - #567, decision 2 (third to drop);
    - #1522, decision 3 (fourth to drop). #414 moved to 2.0 (§7b);
    - #1039, second to drop;
    - the ops rider (#1177, #176, #1176, #1408, #1412), decision 4 (first to drop). These close
      either way: a recipe run once is a terminal result, and a retired one closes as not planned;
    - #1723, which closes when the investigation answers it;
    - #1469, re-read at 1.9's cut. It closes only if its corpus has arrived and the parser lands.
- **2.0 (14):**
  - with Campaign: #1705, #1706, #1707, #1708, #1709, #1710, #1711, #1692, #316;
  - #949, an input to #1708's gate policy: the fallback if an answered design question must reach
    the plan through a revision;
  - #950 and #557, inputs to the Campaign SIP's revision: the gate's review packet, and the lead's
    per-repair acceptance review;
  - #1727, with the decision on SIP-0107 step 7 (§20 on the re-take path, and the re-take
    transaction);
  - #1728, the `campaign:` and `deploy:` tags, with Campaign and #1720.
- **Closed (3):**
  - #1626, at the 1.8.2 cut (that plan's decision 4, on the `redelivery` reading);
  - #194, not planned: only `validation-multirole` uses parallel proposers;
  - #1122, not planned: #1123 delivered targeted qa repair on this stack, and qa × React supplied
    5 scoped transactions on 1.8.2 without fill slots.

That is 26 + 14 + 3 = **43**, and 40 open.

**Not an issue, named so it is not lost:**
- SIP-0107 §38 step 7, a 2.0 decision (§46q);
- SIP-0086 §12a change 4, held (decision 6).

---

## 6. Sequencing

1. The 1.8.2 cut: tag, package, records, hygiene.
2. **#1697 alone,** with its replay of A′ d3 and d6.
3. §3.3's instruments. They are driver-side except #1716, and can merge in parallel with step 4.
4. **#1507, in three slices,** each merged and main read green: plan-gate policy, then `execute_run`,
   then `execute_cycle` with the named boundary.
5. The named debts that are behaviour-neutral (§3.4), between slices where they touch no slice's
   file.
6. The deploy; the pre-registration (**stop for the owner**); the diagnostics; the counted set.
7. #1522 (decision 3), after the set and the convergence replay have read. #414 moved to 2.0 (§7b).
8. The cut.

---

## 7. Decisions: adopted at merge (the owner's word, 2026-09-29: "Merge the 1.9.0 plan and get started")

Each decision below was adopted as recommended. Decision 6 is recorded in SIP-0086 §12a.

1. **#1720 (lineage) and #1722 (Prefect tags): 1.9 or 2.0?**
   - **Recommendation: #1720 in 1.9.** It is #80's promised follow-ons, which makes it debt. Without
     it, 1.9's own set cannot tell an agent-only rebuild from a clean one, and SIP-0108's lineage
     overclaims today.
   - **Recommendation for #1722** (now narrowed to these): its `project:`, `framework:` and
     `replay-of:` tags in 1.9, since they are small and additive. `campaign:` and `deploy:` are
     #1728 (2.0).
2. **#567's precondition,** "after Scoped Code Revision settles what a repair emits". The emission
   forms (anchored edits, fills, whole-file) are settled and recorded (SIP-0107 §46k–§46p). Only
   the flip's refusal is open. **Recommendation:** treat the precondition as met, and let #567 land
   in 1.9.
3. **#1522 and #414 are correction-path behaviour changes in a feature-free minor.**
   **Recommendation:** keep them, but land them only after the extraction's set has read, each with
   its own counted roll. Otherwise move them to 2.0.
4. **The ops rider, on its fifth plan.** **Recommendation:** run each recipe once on the idle box
   during the extraction work. #1177, #1408 and #1412 are Atlas A/B items; if Atlas stays blocked on
   its endpoint, retire them as not scheduled rather than carry them a sixth time.
5. **N read as texture on 1.9's set,** at no extra rolls. **Recommendation: yes.** 2.0's flip
   decision will need a fourth count, with both of the counting fixes in.
6. **SIP-0086 §12a change 4,** held since 2026-09-25. Its premise does not hold: the repairs have no
   loop. **Recommendation:** close it in SIP-0086 as not built, with that reason, rather than carry
   it.
7. **Crew review of this plan and 1.9's pre-registration,** the 1.8.2 plan's decision 6, carried.
   **Recommendation:** the same rule, stating it when the budget does not allow.

### 7a. Rulings after adoption (the owner's word, 2026-09-29: "ok good with all recommendations - go")

Ten questions reached the owner after rev 3 merged. Each was ruled as recommended:

1. **#1720's deploy record is written by a one-off command in the runtime image.**
   `rebuild_and_deploy.sh` runs `docker compose run --rm runtime-api python -m squadops.deploys.record`,
   which writes through a new port's Postgres adapter. That is the migrations' trust boundary, with
   no credential and no new route. The first half, image revisions and the heartbeat's `revision`,
   merged as #1753.
2. **The driver reads `docker logs` first, and Prefect's stored logs as the fallback** (#1745).
   - Measured: Prefect held 44 of 46 fields on the `redelivery` re-run. It missed the
     redelivered-refusal line, a fault logged as the process died, and one dispatch.
   - It held 56 of 56 on A′'s d3 after the rebuild.
   - §3.3's "Prefect first" is corrected to match.
3. **#176 recipe 2** is the first cycle on the 1.9 deploy: the `smoke` squad, `hello_squad` and
   `selftest`. It doubles as the deploy-alive smoke, and #176 closes with its result.
4. **#1176:** step 1 is measured on the issue. `qwen3.8:27b`'s renderer keeps a prior turn's
   thinking; `qwen3.6:27b`'s drops it. Step 3, the accept-rate replay with and without the carried
   trace, runs on the idle box before the deploy. Its mechanism prediction is registered first.
5. **#1177, #1408 and #1412 are retired as not scheduled.** Their blocker is the box, not an Atlas
   endpoint: each needs Ollama stopped and the Spark to itself, which the deploy and the set need.
   SIP-0106 §1.2e keeps the record.
6. **#1754, the paused-run defect, is filed and fixed before the deploy.** It is a defect in the
   boundary 1.9 names as its exit criterion. No diagnostic exercises a duty-window deferral or a
   focus-lease conflict, so it cannot confound the set's reading of the extraction.
7. **#1755, the qa re-take defect,** goes to 2.0 with #1727. It is a correction-path change.
8. **#1031 moves to 2.0.** It is not behaviour-neutral: it changes the persona, adds a conventions
   fragment, and changes the schema gate's findings.
9. **#567 is gated on the replay** described in §3.4.
10. **#1723 is closed** with its answer. Its two design questions are #1757 (2.0). The 10,000-character
    cap on stored generation text is #1756: the framework's own cap, not LangFuse's, and not placed.

**What this does to §5's accounting.**
- **In the release:** #1031 leaves for 2.0, and #1754 joins.
- **Closed:** #1723 (answered); #1177, #1408 and #1412 (not planned).
- **2.0:** #1031, #1755 and #1757 join.
- **Unplaced:** #1756, proposed for 2.0's instruments.

### 7b. Rulings during the set (the owner's word)

1. **#414 moves to 2.0** (2026-09-30: "I'm good to move 414 to 2.0"). Its deferral's trigger is
   met: `validated-fullstack` declares `required_checks`. But the gate it was held on, measured over
   the 1.8.x corpus (84 correction rounds in 57 runs, #414's comment of 2026-09-30), does not
   support the reserve it recommends.
   - The allocation problem it describes did not occur.
   - The one starvation shape, 1.8.0 React roll 5 (`cyc_7998e63be37f`), spent three rounds on a
     non-required builder check and ended `plan_defect` on the repeat rule. Its required checks sat
     on tasks it never reached, so a reserved attempt had nothing to attempt.
   - What it needed is a sequencing rule: an unrepaired non-required failure does not stop the run
     from reaching its required checks. That is a verdict-path change, not an allocation, and it is
     2.0's to design.

2. **The counted rolls' rejections get their evidence fix in 1.9, and their prevention in 2.0**
   (2026-10-01: "Good with your recommendations").
   - **The root cause.** Both rejected counted rolls (React 2 and 4) were a React view throwing at
     runtime under vitest's jsdom:
     - roll 4: a form read by name, `form.datetime.value`;
     - roll 2: a test that rendered a route-param view without its route.

     The `TypeError` that caused each was printed only in vitest's unhandled-error block, which
     nothing read. The analyzer diagnosed the `waitFor` timeout instead. On roll 4 it described a
     validation branch as missing that the code has, and no round could converge.
   - **#1784 lands in 1.9's post-set rebuild.** Those errors reach the failure evidence through the
     `app_traceback` seam (#687, #788). It rides the same rebuild and counted roll as #1522.
   - **#1785 moves to 2.0:** the two jsdom pitfalls, shown in the develop and qa prompts. It changes
     what every develop and qa task is shown, which is broader than a stabilization line carries.

3. **#1522 merges in 1.9** (2026-10-01: "Merge #1522 in 1.9 anyway"). The replay (#1764) saw no strict
   reduction in 96 repairs, the case #1522 keeps, and the set saw none either. The recommendation was
   to move it to 2.0. The ruling keeps it in 1.9, where it rides the post-set rebuild and the same
   counted roll as #1784, predicted silent (pre-registration §12).

**What this does to §5's accounting.**
- **In the release:**
  - #414 leaves;
  - #1774 (the dev-lane fault keyed on the declared join), #1776 (urllib3) and #1784 join, all
    filed during the set.
- **2.0:**
  - #414 joins, reframed as the sequencing rule;
  - #1785 joins.

## 8. What this plan does not decide

- **The Campaign SIP's revision** (after this plan; `post-1-8-2-roadmap-reconciliation.md`), and
  2.0's scope.
- **SIP-0107 step 7:** a 2.0 decision, on the fourth count.
- **The shape of the continuation request at the boundary** beyond "one typed place it enters". The
  Campaign SIP's revision specifies it; 1.9 only guarantees the seam exists and is exercised.
- **1.9's pre-registration,** written after the deploy, as 1.8.2's was.

## 9. Revision history

- **Rev 1 (2026-09-29):** the first draft, written at the 1.8.2 cut on the owner's word. The same
  day: #194 closed as not planned, and #949 placed on 2.0 as an input to #1708.
- **Rev 2 (2026-09-29):** §5 places whole issues. #1724 and #1722 are narrowed to their 1.9
  scope, with their 2.0 halves filed as #1727 and #1728. The in-release list is split into firm and
  conditional closes; #1626 closes at the 1.8.2 cut. The total is 42.
- **Rev 3 (2026-09-29), merged:**
  - every open issue on a release line: #1732 is a firm close; #950 and #557 go to 2.0; #1469 to 1.9;
    #1122 is closed as not planned; #1626 closed at the cut;
  - §7's decisions adopted at merge, and decision 6 recorded in SIP-0086 §12a;
  - 43 issues, 40 of them open.
- **Rev 8 (2026-10-01):** §7b item 3: #1522 merges in 1.9 on the owner's ruling, against the recommendation.
- **Rev 7 (2026-10-01):** §7b item 2: the root cause of the counted set's two rejections. #1784 (the
  evidence fix) goes to 1.9's post-set rebuild and #1785 (prevention) to 2.0.
- **Rev 6 (2026-09-30):** §7b records #414's move to 2.0. §3.4, §3.7, §3.8, §5 and §6 are
  corrected to match.
- **Rev 5 (2026-09-29):** the outcomes of §7a items 3, 4 and 9 (#176, #1176, #567), with the
  pre-registration (`1-9-0-preregistration.md`).
- **Rev 4 (2026-09-29):** §7a records the ten rulings made after adoption. §1, §3.3, §3.4 and §3.5
  are corrected to match: the log order, #1031's move, the #567 gate, #1754, the ops rider and
  #1723.
