# 2.4's SIP-0112 demonstrations: the readout (brownfield and greenfield, E.7, G6)

*The MacBook lane, 2026-10-21. It reads the runs against the pre-registrations,
`2-4-0-brownfield-preregistration.md` and `2-4-0-greenfield-preregistration.md`, which were fixed before each first
cycle. The Spark lane ran every stage on its own deploy and posted each result on #2410 and #2412. This record is
read from those posts and from the products' repositories.*

## In one paragraph

SquadOps took an unfamiliar existing product, a copy of continuum, through all six pre-registered stages:
1. registered it with no change to the product;
2. captured its inherited baseline (`tests` PASS, `lint` FAIL);
3. delivered a first feature through the product's own checks and opened it as a pull request;
4. read an outside developer's change as drift;
5. reconciled the configuration and baseline at the new commit;
6. delivered a second feature on top.

For the greenfield product (Shelfnote), the Spark registered the repository the Mac had created and contributed its
first change, which turned its failing `backend_tests` to PASS. That change was merged and read back as integrated.

Three of the demonstrations' four findings are in SquadOps itself:
- **Stage 5 as pre-registered didn't hold:** a cycle at the stale baseline was accepted before `validate` (#2608).
  It's fixed in #2610 (merged), and the Spark's re-run of stages 4–5 with it deployed refused the cycle.
- **A sync filed the squad's own merged files as outside change** (#2606, fixed in #2610, merged).
- **The acceptance policy can't see new failures inside a check that was already failing** (#2609, open). It
  accepted a second feature that added three lint findings.

## The deploy, the squad, the inputs

- **Deploy:** the Spark's `dep_ceda294644b3`, framework `8f39db05`, after the owner approved the project
  registry's cutover to Postgres (#2408's designed step; the Spark had run the read-only YAML registry until then).
- **Squad:** `full-38-tf`, the six-agent roster on the model the Spark serves (pre-registration amendment 3). `full`
  names a model the Spark doesn't serve.
- **Plans:** the operator's, in `docs/plans/2-4-0-brownfield/` and `docs/plans/2-4-0-greenfield/`. The squad wrote
  the code and the tests, not the plan, so what these runs show is a planned change delivered through a
  product's own process.
- **Products:** `backspring-labs/z_continuum`, a private copy of continuum, chosen by the owner so that nothing is
  written to the real product until the framework is solid; and `backspring-labs/z_shelfnote`.

## Brownfield, stage by stage

| stage | what ran | read against the pre-registration |
|---|---|---|
| 1. registration | `prj-z-continuum` imported, then `validate`: READY at `43369054` | **held.** A stable ID, the record in the runtime's registry, and no commit to the product |
| 2. baseline | configuration revision 1 (instruction source `CLAUDE.md`); capture at `43369054` | **held.** `tests` PASS, `lint` FAIL, both inherited and named |
| 3. first feature | `cyc_709e3a912150` / `run_7bca712bd35b` (4 min): `continuum --version` | **held.** Verification `art_0d17c83b411c` accepted (`tests` PASS, 60 passed; `lint` FAIL inherited, 59 findings before and after). The capture `2f6b3baa` holds only the two changed files, byte-identical to what was verified. z_continuum#1 opened, recorded pending |
| 4. outside change | z_continuum#1 merged (`17a819f3`, a merge commit), then the outside commit `ba8fa68b`: `CLAUDE.md` and `src/continuum/__init__.py`, pushed from the owner's account (amendment 2); then `sync` | **held, with a finding.** Upstream read past the baseline, `CLAUDE.md` named `instructions` (the one category that invalidates evidence), the contribution read as integrated at `2f6b3baa`. But `source` also listed the contribution's own two files beside the outside one (#2606) |
| 5. reconcile | a cycle at the old baseline; then `validate`, `configure`, `baseline --capture`, `sync` | **didn't hold before validation.** The cycle at `43369054` was accepted (`cyc_001b267cac63`, cancelled after 14 s with no development; #2608). After `validate` (READY at `ba8fa68b`), both the old precondition and a cycle at the new commit were refused until configuration revision 2 and the baseline at `ba8fa68b` were recorded; the last `sync` read no drift |
| 6. second feature | `cyc_c1b7dba3ae25` / `run_2ad3b6e34552` (3 min): the version in `inspect --json` | **held as the policy reads it, with a finding.** Verification `art_d6fa8d0006ae` accepted (`tests` PASS, 61 passed; `lint` FAIL inherited). Capture `0c814a7c`, z_continuum#2 opened, recorded pending. Read finding by finding, ruff went from 59 to 62, and the policy couldn't see it (#2609) |

**Distinguishable throughout:**
- each run's verification record is an artifact;
- the contribution states and the sync findings were read back from the API, and their records are on #2410.

## Greenfield, stage by stage

What ran on the Mac (the first commit, configuration, a first accepted change and an outside change) is listed in
the pre-registration. On the Spark:

| stage | what ran | read against the pre-registration |
|---|---|---|
| 1. registration | `prj-shelfnote` imported from the existing repository, then `validate`: READY at `093ca2a9` | **held.** No commit to the product |
| 2. baseline | configuration revision 1 (instruction source `CONTRIBUTING.md`); capture | **held.** `boots` PASS, `backend_tests` FAIL (no tests yet), `frontend_tests` PASS |
| 3. change | `cyc_7bf35ffb4cc5` / `run_1f37f577c7ee` (3 min): the books API | **held.** Verification `art_1f198cf507d5` accepted, with `backend_tests` **resolved** (8 passed). The capture holds only the two product files |
| 4. contribution | `contribute`: z_shelfnote#1, commit `2dd04e7f` | **held.** The head is the verified tree, recorded pending |
| 5. integration | merged by the MacBook lane as the owner's stand-in (`9bcdc7c0`); `sync` | **held.** Read as integrated at `2dd04e7f`. The same sync listed the contribution's own files as source drift (#2606) |

## The re-run of stages 4–5, with #2610 deployed

On the Spark's `dep_31fe124fd638` (framework `88e5bf7e`, 166 of 166 loaded checks), with `prj-z-continuum` at
`ba8fa68b`, revision 2:
1. **The second contribution merged:** z_continuum#2, by a merge commit `6af35238`, made by the MacBook lane as the
   owner's stand-in. Its review note (three new ruff findings, #2609) stays on the pull request.
2. **Another outside commit,** `77cb6d66`, pushed from the owner's account. It adds a line to `CLAUDE.md` and
   changes a docstring in `src/continuum/main.py`, neither of which #2 touched.
3. **The sync** (`demo-a-sync-3`, `source-drift/v2`), verbatim on #2410, matched every expected line:
   - `changed`: `instructions` `CLAUDE.md`, and `source` `src/continuum/main.py`;
   - `integrated`: `cyc_c1b7dba3ae25` at `0c814a7c`, `source` `src/continuum/cli.py` and
     `tests/test_cli_inspect_version.py`, shown in the CLI's table as `source, by cyc_c1b7dba3ae25`;
   - `relevant`: `instructions`;
   - both contributions integrated.
4. **A cycle at `ba8fa68b`, revision 2, before `validate`:** HTTP 409 `STALE_SOURCE_PRECONDITION`, "upstream is at
   77cb6d66…, past its baseline ba8fa68b…, with instructions changed (projects sync): reconcile it at the new commit
   first". No cycle was created.

So stages 4 and 5 now hold as pre-registered. The Spark lane then reconciled the Project at `77cb6d66` (validate,
configuration revision 3, baseline, a closing sync), so it isn't left held.

## IR-2, live on the Mac

**What it checks (§8.4):** one external Project at one pinned revision, launched standalone and through the Campaign
launcher, reaches `prepare_cycle()` with the same typed source context and Development Configuration revision, and
each unit pins a SIP-0110 snapshot under its own owner.

**The setup:** `prj-shelfnote` on the Mac (`dep_cc31bd6fd406`), reconciled at `433f6c51`, configuration revision 3,
baseline `boots`, `backend_tests` and `frontend_tests` all PASS.
- **The standalone cycle:** `cyc_2c995f503391`.
- **The Campaign:** `cmp_e616b0a78aa6`, uncounted, one cycle allowed (its definition is in the scratchpad, not
  committed). Its calibration cycle is `cyc_95c8659ae6c5`, launched by `campaigns start`.

**The result:**
- **Both cycles' source contexts are identical,** read back from the API: `project-source-context/v1`, baseline
  `433f6c51`, revision 3, record version 16, upstream `433f6c51`.
- **Each unit pinned its own snapshot:** the standalone cycle `snp_ef0e4ef30fa9e74f`, and the Campaign
  `snp_c00e517025eabfef`. The Campaign's cycle binds the Campaign's: asked for its own, the API answers that it
  "binds the campaign's snapshot".
- **Both runs then failed alike,** after preparation, at provisioning: "implementation plan required but absent".
  No plan was given, since the check is preparation's, and the Campaign completed.

So IR-2 passes.

## The findings

| issue | what | where it stands |
|---|---|---|
| #2606 | a sync filed an integrated contribution's own files as outside source drift | fixed in #2610 (merged): the drift document lists them under `integrated`, apart from what changed outside. Shown in the re-run below |
| #2608 | a cycle was accepted at a baseline a sync had already found upstream past, with relevant drift | fixed in #2610 (merged): `prepare_cycle` refuses until validation. Refused live on the Mac (`dep_cc31bd6fd406`) and in the re-run below |
| #2609 | the acceptance policy reads an already-failing check only as a whole, so new failures inside it pass | open. It needs a design: a check declares how its findings are read, the baseline keeps them, and new ones are refused |
| #2607 | every file the squad emits loses its final newline, and an edited file loses the one it had | open. Seen in all three pull requests; no check reads it |
| #2605 | the CLI's 30 s request timeout is shorter than a baseline capture, so a capture that completed reads as failed | open (the Spark lane's). #2603 (merged) keeps a contended memory change under it |

**Two quality notes no check caught:**
- Stage 6's change also deleted four blank lines between top-level functions, which nobody asked for.
- Stage 3's change dropped `cli.py`'s final newline.

A maintainer would ask for changes on z_continuum#2, and it is left open.

## What this doesn't cover

- **The squad framing its own plan:** every plan here was the operator's.
- **IR-3:** a Campaign's admitted instruction binding under an outside instruction change. Stage 4's change was read
  by `sync`, and no Campaign was running.
- **IR-7**, which waits on Outcome Evaluation's phase 1.
- **Creation and evolution on one deploy:** Shelfnote's first commit was made on the Mac, and its contribution on
  the Spark.
- **The archive and handoff (E.4.5),** not in 2.4 by the owner's ruling.
