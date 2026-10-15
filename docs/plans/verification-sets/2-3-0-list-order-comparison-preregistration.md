# 2.3: a declared list order, before and after #2276 — pre-registration

**Status:** approved by the owner as written, 2026-10-14, with both choices in §8. #2276 merges between the arms on
this approval.
**Issue:** #2202. **The fix:** PR #2276. **Plan:** the 2.3 plan, phase 8: "#2202, then #2205: each with its own
pre-registered before/after comparison on the chosen engine … before it is batched with anything else".
**Uncounted.** Both arms are comparisons, not set rolls.

## 1. What the comparison reads

#2202: a manifest's `decisions[]` are prose, so an ordering written there was never built and still passed every gate.
The 2.2 window's campaign 3 (`cmp_d4181c169653`) had exactly this. Its calibration (`cyc_03b6f8ef0749`) declared
"runs ordered by datetime", and its `GET /runs` returned insertion order. Its proposer then proposed the ordering the
manifest already claimed.

#2276 makes an ordering checkable, through four links:
1. **Declaring it:** the manifest declares an order on its list endpoint: `order: { field, direction }`.
2. **Teaching it:** the authoring rules and the proposal prompt say to declare it there, not only in `decisions[]`.
3. **Deriving the probe:** the contract derives a probe for each declared order. It creates elements out of order and
   checks the list it reads back.
4. **Checking it:** the probe runs at verification, like every derived probe.

The comparison runs one campaign on the same objective twice, on TensorFold: once on the deploy without #2276, and once
on a rebuild that adds only #2276. It reads whether each link happens live.

## 2. The campaign

`examples/03_group_run/campaigns/2-3-0-list-order-comparison.yaml`, used for both arms. It is the 2.2 window's campaign
3 with three changes:
- the squad is `full-38-tf`;
- plan gates are supervised by the fixed rules of §4;
- it is labelled as this comparison.

Its objective is the PRD's expansion item "sort the runs list by datetime" (§4.1, Tier 1, item 2). It runs a
calibration and one increment, and the policy is campaign 3's.

## 3. The arms and the deploys

- **Before:** `dep_7a6cf99f7c11`, from `5105a5e2`, the deploy #2279's diagnostic runs on. It starts once that
  diagnostic has closed.
- **Between the arms:** #2276 merges, approved by the owner with this pre-registration, and nothing else does. The runtime API and every agent
  are rebuilt from that merge. The deploy id, commit and image ids are recorded on #2202 before the after arm starts.
  #2276 changes the agents' handlers and the runtime's contract derivation, so all of them are rebuilt.
- **After:** the same campaign definition, created fresh.

**Not run if** main's run for the deployed commit is red, the box isn't idle, or a loaded check fails. The rebuild adds
a loaded-check row showing #2276 is loaded: a manifest with `order:` derives the ordered probe. It fails on the before
deploy.

## 4. What the supervisor does, fixed before launch (both arms)

- **Increment gates:** approve each proposal at version 1, as it stands, with the notes "#2202 comparison: approved as
  proposed". The reading is the build. If the rails refuse a proposal, the runbook's §3 applies and the refusal is
  recorded. That is a reading of its own (§5, B3 and A3).
- **Plan gates:** approve each one as it stands. Any open question is answered in the notes with the PRD's reading,
  and nothing else is said.
- **Every decision** is recorded as an agent's (`--as-agent`). There is no other intervention. A run that fails is
  left to the campaign's own rules.

## 5. Predictions

Each one is read from the cycle's manifest, its verification contract, its proposal's change request, the run's
verification results and the delivered tree.

**The replay:** the delivered list's order is also read outside the cycle, by the boot audit
(`scripts/dev/audit_delivered_app.py`) on each accepted cycle's delivered app.
- **Its contract:** the one #2276 derives from the cycle's manifest, with the order the cycle claimed (in a decision or
  a criterion) declared on `GET /runs`.
- **Its status:** this is a replay, not a reading the cycle made, and is named as one. It is the only way to read the
  before arm's order, where no probe exists.

**Before (no #2276):**

| # | prediction | read from |
|---|---|---|
| B1 | no manifest declares an order on an endpoint. Any ordering is in `decisions[]`, in a criterion's prose, or nowhere, and each is recorded by where it is | each cycle's `interface_manifest.yaml` |
| B2 | no verification contract has an ordered probe | each cycle's `verification_contract.yaml` |
| B3 | the increment's proposal carries the ordering as criteria and, if anywhere in the manifest, as a decision. It does not declare it on `GET /runs` | the change request |
| B4 | **the defect's chance:** an accepted cycle whose manifest or criteria claim an ordering can deliver `GET /runs` unsorted. Read by the replay. A sorted delivery isn't a failure of this prediction; it shows the order went unchecked, not that it was missing | the replay |

**After (#2276):**

| # | prediction | read from |
|---|---|---|
| A1 | a cycle whose manifest states an ordering declares it as `order:` on `GET /runs`, with or without a decision beside it | the manifests |
| A2 | each declared order has its probe in that cycle's verification contract, with seeds | the contracts |
| A3 | **the proposer:** the increment's proposal modifies `GET /runs` to declare `order: { field: datetime, direction: … }`, and its footprint holds the file that serves the list | the change request; its footprint |
| A4 | **the check:** the ordered probe runs at verification. It passes on the accepted tree, or it fails and a correction round repairs the list's serving code | the run's verification results |
| A5 | **the fix's claim:** no cycle is accepted with a declared order its `GET /runs` doesn't honour. Read from the probe's result, and checked against the replay | A4; the replay |

**What a result would mean:**
- **A5 failing** (accepted, a declared order, an unsorted list) falsifies the fix, and the sequence stops for a read.
- **A3 failing** with A1 holding means the proposal prompt's half didn't take, while the manifest's did, and the
  reverse is a reading too. Either is recorded as it is, and neither is retried.
- **B4 sorted** in every before cycle leaves the before arm unable to show the defect live. The window's
  `cyc_03b6f8ef0749` remains its evidence, and the comparison then reads only whether the after arm checks what it
  declares.

## 6. Box time

About 2 h per arm, a calibration and one increment on TensorFold, plus the rebuild between them. That is about 4.5 h in
all, after #2279's diagnostic. The log archive (`campaign_log_archive.py --follow`) runs beside each campaign.

## 7. Not covered

- **Next.js:** the campaign builds FastAPI with React. #2276's Next.js probe shell is covered by its unit tests, and
  is not read live here.
- **A descending order and a numeric field** are covered by the unit tests, unless the squad chooses one.
- **The prompt's worked example** still records ordering only as a decision. It is kept by the owner's ruling
  (2026-10-14), so the authoring rules' new line is the only teaching the author sees.

## 8. The owner's choices

The owner approved both on 2026-10-14, and approved #2276's merge between the arms with them.

1. **One campaign per arm,** on the window's sorting objective, rather than a targeted set of plain cycles. The
   objective makes an ordering likely to be declared, and a plain cycle rarely takes the PRD's expansion items. Of the
   last four TensorFold cycles, one manifest mentioned sorting, and it put it out of scope.
2. **#2276 merges between the arms,** because deploys are built from main. The after deploy then differs from the
   before deploy by #2276 alone.

## 9. Deviation: the after arm re-runs on #2276 and #2309

Recorded 2026-10-14, before the re-run starts. The owner approved it the same day.

**What happened.** The first after arm (`cmp_f59a69f07bc0`, on `dep_4dbbbb990e74` from `f34b9df9`) stopped at its
calibration (`cyc_1aeaea1c304d`):
- A1, A2 and A5 held;
- A4 held only in part. The ordered probe ran and failed on an insertion-order list, but no correction round followed;
- A3 wasn't reached.

The cause was #2308, which predates #2276. When a contract probe failed, qa.test marked its outputs failed but returned
the task as successful. Only the task's result decides whether correction runs, so no failed probe had been repaired
since #1223. #2309 fixes it. The readings are on #2202.

**The change.** #2309 merged (`7eb661e3`), and the runtime API and every agent are rebuilt from it. eve runs qa.test, so
it is among them. The after arm runs again, on the same campaign definition, created fresh. The first after arm's
readings stand as recorded, and the re-run's are recorded beside them.

**What it does to the comparison.** The after deploy now differs from the before deploy by #2276 and #2309, not #2276
alone (§3 and §8, choice 2). #2309 changes only what happens after a contract probe fails, and no contract probe failed
in the before arm: neither cycle's eve log has qa.test's failing-probe line. So the before arm's readings would have
been the same on #2309, and the difference between the arms is still #2276's.

**#2205's comparison** runs its before arm on this same deploy, as its pre-registration's §3 says ("the deploy #2202's
after arm runs on").

## 10. Result

Recorded 2026-10-14. The readings, with their evidence, are on #2202. The records are under
`var/verification_sets/2-3-0-list-order/`.

**Before #2276** (`cmp_ed8000dfb94f`, on `dep_c627c2873c3c` from `8dded804`): B1–B4 held.
- No manifest declared an order. The increment's manifest put it only in `GET /runs`'s summary, and no contract had an
  ordered probe.
- The proposal carried the order as criterion T1, with `backend/routes.py` in its footprint.
- The build sorted, and T1's test checked it.
- **The replay** of the increment, against the contract #2276 derives with its claimed order declared, passed all six
  probes. The before calibration, replayed the same way as a control, failed the ordered probe with insertion order,
  so the replay discriminates.
- **As §5 anticipated,** the before arm didn't show the defect live. The window's `cyc_03b6f8ef0749` remains its
  evidence.

**After #2276, first run** (`cmp_f59a69f07bc0`, on `dep_4dbbbb990e74` from `f34b9df9`): stopped at its calibration.
- A1, A2 and A5 held. The ordered probe caught insertion order, and the calibration was rejected.
- No correction round followed (#2308, §9), so A4 held only in part, and A3 wasn't reached.

**After #2276 and #2309, the re-run** (`cmp_a47189e4e061`, on `dep_0eafe15d5819` from `7eb661e3`): A1, A2, A4 and A5
held; A3 wasn't exercised.
- **A1, A2:** the calibration declared `order: {field: datetime, direction: asc}` on `GET /runs`, with a decision as
  its warrant. Its contract derived `vc-probe-runs-ordered`, with seeds. The increment kept both.
- **A4:** neo's fill returned insertion order, and the probe failed. eve failed the task, and a correction round
  repaired `backend/routes.py` with a one-line `sorted(…, key=lambda r: r.datetime)`. The retest passed.
- **A5:** both runs' verification list the ordered probe as executed and passed. Both replays pass with the cycle's
  own contract.
  - The increment's replay first failed every backend probe with 501, an audit defect: the boot audit assembled the
    increment's run alone, which holds the scaffold's stub for the file the increment left alone (#2310).
  - With its fix (PR #2311), the audit assembles the accepted tree and passes.
- **A3:** the calibration had already declared and built the order, so the proposer had none left to declare. It
  proposed showing each run's datetime in its row, with the view as its footprint. That is the reverse of the 2.2
  window, where a proposer proposed an order the manifest only claimed.

**What the comparison shows.**
- **Before #2276,** an ordering was checked only where an increment's own criterion test happened to check it, and
  the manifest carried it as prose.
- **After it,** the order is structure: the author declared it, the contract derived its probe, and the probe caught a
  build that ignored it. With #2309, the correction loop repaired the serving code. No cycle was accepted with a
  declared order its list didn't honour.

**Defects found on the way:**
- **#2308,** fixed by #2309: a failing contract probe never engaged correction, since #1223.
- **#2310,** with its fix in PR #2311: the boot audit assembled a campaign increment from its own run.

**Not read live:** the proposer's teaching (A3), because no increment had an order left to declare. It is covered by
#2276's unit tests.
