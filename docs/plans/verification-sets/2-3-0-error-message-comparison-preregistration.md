# 2.3: an error's message declared on its code, before and after #2275 — pre-registration

**Status:** for the owner's approval. Nothing runs before it.
**Issue:** #2205. **The fix:** PR #2275. **Plan:** the 2.3 plan, phase 8: "#2202, then #2205: each with its own
pre-registered before/after comparison on the chosen engine … before it is batched with anything else". It follows
#2202's comparison (`2-3-0-list-order-comparison-preregistration.md`).
**Uncounted.** Both arms are comparisons, not set rolls.

## 1. What the comparison reads

#2205: the 2.2 window's campaign 4 (`cmp_ff3ddfdfbc70`) asked for exact error messages, and its proposal
(`prop_5af48f5f739c` v1) couldn't be built. Three gaps made that happen:
1. **The undefined key:** the proposal put the messages under `messages:` in three endpoint definitions, a key the
   manifest doesn't define, so it was dropped silently.
2. **The unbuildable criteria:** the footprint was derived without that key, so it omitted `backend/routes.py`, and the
   criteria T1–T3 on its endpoints could not be met.
3. **No place for wording:** the manifest had no element for an error's message at all.

The rails passed it. Only the supervisor's reading of the footprint caught it, and the revision dropped the backend
messages.

#2275 closes all three:
- the rails refuse an undefined key by name, and an endpoint criterion whose serving file the delta leaves alone;
- the owner's ruling (a) of 2026-10-14 adds `message` to each code in the error contract;
- the frozen error module renders a declared message, and the derived probes assert it.

The comparison runs one campaign on the window's objective twice, on TensorFold: once on the deploy without #2275, and
once on a rebuild that adds only #2275.

## 2. The campaign

`examples/03_group_run/campaigns/2-3-0-error-message-comparison.yaml`, used for both arms. It is the 2.2 window's
campaign 4 with three changes:
- the squad is `full-38-tf`;
- plan gates are supervised by the fixed rules of §4;
- it is labelled as this comparison.

Its objective is the PRD's expansion item "improving the error messages the UI shows" (§4.1, Tier 1, item 4). It runs
a calibration and one increment, and the policy is campaign 4's.

## 3. The arms and the deploys

- **Before:** the deploy #2202's after arm runs on, which carries #2276 and not #2275. It starts once that arm has
  closed, so no rebuild comes between them.
- **Between the arms:** #2275 merges, on the owner's approval, and nothing else does. The runtime API and every agent
  are rebuilt from that merge, because #2275 changes the runtime's rails and derivation, the scaffold the agents expand,
  and the probe judge they run. The deploy id, commit and image ids are recorded on #2205 before the after arm starts.
- **After:** the same campaign definition, created fresh.

**Not run if** main's run for the deployed commit is red, the box isn't idle, or a loaded check fails. The rebuild adds
a loaded-check row showing #2275 is loaded: a code's declared message reaches the frozen error module and the derived
probe. It fails on the before deploy.

## 4. What the supervisor does, fixed before launch (both arms)

- **Increment gates:** approve each proposal that reaches the gate, at the version it arrives, as it stands, with the
  notes "#2205 comparison: approved as proposed". **The supervisor doesn't read the footprint.** In the window, that
  reading is what caught gap 1, and the rails are what this comparison reads.
- **Plan gates:** approve each one as it stands. Any open question is answered in the notes with the PRD's reading,
  and nothing else is said.
- **Every decision** is recorded as an agent's (`--as-agent`). There is no other intervention. A run that fails, or an
  increment that's rejected, is left to the campaign's own rules.

## 5. Predictions

Each one is read from the proposal's change request (every version), the rails' refusals, the cycle's manifest and
verification contract, the run's verification results and the delivered tree.

**Before (no #2275):**

| # | prediction | read from |
|---|---|---|
| B1 | **where the wording goes:** if the proposal asks for exact error messages, it puts them in a key the manifest doesn't define, in a view's prose, or in criteria only. Each is recorded by where it is | the change request |
| B2 | **the rails pass it:** no refusal names an undefined key or an unbuildable criterion | the proposal's rail verdict |
| B3 | **the defect's chance:** an endpoint criterion on wording whose serving file the footprint omits can't be met. The increment's verification fails it, the plan gate refuses a task outside the footprint, or the build writes the wording where the footprint allows (the view). Which one happens is recorded | the plan gate; the run's verification; the delivered tree |

**After (#2275):**

| # | prediction | read from |
|---|---|---|
| A1 | **the proposer:** wording is declared on the codes, as a `modify` of each `error_code` with `message`. If a version writes an undefined key instead, the rails refuse it by name (`undefined_key`), and a later version declares it on the codes | every version of the change request; the refusals |
| A2 | **the footprint** holds the frozen error module (`backend/errors.py`), and no `surface_outside_footprint` refusal names a criterion on an endpoint that declares a rewritten code | the approved change request |
| A3 | **the contract:** each derived rejection probe whose code declares a message carries `error_message` | the cycle's `verification_contract.yaml` |
| A4 | **the check:** the delivered app returns each declared message word for word. The probes pass, and the increment's criteria on the wording pass | the run's verification results; the increment's evaluation |
| A5 | **the fix's claim:** no proposal reaches the gate whose endpoint criteria no build may meet | A1–A2 |

**What a result would mean:**
- **A4 failing** (a declared message, a probe that fails it, and the cycle accepted anyway) falsifies the fix, and the
  sequence stops for a read.
- **A proposer that never asks for exact backend wording** (as the window's revision did, keeping the messages in the
  view) leaves gap 3 unexercised in that arm. That is recorded as "not exercised", not as a pass. The rails' readings
  (B2, A1–A2) still stand.
- **B3 with the build writing the wording into the view** is the window's own outcome, and is a reading of the defect:
  the criteria named backend endpoints.

## 6. Box time

About 2 h per arm, a calibration and one increment on TensorFold, plus the rebuild between them. That is about 4.5 h in
all, after #2202's comparison. The before arm needs no rebuild of its own. The log archive
(`campaign_log_archive.py --follow`) runs beside each campaign.

## 7. Not covered

- **Next.js:** the campaign builds FastAPI with React. The Next.js error module's rendering is covered by #2275's unit
  tests.
- **A message for `validation_error`,** unless the proposer declares one.
- **Wording that differs by endpoint for one code,** which the ruling's design doesn't express.

## 8. The owner's choices

1. **One campaign per arm** on the window's error-message objective, rather than a targeted set of plain cycles: no
   plain cycle asks for exact error wording.
2. **The supervisor approves without reading the footprint,** because the rails are what's measured. In the window, the
   supervisor's reading is what caught gap 1.
3. **#2275 merges between the arms,** because deploys are built from main. The after deploy then differs from the
   before deploy by #2275 alone.
