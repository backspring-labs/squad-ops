# 1.9.0 plan — the close of the 1.x line

**Status:** draft, rev 1 (2026-09-29), for the owner's review. Written on the owner's word at the
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
| **Readouts depend on container logs, which a rebuild wipes.** Prefect holds the same marker lines durably, one for one, back to 2026-04-25. | #1719 discussion (the evidence comment) | the driver reads Prefect's stored logs. That is hardening, with no new API surface |
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
- **#1724, items 1–2:** the record carries each re-take's verification (the suite line and the final
  typed-check evaluation, with its `workspace_revision_id`), and each self-evaluation pass that adds
  or re-emits a file.
- **#1696:** the marker self-check checks each sample line.
- **The driver reads Prefect's stored logs** for its loop texture, falling back to `docker logs`.
  That ends "a rebuild destroys the texture" (#1719 discussion).
- **#1716:** the dev-lane fault survives the task's own self-evaluation. It is applied to what the
  task hands on, and the marker comment is taken out of the code the model reads.
  - This is a diagnostic change in `src/squadops/capabilities/handlers/fault_injection.py`, and
    changes nothing for a normal cycle.
  - It is needed so the next N count can supply dev × Next.js at all.
- **#1723:** the question is investigated, not "fixed". The investigation renders round 0's analyzer
  request on both lines, and says whether the rewind is variance or a change in what the analyzer
  sees. A change to the correction path's behaviour is out of 1.9 (§2); if one is indicated, it is
  a 2.0 item.

### 3.4 The named debts

Each is one PR, with its own test, behaviour-neutral unless it says otherwise:
- **#353:** the prompt manifest hashes are stamped at build, not hand-maintained.
- **#1031:** the manifest-authoring design primer.
- **#1448:** the routes stop reading their ports from a process-global registry.
- **#1522:** a repair whose retest reduces failures without passing is not discarded wholesale. This
  is a correction-path behaviour change, so it lands **after** the extraction's set reads, or moves
  to 2.0 (decision 3).
- **#414:** the correction budget's allocation is severity-aware. Also a behaviour change, with the
  same rule as #1522.
- **#567:** the fenced parser's CommonMark recognition engine. Its precondition was "after Scoped
  Code Revision settles what a repair emits" (decision 2).
- **#1701:** the duplicate "Failed to transition … cancelled" warning.
- **#1691:** `rebuild_and_deploy` syncs prompts before it starts agents.

### 3.5 Dropped from 1.8.2, re-placed

- **Item 12, the convergence replay:** scoped against whole-file, as the 1.8.2 plan §3.2 item 12
  specifies. It is driver-side and runs overnight on the idle box, with its predictions registered
  before it runs. Its reading informs 2.0's flip decision.
- **#1039,** the docs site design pass: prose and assets, never a cut blocker.
- **The ops rider:** #1177, #176 recipe 2, #1176, #1408 and #1412. This is its fifth plan, and
  decision 4 asks whether to run it or retire it.

### 3.6 The cut criterion: three gates

| gate | criterion |
|---|---|
| **implementation** | #1697, then the three #1507 slices, merged, with the completion boundary named, and every terminal path shown reaching it by a wiring test. §3.3's instruments merged before the deploy. The named debts that land do so by §3.4's rules. |
| **experimental** | **Behaviour held equal across the extraction**, read on 1.9's set (§4):<br>• L1 holds on every counted roll;<br>• functional yield at 1.8.2's level or better (six of six accepted);<br>• the `unattended-chain` diagnostic reads YES on every row of the 1.8.2 claim;<br>• `redelivery` and `compile-loop` read as predicted;<br>• #1697's prediction reads (distinct ids, refunds joined to their own dispatch). |
| **evidence** | every record three-state; readouts from the durable log store; the records attached to the Release after the credential scan; hygiene at the cut (step 8); what the cut evidence does not cover, stated |

### 3.7 Merge discipline

- **One reason to change per PR.** Each #1507 slice is a merge with its tests, and main is read green
  after it.
- **No correction-path behaviour change merges between #1697 and the set's reading.** #1522 and #414
  wait, by §3.4.
- **Nothing merges between opening the release PR and merging it** (CLAUDE.md, *Release cut*).

### 3.8 Capacity: what drops first, and what cannot

When the line runs long, it sheds in this order, and each drop is recorded in the cut record:
1. the ops rider → retired or 2.0 (decision 4)
2. #1039 → 2.0's idle-box time
3. #567 → 2.0
4. #1522, #414 → 2.0 (they are behaviour changes; §3.4)
5. the convergence replay (item 12) → 2.0, stated as the flip decision's missing input

**What cannot drop, because it is the line's claim:** #1697; the three #1507 slices and the named
completion boundary; the instruments §3.3 needs for the set to read (#1714, #1718, #1724 items 1–2,
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

**40 open issues on 2026-09-29, each placed once.**

- **In this release (25):**
  - first: #1697;
  - the headline: #1507;
  - instruments (§3.3): #1714, #1718, #1724 (items 1–2; items 3–4 go with 2.0's flip decision),
    #1696, #1716, #1723 (investigated);
  - debts (§3.4): #353, #1031, #1448, #1522, #414, #567, #1701, #1691;
  - from 1.8.2's drops (§3.5): #1039, #1177, #176, #1176, #1408, #1412;
  - by decision 1: #1720, #1722 (its available-now tags; `campaign:` and `deploy:` follow Campaign
    and #1720);
  - read on 1.9's set: #1626.
- **Closed at the 1.8.2 cut (proposed):** #1626. The 1.8.2 plan's decision 4 reads "#1626 closes on
  the `redelivery` diagnostic", and A′ d3 read as predicted: two kills, two typed refusals, no run
  left running. **If it is closed at the cut, the in-release count is 24.**
- **2.0, with Campaign (9):** #1705, #1706, #1707, #1708, #1709, #1710, #1711, #1692, #316.
- **At design review (4):** #949, #950, #194, #557.
- **Read at the cut, open by design (1):** #1469.
- **Not scheduled (1):** #1122.

That is 25 + 9 + 4 + 1 + 1 = **40**.

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
7. #1522 and #414, if decision 3 keeps them, after the set has read.
8. The cut.

---

## 7. Decisions for the owner

1. **#1720 (lineage) and #1722 (Prefect tags): 1.9 or 2.0?**
   - **Recommendation: #1720 in 1.9.** It is #80's promised follow-ons, which makes it debt. Without
     it, 1.9's own set cannot tell an agent-only rebuild from a clean one, and SIP-0108's lineage
     overclaims today.
   - **Recommendation for #1722:** its `project:`, `framework:` and `replay-of:` tags in 1.9, since
     they are small and additive; `campaign:` and `deploy:` with Campaign and #1720.
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

## 8. What this plan does not decide

- **The Campaign SIP's revision** (after this plan; `post-1-8-2-roadmap-reconciliation.md`), and
  2.0's scope.
- **SIP-0107 step 7:** a 2.0 decision, on the fourth count.
- **The shape of the continuation request at the boundary** beyond "one typed place it enters". The
  Campaign SIP's revision specifies it; 1.9 only guarantees the seam exists and is exercised.
- **1.9's pre-registration,** written after the deploy, as 1.8.2's was.

## 9. Revision history

- **Rev 1 (2026-09-29):** the first draft, written at the 1.8.2 cut on the owner's word.
