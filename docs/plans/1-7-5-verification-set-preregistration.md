# 1.7.5 — Verification Sets: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Merging it is the owner's act and does not change what it pre-registers; the
branch commit is the record. Revised while the checkpoint pair and the shakeout loop run —
each finding becomes a merged fix and, where the fix is in deployed code, a new deploy (§2)
— and frozen before the first counted launch.

This is the 1.7.5 plan's §4 (`docs/plans/1-7-5-plan.md`) as data: **one bar, L1; one live
hypothesis, the fill declaration; five seam invariants proven by five diagnostics on the
pinned deploy; three CI invariants read live as texture.** Six counting rolls on
FastAPI+React, three on Next.js+TS, on one frozen deploy. Everything not restated here is
inherited **verbatim** from the 1.7.4 pre-registration and, through it,
1.7.3/1.7.2/1.7.1/1.6.6/1.6.5/1.6.4/1.6.3: §5 (scoring), §5.1 (roll validity — void / reset
/ counted), §6 and §6.1 (the gate constant and the two approval paths), §7 (prohibited while
open).

**What is different about this line, stated first.** 1.7.5 is a stabilization release whose
content is three structural closures — the composition roots (#286, #301, #637), invocation
truth (#929, #1206) and the recovery extraction (#1152, the whole of
`docs/plans/1-7-5-recovery-extraction-map.md`). None of them is a feature and none should
change what a roll does. That is the claim, and it is the hardest kind to evidence: **an
extraction that changed nothing looks exactly like an extraction that was never run.** So
the set's weight sits on reachability, not on verdicts:

> Zero attributable findings is acceptable **only if every registered diagnostic reaches its
> seam on the pinned deploy.** A clean extraction is not suspicious by definition, and a
> finding is not evidence of adequacy — the reachability count is.

**The rules this document carries from the plan's preamble, applied before roll 1:**

- **Every registered readout maps to a typed evidence field before the set opens, checked
  against a real record.** §3 names the field beside every claim.
- **No fault, no prediction.** The untouched-file rule (#1406) is a seam invariant, not a
  live hypothesis: its condition needs a correction round, an environment skip and a
  criterion on an untouched file, and nine ordinary rolls may produce none (1.7.4 produced
  one in nine). It is exercised **deterministically** by the absent-suite diagnostic instead
  (§3b).
- **Rolls measure emergent behaviour; faults prove reachable seams; CI proves deterministic
  mappings.** A diagnostic is read by the seam it reached (`seam_reached`), never by "the
  fault fired" (#1310, #1300), with a **two-run budget** each.
- **H1 is retired as a bar.** It holds by construction since #1430 and the 1.7.4 record said
  so. Its content stays a texture field in the three-state vocabulary: on a clean roll the
  framework row is filtered at `validation.py:252`, so the field reads
  `unaskable(filtered at the typed-check seam)` and the driver reads the run report's
  executed/passed counts beside it.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **6 counted** on FastAPI+React (§4) and **3 counted** on Next.js+TS (§5) — the fourth consecutive set at that size, for comparability across 1.7.2, 1.7.3 and 1.7.4 on one PRD and two stacks |
| Bar | **one: L1** (#1268), as amended before the 1.7.4 set opened — blocking on a counted roll whose contentless emission is *not recovered*; the occurrence count tracked and never quoted as zero |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 → 1.7.4 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `development_profile=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React **`3921c5a62106`**, Next.js+TS **`33cadf53688e`** — observed on the shakeout pair that closed the loop, on the frozen deploy, and unchanged from the value each arm carried through deploy A. Asserted on every counting roll; a move is recorded, not explained away |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — observed on both arms of the closing pair, unchanged 1.6.6 → 1.7.5 |
| Deploy — commit | **`8fd30eb8`** — main after the shakeout loop's last fix. A label, not an assertion (#1296): the image ids are the assertion |
| Deploy — image ids | `runtime-api` **`93c7dd5fd6f5`**, `max` **`3231fab70330`**, `neo` **`660d09e6a113`**, `nat` **`c341331f4456`**, `bob` **`c4b73e36d416`**, `eve` **`29693f10cdd4`**, `data` **`8d287dbad879`** — from the frozen deploy's identity; asserted at every counting launch |
| Loaded, not built | Verified per container as a live call with its paired control. Each arm's `loaded_checks` carries the prelude's ten surfaces **and the three closures' own** (#1493): `_llm_call`'s keywords with the deployed tree's single `chat_stream_with_usage` call site beside them; `PatchAcceptance` and `CorrectionRepair` constructed by the executor with the runner holding the same instance; `create_app(config)` with `CommsConfig()` raising |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-5-<arm>.yaml --roll N` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first, then Next.js+TS rolls 1–3 |

---

## 2. Preconditions and the shakeout log

### Deploy A — four rounds, and what each found

The prelude's deploy. One checkpoint pair per the plan; a red there belongs to the prelude
tranche, not to the closures.

| deploy | React | Next.js | what the round found |
|---|---|---|---|
| `3e72dc65` | rejected | rejected | the baseline-stylesheet work (#906/#1463) broke `frontend_build` on all six halves, hidden behind an empty reason |
| `7e228e57` | rejected | rejected | #1468 — the frontend-build row single-sourced; the tests proved the seam, not the wiring |
| `d16790f2` | rejected | rejected | #1472 — the failure reason derived one layer down; its own derivation then read PROGRESS as SHIFTED, fixed by #1475 |
| `d433fc27` | **accepted** | **accepted** | nothing new — **the pair that closed deploy A** |

Four rounds for one defect family, each round finding the next layer of it. That is the
shakeout loop behaving as designed, and it is why the loop exists rather than a single pair.

### Deploy B — the closures' deploy

Built from main carrying all three closures and the four hardening items.

| round | deploy | React | Next.js | what the round found |
|---|---|---|---|---|
| 1 | `b71d70ea` | **refused** | **refused** | see below — **not counted against the three-pair budget: no cycle ran** |
| 1 (re-run) | `8fd30eb8` | **accepted** | **accepted** | nothing new — **the pair that closed deploy B** |

**Round 1's refusal, recorded in full because it is a closure finding.** Both arms died in
two seconds on their first `squadops cycles create` with HTTP 500,
`RuntimeError: ProjectRegistryPort not configured`. The cause was #301's own: the comms
factory imported `A2AServerAdapter` at module scope, and only `agent.lock` ships the `a2a`
SDK — so the runtime-api, importing that factory **for its queue**, could not import it at
all. `_init_cycle_subsystem`'s `except Exception` turned the `ModuleNotFoundError` into one
log line; the container passed its health check and every other route answered.

Three things landed from it, and the third is the one that matters most:

1. **#1494** — the server is a local import inside `create_a2a_server`.
2. **#1495** — the swallowing `except` is gone. A runtime-api that cannot bind its cycle
   ports now refuses to start. Verified safe first: every optional dependency in that block
   already degrades on its own, and a test pins that so removing the catch cannot turn a
   transient database error into a boot loop.
3. **The guard that should have caught it, extended.** #637's job imports each *root* under
   its lock — but the roots import their adapter factories **lazily**, so a bare module
   import never reaches the line. A second step now imports, under the same lock and the
   same empty environment, what each root *composes at startup*. Verified red pre-fix and
   green post-fix against a venv built from `api.lock`.

**This refusal does not spend a shakeout round.** A round is spent when a pair completes and
is read; here no cycle was created, so there is nothing to attribute and nothing to compare.
The record states it as a deploy-preparation finding, counted separately from the loop.

**What the closing pair showed.** Both arms accepted, both functional, both P0 held, zero
failed checks and zero adverse, unverified or unevidenced criteria — React 18/18 in 51 min,
Next.js 16/16 in 56 min, each boot audit answering five contract probes. **Deploy B took one
round where deploy A took four.**

The React arm is the one that carries evidence about the extraction. It took a correction
round, which deploy A's last React shakeout never did, so twenty-two `loop_texture` fields
that read UNASKABLE there were asked here and the arm's unaskable count fell 31 → 6. What
they answered, on the deploy, in the order a real failure takes:

* `applied_patches: 2`; `patch_verifications` one row, `task_type=qa.test status=passed
  checks=18 failed=- agent_rows=12 agent_executed=12 skips=missing_tooling:3`
* `retests`: `patch_retest status=SUCCEEDED passed=True reason=Repaired suite passed` —
  **L2's seam reached on a real roll**, through `PatchAcceptance._retest_patched_suite`
* `evidence_superseded` emitted by `adapters.cycles.patch_acceptance` — the moved block
  naming itself in the deployed logs, which no unit suite can demonstrate
* `decision_inherited_claims`: `inherited: false`, `echoes: []` — **A1 held**, artifact named
* `no_execution_on_passed_verifications: {missing_tooling: 3}` — #1406's shape live: three
  environment skips on a verification that PASSED, with 18/18 saying no credit was withheld

The six fields still unaskable on that arm are the structural ones already registered —
#114's typed-check filter, #999's absent fill-merge evidence, the qa container's own log
line, and the two retry fields that presuppose a retry that was not aimed. None is new.

The Next.js arm ran clean with no correction round, so its twenty-two patch-path fields are
unaskable by the same structural rule, and `fill_merge_evidence` is observed with eight
filled slots, zero not-applicable, and the store touched.

**The #1206 generations reading, taken on this pair (§3e).** **EQUAL on both arms** — React
20 generation records against 20 LLM calls, Next.js 18 against 18 — where the 2026-08-31
pair read 26 against 35.

The ratio alone would not have settled it, and §3e says why: `gens_per_task` read exactly
1.00 on every cycle measured before #929 and was wrong every time, because a call producing
neither a log line nor a record is invisible to both sides. So the reading joins on a value
the two sides produce independently — the completion-token count, which LangFuse receives
over HTTP from the adapter's usage block while `log_emission_shape` writes it into the agent
container's own log from a different module. **Every count is matched on both sides in both
arms; none is named by only one.** The LangFuse side is scoped by `metadata.cycle_id` rather
than by a clock window, and its 19 and 16 distinct task ids against 20 and 18 calls are the
tasks that made two calls.

### The deploy-identity question this line had to answer

A driver asking only the prelude's questions proves the prelude and says nothing about the
closures — the same hollow-identity failure as a driver left on the previous deploy's
commit. #1493 added three rows to both arms' `loaded_checks` before deploy B opened, each a
live object fact with a control (§1, "Loaded, not built"). The `929` row is the one worth
naming: it prints the number of `chat_stream_with_usage` call sites in **the tree the image
baked**, and it reads `1`.

---

## 3. The exercise plan — stated before roll 1

### 3a. The bar

| id | claim | blocking on | typed field |
|---|---|---|---|
| **L1** (#1268) | the loop remains able to produce a valid running result — a counted roll whose contentless emission is **not recovered** breaches it | every counted roll | `loop_texture.contentless_emissions` with its recovery outcome; the occurrence count reported, never quoted as zero |

### 3b. The live hypothesis — one

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **the fill declaration** (#1434): zero contentless fill-mode first attempts across the counted set | every Next.js roll; emission-shape lines and the #1436 stamp | one contentless fill-mode first attempt | that `NONE` was semantically misdeclared, that `LOW` is the minimum honest declaration, and that the measured set found no contentless recurrence under the pinned provider, model and deploy on this workload. **Not** that `LOW` is generally sufficient; a provider or model change re-opens the reading |

**L1 and the hypothesis have different thresholds, deliberately.** One contentless fill
attempt falsifies the hypothesis while the loop may still demonstrate honest recovery and L1
stays green. That outcome is useful evidence, not a contradiction.

### 3c. The seam invariants — proven on the pinned deploy, two-run budget each

Five diagnostics, re-registered under a `1.7.5` prefix (#1496). **The recovery extraction is
what these exercise**, and each config names the map §3.4 block it asserts, so the record can
say which moved code a run reached rather than that a fault fired.

| diagnostic | invariant | the moved block it asserts | readout |
|---|---|---|---|
| `absent-suite` | **L2** (#1269) — a repair that supplies the suite an emission failure lacked is retested | accept-patch block 5 → `PatchAcceptance._retest_patched_suite` | "repair-retest seam reached" |
| `own-frame-then-prose-repair` | **L7** (the locus routes to `qa.test_repair`), **L4** (#1276 — a prose-only repair is refunded, not verified), **L5** (the re-take is briefed with its cases) | protocol blocks 4–5 → `CorrectionRepair.dispatch`/`.judge_emission`; outcome block 4 → `_route_correction_path` | the locus pair `affected_task_types → correction_repair_locus`; the refund count by reason; the re-take's briefed cases |
| `path-prefix` | **L8b** (#1311) — no emission lands under a literal `path/` prefix | outcome block 1 → `_carry_facts_to_the_next_attempt` | the extractor's strip count and the stored names (L8a read as the count on every roll) |
| `contentless-builder` | **R1** (#1372) — retried with its fact, not blind; **F1** (#1374) — no false corrected result composed from it | outcome block 1; accept-patch block 6 → `_settle_patch_evidence` with `compose_owed_framework_rows` | `retried_with_fact` / `retried_blind`; `framework_rows_rederived` |
| `absent-suite-then-false-claim` | **A1** (#968) — the decision does not inherit an analyzer claim the workspace refutes | protocol blocks 1–2 → `CorrectionRunner._diagnose`/`._resolve_correction_path` | `decision_inherited_claims` beside `analyzer_claims_dropped` (#1401) — a zero is only evidence with a non-zero beside it |

**A seam not reached after two runs is a closure finding and stops the set.** It is not
declared and carried, as 1.7.4's two-run rule allowed for seams the pack had not touched:
this line's closures moved every one of these blocks, so an unreached seam is a statement
about the extraction.

**The untouched-file rule (#1406) rides the absent-suite diagnostic.** Its condition — a
correction round, an environment skip, a criterion on an untouched file — is exercised
deterministically: the diagnostic runs on the React stack, forces a qa repair, and that
repair's patch verification runs at the runtime-api where npm is absent, which is the exact
shape that demoted three view-compile criteria on `cyc_dd3068d22f2c`. The readout is the
invariant's proof: the executed-and-passed view criteria survive the skip. The stored 1.7.4
case is replayed as a CI fixture beside it. Live occurrences on counted rolls are texture,
read from #1407's readout in the three-state vocabulary.

### 3d. CI invariants, read live as texture

The rewind invariant (**W1** — no honest rewind fault exists, unchanged from 1.7.4), the
locus invariant (**D1**) and the derived-rows invariant (**F1**).

### 3e. Texture — observed, never blocking

Every field with a producer and its unaskable state declared as a schema property (#1445)
before roll 1: the framing run's verdict (#1428); packaging findings per roll by class;
emissions versus banked artifacts (#1436, now exact); fill-mode qa completion tokens under
`LOW` (Q1 re-read); interface-coherence findings (#820) and mock-surface findings (#668) per
roll; the boot-audit image name (#1197); fence counts and placeholder strips per roll (L8a);
**generation records per LLM call on the shakeout pair (#1206, a LangFuse read)**; the
required files the rows declared (H1's content); correction rounds; verdict rate against
1.7.4's.

**The generations reading is this line's own.** #1206 measured 26 LangFuse generations
against 35 LLM calls on the 2026-08-31 pair, and #929's extraction made every seam record.
The shakeout pair's reading should be **equal**. Two cautions on it, registered now:
per-cycle generation counts rise by up to ~35% against 1.7.4 with **no change in spend** —
the gap was instrumentation — and `gens_per_task` read exactly 1.00 on every cycle measured
before this, which looked like an invariant and was the second call being dropped every
time.

---

## 4. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

Pins asserted at every counting launch: `frozen_image_ids`, `expected_config_hash_prefix`,
`expected_squad_snapshot_prefix`, and the launch checkout's HEAD pinned at roll 1. Set
config: `docs/plans/verification-sets/1-7-5-fastapi-react.yaml`.

## 5. Next.js+TS (`nextjs_ts`) — three rolls

As §4, with the stack overrides of §1. Set config:
`docs/plans/verification-sets/1-7-5-nextjs.yaml`. The fill-declaration hypothesis (§3b) is
read on every roll of this arm.

## 6. The shakeout loop and its exit

Deploy A got one checkpoint pair and took four rounds to settle (§2). Deploy B entered the
loop under the same rule — **exit on a pair with no new seam finding, budget three pairs** —
and **exited at round 1**: the pair produced no new seam finding in either arm.

**Rounds taken: one. Rounds attributable to the closures: zero.** The closures did produce
one finding on this deploy, and it is recorded above rather than folded in here: #301's
module-scope `a2a` import, which refused both arms before any cycle was created. It cost a
rebuild and three merged fixes, and it spent no round, because a round is spent when a pair
completes and is read.

**Early stop, one direction.** A falsified hypothesis or an unreached seam stops the set; a
good result never stops it early; a stop in one arm does not stop the other.

## 7. Gate constant

Inherited verbatim; carried in each set config's `gate_notes` and applied identically to
every roll.

## 8. Prohibited while open

Inherited verbatim. **Nothing merges to main between roll 1 and the last counted roll** —
the launch checkout's HEAD is pinned at roll 1 and a commit on that branch voids the pin.

## 9. Drift the record must declare

**Intended zero** — the tag is the measured deploy plus this pre-registration and the
record. Where the tagged tree differs from the validated deploy, the difference is named and
classified additive or behavioural (CLAUDE.md, "Say what the cut evidence does NOT cover").

**One difference exists already and is named here rather than discovered later.** The images
were built from `8fd30eb8`, and that is what `frozen_deploy_commit` carries. The driver runs
the set from a checkout at main, which is ahead of `8fd30eb8` by this document and the five
diagnostic configs — `git diff 8fd30eb8..HEAD -- src/ adapters/` is **empty**, which is the
condition the driver's own framework-drift check enforces on every counting roll. The
difference is docs-only and therefore additive: the driver imports `squadops` modules to
judge P0 and B1, and those modules are byte-identical to the ones the images ran.
