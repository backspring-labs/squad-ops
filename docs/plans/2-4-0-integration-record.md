# 2.4.0 integration record: IR-1 to IR-10

SIP-0112 §8.4's integration scenarios, recorded as §8.3.1 names: each **run** or **not run**. A *not run* record
carries §8.5's four fields: the missing prerequisite, the shared contract affected, the capability whose evidence is
absent, and whether the release claim is affected. The cut reads this record (G6). Each scenario then passes on the
cut deploy, or reports *not run* here.

**Where the runs were.** The owner opened no integration branch (G2). Both lanes integrated through reviewed PRs to
`main`, so each run below was on a deploy of `main`, or of a branch of it carrying both lanes' merged work, named in
its row. A run on the Mac checks machinery, not quality (the owner, 2026-10-18).

**Written** 2026-10-22 by the MacBook lane, from the records each row cites. The Spark lane's rows are its own runs,
read from its records.

## Where each scenario stands

| id | lane | status | the evidence | at the cut |
|---|---|---|---|---|
| IR-1 | MacBook | **run, passed** on the Mac | PR #2444's live check: after the cutover to `postgres`, a selftest cycle of each of the five projects completed (`hello_squad` `cyc_2960c474a2fe`, `run_crysis` `cyc_fa67753711d2`, `group_run` `cyc_970c4a33215e`, `play_game` `cyc_2b4a0313c806`, `agent_chess` `cyc_c61f265210f5`), with artifacts at the same paths and the same PRDs byte for byte. The rollback to `config` was run, then the Mac returned to `postgres`. On the Spark, the cutover was made on 2026-10-21 (`dep_ceda294644b3`, on #2410): the five projects were seeded `READY` and `projects list` served them. No cycle was created there for IR-1. | **passed** on the cut deploy, 2026-10-23 (below) |
| IR-2 | MacBook | **run, passed** on the Mac | `docs/plans/2-4-0-demonstrations-readout.md`, "IR-2, live on the Mac" (`dep_cc31bd6fd406`): `prj-shelfnote` at `433f6c51`, revision 3. The standalone `cyc_2c995f503391` and the Campaign `cmp_e616b0a78aa6`'s `cyc_95c8659ae6c5` read the same source context. Each unit pinned its own snapshot (`snp_ef0e4ef30fa9e74f`, `snp_c00e517025eabfef`). | **passed** on the cut deploy, 2026-10-23, on `prj-z-continuum` (below) |
| IR-3 | MacBook | **run, passed** H.3's points 1–3, on the Spark | #2179, "IR-3, live on the Spark" (`dep_31fe124fd638`, `88e5bf7e`): Campaign W's calibration `cyc_55cfd92773d2` kept its binding of `CLAUDE.md@77cb6d66` through the outside change. Campaign X's launch was refused for the drift (`STALE_SOURCE_PRECONDITION`) and escalated, then bound `@15fc9a77` after reconciliation and resume (`cyc_32123eb94847`). The wiring test is `tests/unit/projects/test_ir3_campaign_instruction_drift.py` (#2616). | as run; point 4 (a re-binding as a recorded intervention) is the unit tests' (`test_rebinding.py`) |
| IR-4 | both | **not run** | see below | not run in 2.4 (the owner's ruling, "go with 2.5") |
| IR-5 | both | **not run** | see below | not run in 2.4 |
| IR-6 | Spark | **not run** | see below | not run in 2.4 |
| IR-7 | both | **not run** | see below | not run in 2.4 |
| IR-8 | MacBook | **run, in part** | PR #2452's live check: `prj-e41-check`, registered after the cutover, was read by `projects show` at once, and `cycles create` refused it as `REGISTERING` (seen, not missing). The Campaign launcher reads a Project registered after the cutover: IR-2's `cmp_e616b0a78aa6` on `prj-shelfnote`, and IR-3's two Campaigns on `prj-z-continuum`, each launched. Outcome Evaluation's read of a registered Project isn't shown: see below. | **register, show, create and launch passed** on the cut deploy, 2026-10-23 (below); the evaluation's read not run |
| IR-9 | both | **run, the native check's half**; **not run, the evaluation's half** | The brownfield demonstration on the Spark (`docs/plans/2-4-0-demonstrations-readout.md`). At stage 3, `prj-z-continuum`'s inherited `lint` FAIL stayed `inherited`, with 59 findings before and after, while `tests` passed (60) and the change was accepted (`art_0d17c83b411c`). At stage 6 it also read `inherited`, though its findings grew from 59 to 62 (#2609). H.5 (#2630) now reads a check with a declared reader finding by finding: growth is `introduced`, and an unchanged set stays `inherited`. On the Mac (`dep_539b1736d144`, #2630's live check), `prj-continuum`'s baseline lint read 59 findings in 42 keys under its declared reader. A check with no reader is held by the shared fixture's contract test and H.5. | the native half as run; the evaluation's half not run |
| IR-10 | both | **run, passed** on the Spark | The counted pair, pre-registered in `docs/plans/verification-sets/2-4-0-ir10-preregistration.md` (#2649) on `dep_1b38de8af6b4` from `23ed15f3`, which carries both lanes' work through #2647, #2636 and #2639 included. FastAPI + React `cyc_00f7cec8da9b`: accepted, 21/21, 0 correction rounds, boot audit PASS. Next.js `cyc_17dcac259f6f`: accepted, 24/24, 3 correction rounds, boot audit PASS. All six predictions held (below). | **held** on the cut deploy, as the cut's set: its P5 carries R3 and R4 (below) |

## IR-10, the counted pair (the Spark lane, 2026-10-22)

Run as pre-registered, one roll per stack: `group_run` on `full-38-tf` (TensorFold) with `validated-fullstack`,
launched by the verification-set driver from `bf3270a3`. That commit's `src/` and `adapters/` match the deploy's, which
is what the driver's drift check holds. Every launch declared memory disabled, and nothing deployed between the rolls.
The records are in `var/verification_sets/2-4-0-ir10/`, and each config hash matches its 2.3.1 baseline roll's.

| # | prediction | read |
|---|---|---|
| R1 | the FastAPI + React roll is accepted, every criterion verified, boot audit PASS | **held**: accepted, 21/21, 0 correction rounds, 24 min, boot audit PASS. The baseline took 27 min and 1 round |
| R2 | the Next.js roll is accepted, boot audit PASS, #2395's signature absent | **held**: accepted, 24/24, 49 min, boot audit PASS, no unverified or adverse criterion. The baseline was rejected for #2395 alone (16/17, 115 min) |
| R3 | the cadence policy and pulse checks unchanged: none declared, no pulse record | **held**: neither cycle's applied defaults declare a cadence policy or pulse checks, and `pulse_verification_records` holds no row for their runs |
| R4 | the correction paths unchanged, and none of 2.4's new executor paths firing | **held**: the Next.js roll's 3 rounds went through handlers the baseline used (`development_correction_repair_handler`, `governance_correction_decision_handler`, and `qa_test_repair_handler` for its one QA repair). *Corrected 2026-10-23:* this reading first named only the first two. The roll's record shows `qa_test_repair_handler` ran (the cut pre-registration's §11). No run carries a binding hold or a halt, and each cycle has its 2 runs (framing, implementation): no restart |
| R5 | every tracked loaded check answers as expected | **held**: 170 of 170 rows observed in each roll (all 166 of `loaded_checks.yaml`, and the services' own) |
| R6 | memory stays disabled, nothing supplied | **held**: all 29 exposures (10 and 19) are `memory_disabled`, and none supplied a task or project instruction |

**Declared, not a prediction:** while the rolls ran, the box also ran single-process unit test runs (up to about 2
minutes each) and node tests in a container, for #2551 and #2564. No measure of IR-10 reads wall-clock time.

## The *not run* records

Each names §8.5's four fields. All four trace to one gap: a Campaign on a repository-backed Project can't launch an
increment (#2619). Its proposal profiles pin a scaffold stack that a source-backed cycle refuses, and its proposal
needs an interface manifest the product has none of. The fix is SIP-0112 H.4, placed in 2.5 with SIP-0109 §24bv and
SIP-0113 §10l (the declared start at the cycle-end hook, re-placed to 2.5 on 2026-10-21). The owner ruled on
2026-10-21: "go with 2.5". The 2.4 plan records it ("Not run in 2.4").

| id | missing prerequisite | shared contract affected | capability whose evidence is absent | release claim affected |
|---|---|---|---|---|
| IR-4 | #2619: no Campaign increment of an external Project, so no scenario suite runs over one | 2 (Campaign admission's suite pin), 7 (starting the product) | that no scenario step reaches a prompt, an envelope, a container, the Project Context, the handoff, an instruction, a clone, a workspace or the product repository during an external Project's increment | no: 2.4 claims no Outcome Evaluation of an external Project |
| IR-5 | #2619: no accepted increment of an external Project | 4 (accepted trees to Git), 5 (outcome references) | that a sandbox revision, a Git commit, an accepted tree and an evaluation result resolve to one another for one increment. A standalone delivery's revision-to-commit mapping is shown by E.4.3 and E.4.4 (#2410, #2411) | no |
| IR-6 | #2619, and the declared start at the cycle-end hook for a repository-backed Project (SIP-0113 §10l, 2.5) | 7 (starting the product) | scenarios on an external Project's own surfaces, started by its own commands, with no interface manifest | no |
| IR-7 | #2619: a greenfield Project is repository-backed, so its first Campaign can't launch an increment | 1 (Project identity), 2 (Campaign admission) | Outcome Evaluation reading a greenfield Project's first Campaign. The greenfield creation itself shipped and ran (`cyc_7bf35ffb4cc5`, `backspring-labs/z_shelfnote#1`, merged as `9bcdc7c0`); #2412 stays open for this scenario | no: the greenfield proof (G6) stands on E.4.6's own evidence |
| IR-8, the evaluation's read | #2619 and SIP-0113 §10l, as IR-6 | 1 (Project identity) | Outcome Evaluation reading a Project registered after the cutover | no |
| IR-9, the evaluation's half | #2619, as IR-4 | 5 (outcome references) | Outcome Evaluation's reading of the same increment as its own record, neither deriving from the other | no |

## At the cut (the Spark lane, 2026-10-23)

On the final deploy, `dep_d7ff50b9b39c` (main `b3acbc82`), with `full-38-tf` on TensorFold, after the cut's set was
read and #2183's T12 campaign was withdrawn and aborted. The records are in `var/verification_sets/2-4-0-cut/ir/`.

- **IR-1, passed.** One `selftest` cycle of each seeded project through `cycles create`, one at a time, each completed
  with its six artifacts under `data/artifacts/<project>/<cycle>/<run>/`:

  | project | cycle | run | took |
  |---|---|---|---|
  | `hello_squad` | `cyc_75c0855f69b3` | `run_ea868150d641` | 82 s |
  | `run_crysis` | `cyc_d6fc90a31e97` | `run_57a835f98b57` | 662 s |
  | `group_run` | `cyc_1460f95004d7` | `run_62df10766977` | 557 s |
  | `play_game` | `cyc_d8a0f06e6c27` | `run_978f2bb56f79` | 383 s |
  | `agent_chess` | `cyc_295a1136f53d` | `run_26f8b16c7c46` | 479 s |

- **IR-2, passed, on `prj-z-continuum`** (`READY` at `15fc9a77`, configuration revision 4), the Mac's pair carried with
  the Spark's squad and its reconciled external Project (`var/campaigns/ir2-cut.yaml`, from
  `docs/plans/2-4-0-greenfield/campaign-ir2.yaml`):
  - **the standalone cycle** `cyc_03644a0e7fd5` and **the Campaign** `cmp_db018b53e124`'s calibration
    `cyc_2260216894c3` read the same source context back from the API: `project-source-context/v1`, record version 22,
    revision 4, baseline and upstream `15fc9a77`;
  - **each unit pinned its own snapshot:** the standalone cycle `snp_101dce52c7249b4f`, the Campaign
    `snp_83a31d2e67658dbe`. Asked for its own, the API answers that the Campaign's cycle "binds the campaign's snapshot";
  - **both runs then failed alike, after preparation, at provisioning:** "implementation plan required but absent", as
    on the Mac. No plan was given, since the check is preparation's, and the Campaign completed.
- **IR-8, the registry's half, passed:**
  - `projects import … --id prj-ir8-cut --idempotency-key ir8-cut-1` gave `registered: prj-ir8-cut REGISTERING (record
    version 1)`, and the same command again gave `replayed`;
  - `projects show` and `projects list` read it at once;
  - `cycles create prj-ir8-cut` was refused, `conflict — Project prj-ir8-cut is REGISTERING: a Cycle needs it READY`, so
    the Project is seen, not missing. The first try, while IR-1's first cycle ran, was refused earlier by the launch
    gate (`box_not_quiet`), and was repeated on the quiet box;
  - **the launch:** IR-2's Campaign launched on `prj-z-continuum`, registered at 17:16Z on 2026-10-21, two minutes
    after the cutover seeded the five projects (17:13:48Z).

  `prj-ir8-cut` stays on the Spark, `REGISTERING`, as `prj-e41-check` does on the Mac. Its locator names no repository
  that exists, and nothing validated it.
- **IR-10, held, as the cut's set** (`docs/plans/2-4-0-cut-preregistration.md` §13): four rolls on the cut deploy, its
  P5 carrying R3 and R4. No cadence policy or pulse check was declared, no pulse record was written, every correction
  round went through the baseline's handlers, and no run carries a hold, a halt or a restart.

## What this record doesn't cover

- **One Campaign's two cycles at different commits** (IR-3). #2619 blocks it, so IR-3 used two Campaigns'
  calibrations from one instruction revision.
- **A pulse check's behaviour.** The regression profile declares no pulse check, so IR-10, on its own deploy and as
  the cut's set, reads the pulse path as inert, and can't read a change in how a pulse check behaves (the
  pre-registration's §4).
