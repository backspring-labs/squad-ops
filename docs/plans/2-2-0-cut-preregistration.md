# 2.2.0 — pre-registration of the cut's set (plan §3 steps 10–11, the cut's criteria)

**Status: DRAFT for the owner, 2026-10-10. Nothing in it is registered, and nothing has launched.** The plan leaves
the regression set's size and the shakeout's exit rule to this document, written when the line's last batch is built
(the 2.2 plan §5), as 2.0 and 2.1 did. The window is read (the slice 4 pre-registration §12, SIP-0110 §5h), and no
code has merged since the window's deploy. So this batch is the window's tree.

**What must be true before it is registered:**
1. **The owner's dispositions at the cut are recorded** (§9): first the lesson's, because it decides what the
   shakeout's proposals receive.
2. **The final deploy is fixed** (§6). It is recommended to stay rebuild 12 (`ed540e1b`, `dep_4015cab5e042`), the tree
   the window measured. A code change pulled into 2.2 means a rebuild, every tracked loaded check answering on it, and
   the diagnostic and the shakeout run on that deploy.
3. **The tier's diagnostic passes** (§2, §4 P5). It is uncounted and runs before registration.
4. **The shakeout loop's exit rule holds** (§3): one shakeout campaign on the final deploy with no new seam finding.
5. **The pins are read** (§6), and nothing in the set has launched.

---

## 1. What the set measures

2.2's headline is Cross-Cycle Memory's first slice and its measured window. Beside it, #1708's plan-review tier is
built but has never run live. The set measures three things:
- the final deploy still builds what 2.1 built, with memory disabled (D12);
- the memory mechanism stays inert where it is declared disabled;
- the tier, activated for the first time, decides plan gates as its policy says, and escalates everything else.

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress on either stack, with memory disabled | each regression roll's verdict, criteria, correction rounds and boot audit, against §2's baselines | a clean campaign |
| a cycle declaring memory disabled pins no snapshot, and every consuming task records a `memory_disabled` exposure whose envelope reconstructs (SIP-0110 §0.15) | each roll's exposures and envelopes (`verify_authoring_envelopes.py`) | the window's replays, which ran with memory on |
| the campaign still evolves the app unattended, with its plan gates decided by the tier where the policy covers them | the shakeout's gate decisions (`decided_by = system:plan_review_tier`, each condition's reading in the notes) and its control log | the regression rolls, which run no campaign |
| every plan gate the policy does not cover escalates, and the escalation's lifecycle runs to its bound | the diagnostic's escalation rows, the expiry, the parked cycle and the continuation's row (SIP-0109 §24bj, §24bk) | a shakeout in which every plan qualified |

---

## 2. The set

- **Regression rolls: two per stack** (recommended), `fullstack_fastapi_react` and `nextjs_ts`.
  - They run on `validated-fullstack` with `full-38`, launched by the verification-set driver.
  - Their configs are carried from rebuild 9's, with the final deploy's tracked loaded checks.
  - **Every launch declares `memory: disabled`** (the driver's declaration, D12).
  - **The baselines** are the line's own regression pairs, on the same profiles and with memory disabled:

    | rebuild | deploy | React: verdict, criteria, rounds, boot audit, minutes | Next.js: verdict, criteria, rounds, boot audit, minutes |
    |---|---|---|---|
    | 1 | `99d4a11e` | accepted, 21/21, 0, PASS, 50 | accepted, 14/14, 1, PASS, 56 |
    | 5 | `76a29c86` | accepted, 20/20, 0, PASS, 53 | **rejected**, 13/15, 2, FAIL, 77 (#2152's case: route fills dropped the scaffold's `try/catch`) |
    | 6 | `8386202e` | accepted, 20/20, 0, PASS, 56 | accepted, 18/18, 2, PASS, 75 |
    | 7 | `09ed3985` | accepted, 21/21, 0, PASS, 47 | accepted, 15/15, 1, PASS, 81 |
    | 8 | `00bf3db6` | accepted, 21/21, 1, PASS, 51 | accepted, 14/14, 0, PASS, 61 |
    | 9 | `a84e085f` | accepted, 21/21, 0, PASS, 47 | accepted, 20/20, 0, PASS, 58 |

    Rebuild 9's deploy is the one the 2.2 shakeout validated. Rebuilds 10–12 ran no regression pair, so the set's
    rolls are the first on `ed540e1b`.
- **The shakeout campaign:** one campaign of **two increments** on React, opening with its calibration cycle.
  - **It declares `plan_gate: tier`** (plan §3 step 10, SIP-0109 §24bj: the cut's shakeout reads the tier live).
  - Its proposal rulings stay with the owner's delegate, since the increment gate is never the tier's.
  - It is the exit rule's shakeout (§3), and the set's campaign reading. It is uncounted, and a new seam finding in it
    is fixed and re-run before registration, never counted.
  - **Its memory follows the lesson's disposition** (§9). The recommended disposition (disabled) leaves no approved
    lesson, so the campaign pins an empty snapshot.
- **The tier's diagnostic, before registration** (#1251: the roll's own path with the fault injected). The shakeout
  covers the tier's approvals. An uncovered case may not occur in it, so the diagnostic forces one through the
  campaign's own path.
  - **The campaign:** one one-increment campaign, `plan_gate: tier`.
  - **The fault:** its objective's `allowed_scope` names the source files its objective changes, and not the test
    directories. Every implementation plan's qa task names a suite under them. So the increment's plan falls outside
    the scope (condition 4), and the tier must escalate.
    - The window's increments show it: each plan's `qa.test` names `backend/tests/criteria/test_T1.py` or
      `frontend/src/__tests__/criteria/T3.test.jsx` (`cyc_2a6f386318cc`, `cyc_5cd3a901a0e4`, `cyc_b84d479eb595`).
    - A proposal's derived footprint holds only product files, so the proposal's own scope rail still passes.
  - **The bound:** its `ruling_bound_s` is short (600), and no one answers. So the escalation expires, the run is
    cancelled `escalation_expired`, the cycle ends parked, and the continuation chooses `abandon_and_propose`.
  - **Exhaustion:** the re-proposal escalates again, for the same reason, and `max_unaccepted_increments: 2` ends the
    campaign `stop_failure` (no-progress). Its close record keeps the accepted calibration and the two expired
    escalations apart.
  - **A late answer:** recorded against one of the expired escalations after the close (§24bj, the late answer). It
    must leave the closed campaign closed.
  - **The delegate's part:**
    - it rules each proposal within the 600-second bound, which a ruling waits too;
    - it answers a calibration's design question if one is asked, since an unanswered calibration would end the
      diagnostic at row 2 and void it;
    - it never answers an increment's escalation before its expiry.
- **What the sample can say:** four rolls, one campaign and one diagnostic show the deploy working, memory inert where
  it is declared disabled, and the tier's two paths each taken at least once. They are not a reliability rate, and the
  record says so.

---

## 3. The frame

- **The shakeout's exit rule:** one shakeout campaign on the final deploy with no new seam finding (2.0's rule). A
  finding is fixed, the deploy rebuilt, and the shakeout re-run. The record reports how many rounds it took.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baseline beyond variance:** every criterion verified, and correction rounds
    within the line's observed range (React 0–1, Next.js 0–2);
  - **P1–P5 hold** (§4).
- **Fail:** a roll rejected, a boot audit failing, or a prediction falsified.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt. It is re-run under 1.8.2's
  void rule and does not spend the budget.
- **Data, not failure:** a correction round, a repaired qa suite, lint findings, and a plan gate the tier escalated in
  the shakeout because a calibration asked a question. That is the tier working, and it is answered by the delegate
  within the bound.
- **A framework fix during the set:** nothing merges while the set is open. A fix voids the set, and it restarts on a
  new deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every roll's cycle declares memory disabled and pins no snapshot; every consuming task records a `memory_disabled` exposure; every captured envelope reconstructs byte for byte | each roll's cycle row, `memory_exposures`, and `verify_authoring_envelopes.py` | a pinned snapshot, a consuming task with no exposure or another status, or an envelope that does not reconstruct |
| P2 | an observation is still recorded where a roll's run produces one (a failed round, a rejected plan): memory disabled stops supply, never observation (§0.3) | the observations table for the rolls' cycles | a failed round in a roll with no observation |
| P3 | in the shakeout, every plan gate whose plan meets all five conditions is approved by the tier, with `decided_by = system:plan_review_tier` and each condition's reading in the notes | the shakeout's gate decisions | a qualifying plan gate decided by anyone else, or a tier approval whose notes miss a condition |
| P4 | in the shakeout, a plan gate that fails any condition escalates, and is never approved by the tier | the shakeout's escalation rows beside its gate decisions | a tier approval on a gate with an open question, a footprint outside scope, or a re-rolled framing |
| P5 | in the diagnostic, the out-of-scope plan escalates (condition 4); the escalation expires at its bound; the run is cancelled `escalation_expired`; the cycle ends parked; the continuation chooses `abandon_and_propose`; the repeat parks again, and the campaign ends `stop_failure` with completed and unresolved work apart; a late answer is recorded against its escalation and reopens nothing | the diagnostic's escalation rows, run, cycle, continuation decisions, close record and digest | any step missing or out of order, a tier approval of the out-of-scope plan, or a closed campaign reopened |

---

## 5. The campaigns' policy

**The shakeout:** 2.1's cut shakeout (`2-1-0-cut-shakeout.yaml`), carried, with one change: `plan_gate: tier`.

| field | value | basis |
|---|---|---|
| `objective.target_accepted_increments` | **2** | §2, as 2.1 |
| `max_cycles` | **7** | 1 calibration, 2 increments, one repair or retry each, 2 replacements: 2.1's rule |
| `ruling_bound_s` | **1800** | 2.1's. A tier escalation waits the same bound a ruling does (§24bj) |
| `plan_gate` | **`tier`** | plan §3 step 10 |
| every other field | 2.1's cut shakeout | unchanged by this line |

**The diagnostic:** the shakeout's policy, with these changes:
- `target_accepted_increments: 1`;
- `max_cycles: 5`: 1 calibration and 2 parked increments, with 2 to spare, so that the no-progress rule ends it and the cycle cap does not;
- `max_unaccepted_increments: 2`;
- `ruling_bound_s: 600`;
- an `allowed_scope` that names the objective's source files and excludes the test directories, as §2 says.

The files are written with this document: `examples/03_group_run/campaigns/2-2-0-cut-shakeout.yaml` and `2-2-0-cut-tier-diag.yaml`. Both validate against the campaign API's objective and policy models.

---

## 6. Pins (read at registration)

| pin | value |
|---|---|
| deploy commit | `ed540e1b` (rebuild 12), unless §9's decision 2 pulls a change in |
| deploy record | `dep_4015cab5e042` (2026-10-09 17:41:07 UTC, `rebuild_and_deploy.sh all`) |
| image ids | read from the running deploy at registration |
| model | `qwen3.8:27b`, digest read at registration |
| loaded checks | the configs' tracked rows, every one answering at the counting preflight |
| set configs | `2-2-0-cut-regression-{fastapi-react,nextjs}.yaml`, sha256 read at registration |
| HEAD at preflight | read at registration. Its difference from the deploy commit is prose only, unless §9's decision 2 says otherwise |

---

## 7. Prohibited while the set is open

- **Merging to main.** A fix voids the set.
- **Rebuilding any service.**
- **Running anything else on the box,** the diagnostic and the shakeout included once the rolls start.

## 8. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or behavioural. On
  today's main: prose only, from `8fb5ca65` (the window's head) to `ca9577c9`.
- **Each void and re-run,** with its cause.
- **Each owner action.**

## 9. The owner's decisions at this stop

Each has a recommendation, and nothing registers before the owner says so.

1. **The lesson's disposition** (SIP-0110 §5h). Recommended: **disabled** at the cut, with the mechanism kept. It is
   ruled first, because the shakeout's proposals receive whatever it leaves approved.
2. **Whether a code change joins 2.2 before the cut.** Recommended: **none**. The plan has the cut tag the tree the
   window measured (§3 step 8). #2205 (an undefined manifest key drops the file the criteria need) and #2206 (a
   cross-role repair labelled as the failed task's) are placed in 2.3. If one is pulled in, the deploy is rebuilt, and
   §2's diagnostic and shakeout run on the rebuild.
3. **Register as drafted, or amend.** Recommended: pre-approve, as 2.1's was. The supervisor registers once the five
   conditions above hold, and reports the readings.
4. **The regression set's size:** two rolls per stack (recommended), or more.
5. **The shakeout:** one campaign of two increments on React, `plan_gate: tier` (recommended).
6. **The tier's diagnostic:** the scope-narrowed campaign in §2 (recommended), or the shakeout alone. The shakeout
   alone may never show an escalation.
7. **The next build-side experiment and Phase 2** (SIP-0110 §5h). Recommended:
   - the owner's direction of 2026-10-09, placed by the 2.3 plan;
   - Phase 2 unplaced and gated.
