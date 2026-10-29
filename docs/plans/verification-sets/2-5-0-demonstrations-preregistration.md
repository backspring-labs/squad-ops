# 2.5.0 — pre-registration of the two demonstrations: a Campaign on a repository-backed Project, read by IR-3 to IR-9

**Status: REGISTERED 2026-10-29, before either Campaign is created.** The records each reading names are filled in
§8 as they're read. Uncounted for the regression rolls. The readings are the release's cross-lane scenarios: 2.5's
first half claims a Campaign on a repository-backed Project works end to end, so IR-3 to IR-9 must pass (the plan's
§3). A scenario reported *not run*, or failed, needs the owner's ruling narrowing the claim, named in the cut record.

## 1. Why they run

The 2.5 plan's §2.1 and §2.1a: two Campaigns on private copies owned by the owner's account, never the real
`backspring-labs/continuum`.
- **The main one, on `z_continuum`:** an imported Python service SquadOps didn't build, with no interface manifest
  and an inherited failing check (`lint`). Two features, with an outside change to its `CLAUDE.md` between them.
- **The short one, on `z_shelfnote`:** the greenfield product made from the `fullstack_fastapi_react` blueprint (E.4.6),
  in its first Campaign. One increment, which adds a page.

## 2. What is in place before either launches

1. **Track A is merged:** #2761, #2763, #2764, #2766, #2769, #2770, #2771, #2772, #2773, #2774, #2777, #2778 and #2780.
   Also needed: SIP-0113 §10l's baseline reading and the blueprint lint (its own PR), and #2784, which makes HTTP checks
   read saved values. Both suites need #2784.
2. **One deploy carries all of it:** `rebuild_and_deploy.sh runtime-api`, `sandbox` and the agents, then
   `verify_loaded.py` with 0 not loaded. Its `dep_…` id and commit go in §8. Nothing merges or deploys while a Campaign
   runs, except a fix this pre-registration's stop rule calls for, and §8 names it.
3. **The Projects, recorded 2026-10-29:**
   - **`prj-shelfnote`:**
     - synced, then validated to its upstream `0abef4ea`;
     - Development Configuration revision 2, with a start declaration: the backend and Vite's preview of the built
       pages, ready through the preview's `/api` proxy, with an `http_base` and a `ui_base`;
     - its baseline: `boots`, `backend_tests` and `frontend_tests` all PASS;
     - its derived profile names no gap.
   - **`prj-z-continuum`:**
     - at `15fc9a77`, revision 5, with a start declaration: `continuum run`, ready at `/health`, with an `http_base` only.
       Its server serves no pages, since `main.py` mounts the API alone;
     - `lint` declares its findings reader `ruff`, and `tests` declares `pytest` (H.5);
     - its baseline: `tests` PASS, and `lint` FAIL, attributed `inherited`;
     - four gaps, all disclosed: `no_test_runner` on `web/` and on the three plugin UIs.

   Both starts were booted before recording, in throwaway containers of the sandbox's image. Each was ready within
   2 s.
4. **The requirements** are `docs/plans/2-5-0-demonstrations/z_continuum-requirements.md` and
   `z_shelfnote-requirements.md`. Each is ingested as a `prd` artifact on its Project and named by
   `objective.requirements` (D10 point 3). The ids go in §8.
5. **Each Project's held-out suite** is drafted by the supervisor and approved on revision 5's terms (D11, delegated):
   - a fresh agent's independent review;
   - `heldout_public_check.py`, finding 0 of each suite's markers, with every place searched;
   - each product repository's files and history also searched, since the squad reads them;
   - the approval recorded by counts only.

   Each Campaign pins its own suite. Only digests and counts appear here. **Both were approved on 2026-10-29**
   (§8). The reviewer's verdict for both was *approve with notes*, and its four suite notes were applied before the
   drafts were stored. A search of every literal value, path segments included, covered the gap #2786 names in the
   marker reader.
6. **The project instruction for IR-3:** one record bound to `repo:file:CLAUDE.md@current` on `prj-z-continuum`, written
   before its Campaign is created. Its `mrec_…` id goes in §8.
7. **IR-4's baselines:** `heldout_sweep.py`, and the same with `--goals`, over each suite before its Campaign is
   created, so a value already somewhere isn't credited to the Campaign.

## 3. The Campaigns and their order

- **The definitions:**
  - `docs/plans/2-5-0-demonstrations/z_shelfnote-campaign.yaml`: one increment, `max_cycles` 4;
  - `docs/plans/2-5-0-demonstrations/z_continuum-campaign.yaml`: two increments, `max_cycles` 6.

  Both run on `full-38-tf`, with plan gates `tier`, proposals through `campaign-increment-source` and no `stack`.
- **The short one runs first.** It reads the whole path (record, proposal, build, acceptance on the runners, the page
  rendered, evaluation, promotion, the review request) on one increment, before the main one's operator steps.
- **The main one's outside change (IR-3):**
  1. The supervisor pauses the Campaign while its first increment's cycle runs. The decision is still recorded, and
     the next launch is held (§10).
  2. After the first increment's decision, a commit to `z_continuum`'s `main`, pushed from the owner's account,
     changes `CLAUDE.md`. It adds a convention the second feature meets: an endpoint that reads one item by its id
     answers 404 for an unknown id.
  3. `projects sync`, then resume.
  4. The next launch waits for the Project's reconciliation. The supervisor reconciles: `projects validate`,
     `configure` (revision 6, the same technical block) and `baseline --capture`.
  5. The launcher rebases the campaign branch onto the reconciled commit and launches (SIP-0109 §24cm).
- **Rulings:** proposals are the supervisor's, under the owner's 2.5 grants. Each is approved as it stands unless the
  rails refuse it. A plan gate the tier escalates is answered from the requirements.
- **At each Campaign's close:** `squadops campaigns push-review` opens its review request on the product (§24ci (b)).
  The owner merges it, or not; the readings don't depend on it.

## 4. The readings, each with what falsifies it

Each is read from the stored records after the Campaign closes, or as each cycle ends. "Not exercised" is reported
for a path the Campaign never took, never "passed".

**IR-3, completed** (`z_continuum`). It closes the gap 2.4's integration record names: one Campaign's two cycles at
different commits.
- **(a)** Every cycle of the first increment binds the instruction at `15fc9a77`'s `CLAUDE.md`, read from
  `memory_cycle_bindings`.
- **(b)** After the outside commit is synced, no launch proceeds at the old pin. The control log shows the launch
  refused or held, by the Project's own gate (`STALE_SOURCE_PRECONDITION` or the escalation that holds the intent),
  until the reconciliation.
- **(c)** Every cycle of the second increment binds the new `CLAUDE.md` content at its own commit, the rebased head.
- **(d)** A standalone cycle created on `prj-z-continuum` after the reconciliation binds the new content. It is
  cancelled once its binding is read.
- **(e)** No re-binding of the Campaign appears except as a recorded intervention. None is expected.

It is **falsified by** any cycle bound to content other than its own commit's, a launch at the old pin after the
sync, or a re-binding with no intervention row.

**IR-4** (both). No held-out step value reaches a prompt, an envelope, a squad container, the Project Context, the
handoff, an instruction, the managed clone, a workspace or the product repository.
- **The commands:** `heldout_sweep.py --suite … --digest … --campaign <cmp>`, with `--host-root` for:
  - the Campaign's archive (`var/campaigns/<cmp>`);
  - a fresh clone of the product repository, holding every ref, its review branch included;
  - the managed clone.

  The same is run with `--goals`.
- **It passes when:**
  - no step marker is found outside the suite's store and the evaluator's records;
  - each goal is found only in the proposal task's own records and the evaluator's (§10t ruling 7), and at least once
    there.

  Any place unsearched fails it.

**IR-5** (both). For each accepted increment, four identities resolve to one another through their mappings
(contract 4), and none is stored in another's field:
- the delivery's sandbox revision;
- the campaign branch's commit;
- the Campaign's accepted tree identity;
- the evaluation record's `evaluated_tree_identity`.

It is **falsified by** a mismatch, or a field holding another's identity.

**IR-6** (`z_continuum`). Its evaluation records, for the calibration record and each increment:
- name the start declaration's revision and its `http_base`;
- run each HTTP scenario on the declared base;
- record the suite's one page scenario `not_applicable`, since the declaration serves no UI;
- read no manifest, and fall back to no sample application: lint reads `not_a_scaffold_stack`, and nothing starts by
  a stack.

It is **falsified by** a page scenario run or failed rather than not applicable, a manifest read, or a stack start.

**IR-7** (`z_shelfnote`). Its calibration record and its increment's cycle are each evaluated through the same path as
`z_continuum`'s:
- §10l's baseline reading of the record's commit;
- the captured tree at the increment's end (§10aa);
- each record naming the registry's Project.

Lint is measured by the blueprint's rule set (§10l), not reported `not_a_scaffold_stack`. It is **falsified by** a
missing baseline reading, a record on the vault's partial tree, or the blueprint's lint unmeasured.

**IR-8** (`z_continuum`). The evaluation records name `prj-z-continuum`, the registry's Project, and
`config/projects.yaml` names none of it. It is **falsified by** a record naming another Project, or a YAML entry for it.

**IR-9** (`z_continuum`). Read in each increment's native verification beside its evaluation record:
- `lint` reads FAIL, attributed `inherited`;
- or `introduced`/`regressed` only where its findings grew, by H.5's reader, now `ruff`;
- the evaluation's reading is its own scenarios'.

Neither derives from or rewrites the other. It is **falsified by** a grown finding read `inherited`, `inherited` read
where nothing grew but the attribution differs, or an evaluation field copied from the native verification, or the
reverse.

**Read beside them, with predictions:**
- **The baseline readings (§10l):**
  - `z_continuum`'s suite: five pass, four fail (every scenario that reads an item by its id), and the page scenario
    is not applicable. Two of the five pass before either feature exists, because FastAPI already answers 404 for an
    unknown path. They guard against a build that answers otherwise;
  - `z_shelfnote`'s suite: five pass and four fail (every search scenario, the page one included).

  This was read on 2026-10-29 for the HTTP scenarios against today's products, outside the deploy, along with a
  minimal correct build of each feature that passed every one.
- **#2780's anchored page** (`z_shelfnote`):
  - the change request's page criterion names `/search`'s anchor;
  - acceptance renders `/search` on the candidate, started from its declaration;
  - the route is held by that anchor.

  **The missing-route negative is a replay, and is named as one:** the same renderer
  (`DeclaredStartRoutes.render`) on the accepted candidate with the added route's element removed. It must read the
  route broken and the increment rejected. No squad can be made to omit the page, so no run is claimed for it.

**Read beside them, without a prediction:**
- each cycle's verdict;
- the repairs and retries, by #2664's and #2743's rules;
- whether the review-request push's ref-follow recovery (§24ci (b), #2772) ran. It's exercised only by a git failure
  after the registry's commit, which a run can't arrange, so it stays unit-tested and is named *not exercised* if it
  doesn't run.

## 5. The stop rule

- **A seam finding on Track A's path stops that Campaign:** a reading above falsified, or a launch, rebase, binding,
  acceptance or evaluation that departs from its SIP's text.
  - The Campaign is paused at its next decision.
  - The finding is filed with its evidence.
  - A fix lands, and is deployed and recorded in §8.
  - The Campaign resumes, or a fresh one repeats the reading.
- **Budget:** two rounds per Campaign.
- **A finding in the squad's output, or in the evaluator,** is filed and the Campaign continues.
- **A failed cycle is retried at most once,** by the Campaign's own policy.

## 6. Box time

About 3 box-hours for the short one and 4–6 for the main one, as the plan guides. One thing runs at a time.

## 7. What it does not cover

- **Next.js, and a product with no Python.** Both products are Python services, and `z_shelfnote`'s frontend is
  React on Vite.
- **`z_continuum`'s UI.** Its server serves no pages, so its page surface is recorded not applicable, never measured.
- **The page scenario's validation before the run.** Its steps and checks are revision 6's vocabulary, read on
  `group_run`; this Campaign is its first reading on `z_shelfnote`.
- **Any verdict's quality.** The evaluations are reported only (phase 1's rule).
- **The secrets resolution (#2421),** which neither start declaration needs.

## 8. Records, filled as read

| what | value |
|---|---|
| deploy | |
| `z_shelfnote` suite digest, approval | `a1a6a0b7…`, 9 scenarios, approved 2026-10-29 (`var/verification_sets/2-5-0-demonstrations/suite-approvals.md`) |
| `z_continuum` suite digest, approval | `7ce88042…`, 10 scenarios, approved 2026-10-29 (the same record) |
| `z_shelfnote` requirements artifact | `art_c8768ea0ea71` |
| `z_continuum` requirements artifact | `art_da4c3bd75d8f` |
| IR-3's project instruction | |
| `z_shelfnote` Campaign | |
| `z_continuum` Campaign | |
| the outside commit | |
