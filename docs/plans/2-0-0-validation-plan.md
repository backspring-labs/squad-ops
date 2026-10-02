# 2.0.0 validation plan — what each step proves, the recovery diagnostics, the reference scenario

**Status:** DRAFT, rev 2 (2026-10-02), for the owner's and the crew's review. Written overnight on the
owner's word ("progress the plan through the night"), answering "do you have the validation plan
spec'd?".

It is the companion to:
- `docs/plans/2-0-0-plan.md`, the adopted plan;
- `sips/accepted/SIP-0109-Campaign-Orchestration.md`: §18 (what each step proves), §19 (the acceptance
  criteria) and §22 (the tests).

**What it is not:** the pre-registration. That is written after the shakeout campaign and stops for the
owner (the plan's §6, step 14), with the counted set's predictions and the limits' values.

---

## 1. The rules every step's PR follows

| rule | from |
|---|---|
| **A changed seam has a wiring test** that enters at the caller the live cycle uses, and asserts what reaches the seam. The PR's Evidence section names the entry point | `docs/TEST_QUALITY_STANDARD.md`, anti-pattern 6a |
| **A mutation check per changed seam:** the guard is reverted or broken, the named test fails, the code is restored, and the `.pyc` is deleted | the 1.9 line's practice |
| **Real records, not only fixtures.** A new check or producer is run against stored cycles from `data/artifacts/` and the registry | the verification sets' practice |
| **A behaviour-neutral step proves its neutrality** by recomputing every stored cycle, old path against new | SIP-0109 §18, step 1a |
| **A step's offline proof reads the deploy, never writes it.** A backfill or replay reads the live registry or vault, and writes neither | the 1.9 line's replay practice |
| **A step that changes what the deploy runs is also proven live.** After it merges: rebuild, confirm the migration applied and the new code is the code loaded, confirm stored cycles still read, then one uncounted regression roll on the baseline's configuration (§4) once the box is quiet. Live runs are fast-lane evidence, never the cut's (the plan's §5) | CLAUDE.md's wiring rule: #1250, #1256 and #1261 were each found by a live cycle |

---

## 2. The verification matrix

One row per SIP-0109 §18 step, and the evidence that step's PR carries before the next step starts.

| step | issue | unit | wiring: the entry point | mutation: break this, and this test fails | replay, backfill or live | intermediate acceptance (§18) and criteria (§19) |
|---|---|---|---|---|---|---|
| **1a: the failure producer** | #1710 (part 1) | `failure_events(outcome, evidence)` on a crafted completed outcome (failed and unverified checks), a failed run, and an unrecorded input | `assess()`, the function the assessment route calls, reaching attribution through `failure_events` | drop the unverified events, and the completed-cycle attribution test fails | **backfill:** for every cycle in the deploy's registry, `assess()` before and after the change yields an identical attribution (a read-only script) | behaviour-neutral; criterion 12d |
| **1: the campaign object, the control log, the launch outbox** | #1799 | each transition commits with its control-log row; an idempotency key repeated returns the row; a conflicting key is refused; a launch intent is written in the decision's transaction | the registry adapter's transition method, entered as the continuation choke point will call it | remove `source_launch_id`'s uniqueness, and the duplicate-launch test fails | **integration (Postgres):** the migration applies on a fresh database and on main's schema; the uniqueness holds under concurrent launchers. **Fault points:** a crash after the intent commits and before the cycle is created, and after the cycle is created and before the intent is marked | atomic commit; conflicts refused; restart from the log; exactly one cycle per intent; criteria 1, 8, 12c |
| **2: the proposal run and the typed change request** | #1706 | `ChangeRequest` validation; an out-of-scope `manifest_delta` or footprint refused; the footprint derived, never authored | the `proposal` workload dispatched through the executor's run path, with a stubbed LLM port, recruited and released like any run | let an out-of-scope delta through, and the refusal test fails | **real manifests:** stored authored manifests (`data/artifacts/*/interface_manifest.yaml`) with typed deltas applied run through the SIP-0103 gates | recruitment like any run; out-of-scope refused; criteria 3, 4 |
| **3: the evaluator trees and the verifier bundles** | #1806 | the baseline overlay's contents; the candidate-verifier overlay's contents; test identity (new, modified, renamed); bundle content addressing | the evaluator that builds each overlay, entered from accumulated acceptance | put one candidate product file into the baseline overlay, and the isolation test fails | **real suites:** test identity over `tests/fixtures/roll_replays/` and stored qa suites | accepted tree immutable; overlays isolated; adding a criterion moves no other bundle; criteria 7, 8, 12e |
| **4: accumulated acceptance and baseline discrimination** | #1707, #1796 | a criterion with no discriminating test is not met; an import or setup failure is not discrimination; a frozen bundle runs by its invocation | **`CycleCompletion`**, with a stored two-increment campaign record built from real cycles; the frozen criteria reach the verdict | count an import error as discrimination, and the classifier test fails | **the reference scenario's baseline (§4):** the fixed change request's tests on the baseline overlay must fail as assertions (a join that succeeds where the criterion expects 409; a missing test id) | frozen criteria executing; import errors not counted; criteria 5, 6, 7 |
| **5: the gate, the binding, the lease, the decision table, repair and retry** | #1801, #1802, #1800, #1705 | one crafted input per row of the three-step decision; the precedence overlaps, including criterion 12g (escalation against a pausing limit); stale and conflicting rulings; `approved_with_refinements` refused | the existing gate decision path, into the campaign's ruling transition; every launch path (campaign, CLI, driver) into the lease check | let a stale binding through, and its test fails; let a launch through under a supervisor's lease, and its test fails | **live, read-only:** the quiet-box check against the running deploy's engines and deploy record (it may launch nothing) | each row reachable; a paused action resumed once; repair and retry reuse exactly the bound request; criteria 5, 9, 10, 11, 12, 12a, 12b, 12f, 12g |
| **6: the projections** | #1799 | each control-log row projects to `AuditPort` and to an event | the transition, through to both projections | make the projection's failure abort the transition, and the "a failed projection loses no record" test fails | — | a failed projection loses no control record |
| **7: calibration, the reference scenario, evidence** | #1709, #1804, #1710 | the package materializes from records alone, idempotently | campaign close, with a stored campaign | materialize from a log instead of the records, and the "usable without the deploy" test fails | **a crash at close:** the projection re-runs and is byte-identical | criteria 2, 13, 14 |
| **8: the recovery diagnostics** | #1803 | — | — | — | **live, §3** | every row of §12a; criterion 1 |

---

## 3. The recovery diagnostics (#1803)

Each guarantee in SIP-0109 §12a is verified at **two layers**:
- **deterministically in CI**, with fault points in the registry adapters;
- **live on the deploy**, driven by the verification-set driver and read from the campaign's control
  log.

Each prediction is a **mechanism**: a record field that takes a stated value, never a rate.

| guarantee | CI fault point | live injection | read from | passes when |
|---|---|---|---|---|
| **restart at every state** (calibrating, proposing, awaiting ruling, launch blocked, paused, escalated, promoting) | a fresh adapter instance over the persisted rows | `docker restart squadops-runtime-api` when the control log shows the state | the control log's last committed transition, before and after; the count of rulings | the resumed state equals the last committed transition, and the ruling count is unchanged |
| **a duplicate completion event** | the choke point called twice for one cycle | the completion event re-published for a finished cycle | decision rows and launch intents keyed by that cycle | exactly one decision row and one intent |
| **a repeated ruling; a conflicting key** | the ruling transition, twice | the gate decision posted twice; then the same key with a different payload | the ruling rows; the control log's refusal row | the repeat returns the recorded ruling; the conflict is refused and recorded; nothing launches |
| **interruption during promotion** | a fault inside the promotion transaction, before commit | the runtime API killed between the evaluation results and promotion (on the evaluator's last log line) | the accepted identity; the evaluator results | the accepted identity is either the old or the new one, never partial; the new one only with every result recorded |
| **an abort mid-cycle** | — | `squadops campaigns abort` while a run is in flight | the cycle's cancellation; launch intents after the abort | the cancel path fires; no intent after the abort; the campaign ends `aborted` |
| **a crash on either side of cycle creation** | after the intent commits and before the cycle is created; after the cycle is created and before the intent is marked; two launchers on one intent | one kill of the runtime API around a launch | intents against cycles by `source_launch_id` | exactly one cycle per intent |
| **a pause, then a resume** (five cases: accepted, rejected, `proposal_failed`, repair, retry) | crafted counters reaching a pausing limit | — | the held pending action, and the action executed after resume | the held action executes once, with no new decision row |
| **launch blocked, then resumed** | the quiet-box check returning not quiet | **a small foreign model loaded in Ollama** before a launch, then unloaded | the launch-blocked rows; the escalation after the count | refused and recorded; resumes when quiet; escalates after the count |

**One risk, stated:** the live launch-blocked diagnostic loads a model the deploy did not. The Spark has
a record of swap thrash with two large models resident (`reference_spark_crash_history`). It uses the
**smallest available model**, and is pre-registered with the box's free memory read before and after.

---

## 4. The brownfield reference scenario (#1804)

**The baseline: `cyc_7a4b7a6fbf0e`.** This is the 1.9 post-set counted React roll on deploy `8a058dc3`,
accepted 21 of 21 with zero correction rounds (`docs/plans/1-9-0-preregistration.md` §12). It is the most
recent accepted FastAPI+React tree, on the current framework.
- **It implements no capacity limit.** Its interface manifest names none, and no view mentions one,
  checked 2026-10-02. That leaves the PRD's first expansion for the change request below.
- **It is pinned** by the content hash of its tree, reconstructed from the vault the way
  `scripts/dev/capture_delivered_app.py` reconstructs it, and by its manifest's hash, both taken when
  the scenario is frozen.

**The fixed change request: the PRD's own Expansion Tier 1, item 1, the capacity limit per run**
(`examples/03_group_run/prd.md:105-108`):

| field | value |
|---|---|
| `kind` | `feature` |
| `prd_delta` | the capacity-limit requirement, as the PRD states it |
| `manifest_delta` | **modify** entity `Run`: add `capacity`, optional integer. **Modify** the create endpoint's request: accept `capacity`. **Modify** the join endpoint: add the error `capacity_exceeded` (409). **Modify** the detail route's view: add the test id `capacity-status` |
| `criteria` | **C1:** creating a run with capacity 2 returns it with `capacity: 2` (the create endpoint). **C2:** joining a full run answers 409 `capacity_exceeded` (the join endpoint). **C3:** the detail view renders "2 / 2 joined" in `capacity-status` (the detail route) |
| `must_not_break` | every baseline criterion |
| `retires`, `replaces_verifiers` | none |

**Why this request:**
- Its expected behaviour is specified by the same PRD the baseline was built from.
- It touches each surface a brownfield cycle edits: an entity field, a request, an error and a view.
- Each criterion has a public surface, so baseline discrimination is checkable. On the baseline:
  - C1's `capacity` is absent from the response;
  - C2's join succeeds where 409 is expected;
  - C3's test id is absent.

  Each is an assertion failure, not an import error.

**The proposal half.** The strategy role also proposes against the same baseline, under the objective
"evolve group_run toward its PRD's expansion scope". That proposal is recorded and rated by the
supervisor, not built (SIP-0109 §11a).

**What its record reports, separately:**
- delta framing (which tasks ran and which were skipped);
- scoped repair, if a round occurs;
- accumulated acceptance (the baseline's frozen criteria on the candidate);
- baseline discrimination (C1–C3 on the overlay);
- the rated proposal.

It runs in the fast lane between campaigns, and in the counted set.

---

## 5. What this plan does not decide

- **The pre-registration:** the counted set's predictions, the limits' values (set from the shakeout,
  immutable for the set, recorded with their basis), and its readings.
- **The shakeout's own exit rule:** 1.9's, carried (a pass with no new seam finding, within a budget).
- **Which model the live launch-blocked diagnostic loads:** the smallest that Ollama serves on the box at
  the time.

## 6. Revision history

- **Rev 1 (2026-10-02):** the first draft, written overnight. It holds the verification matrix, the
  recovery diagnostics' designs, and the reference scenario's pinned inputs. For review.
- **Rev 2 (2026-10-02):** rev 1's rule "never launches a cycle" cited the plan's §6, which says no such
  thing. Replaced by two rules: offline proofs only read the deploy, and a step that changes what the
  deploy runs is also proven live, with a rebuild and one uncounted regression roll (the owner's
  question: aren't builds and cycles critical for validation as you go?).
