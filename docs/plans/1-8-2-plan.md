# 1.8.2 — plan

**Rev 3, 2026-09-24 — the owner's rulings.**
- **Decision 1, ruled: both.** Campaign readiness is the headline, measured first on deploy A, and
  the flip rides beside it, strictly conditional:
  - N is registered on deploy A's existing supply (the 1.8.1 supply diagnostics and the counted
    set), with no extra rolls
  - the flip goes on deploy B only if N is met
  - the flip and deploy B are the **second** thing to drop when the line runs long (§3.9)
- **Decision 7, ruled: attach.** Each line's full verification records are attached to its GitHub
  Release at the cut, after a credential scan (§3.2 item 16).
- **Decisions 2–6 and 8** are adopted as recommended at merge.

§2.3, §3.5, §3.7, §3.9, §4.1, §4.2, §6 and §7 are rewritten to match. Rev 2's and rev 1's status
blocks are kept below for the record.

**Rev 2, 2026-09-24.** Rev 1 recommended the campaign-readiness shape but gave the claim no test.
Rev 2 adds four things, at the owner's ask:
- **a registered test of the claim:** the `unattended-chain` diagnostic (§4.1), with the driver
  support it needs (§3.2 item 14)
- **the hang bound, verified and made explicit:** the dispatch timeout becomes a declared value, not
  an inherited one (§3.2 item 15)
- **where an unattended cycle's review gate gets its decider:** Campaign's design, with the chain
  using the driver's registered policy and saying so (§2.3, §8)
- **a capacity section with a drop order** (§3.9)

**Rev 1, 2026-09-24 — written after the 1.8.1 cut** (v1.8.1 tagged at `7f9af662`; record in
`docs/plans/1-8-1-window-preregistration.md` §10c–§10f). Rev 0 was drafted on 2026-09-22 at the
1.8.1 deploy-A N reading, on the owner's ask, with every row that depended on deploy B′ left open.
Rev 1 writes those rows, adds what the window, the cut and the post-cut worktree cleanup taught,
and **changes the recommended shape of the line** (§2.3, §7 decision 1): from "re-supply N and
land the flip" to **"make a cycle safe to leave running unattended"**, the property Campaign
(2.0's headline) needs from every cycle it launches. Rev 0's shape is kept beside it as the
alternative, for the owner to choose between.

Written from:
- the 1.8.1 records: the deploy-A pre-registration §10 (22 diagnostic records, 6 counted rolls,
  N = 4 of 6) and the window pre-registration §10a–§10f (B′ and B″ shakeouts, the window 0 / 0 / 6,
  the cut record)
- the 1.8.1 plan's hand-off (§2.3, §3.4, §3.8, §6, §7 step 13)
- SIP-0086 §12a and SIP-0096 §17a as re-targeted on 2026-09-17
- SIP-0107 §38 step 7 and §39.8
- SIP-0108 §10o (Solo kept)
- the Campaign SIP (`sips/proposed/SIP-Campaign-Orchestration.md`)
- the tracker on 2026-09-24: 28 open issues, each placed by name (§5)

**1.8.2 is the model-capability tranche and the line that answers what 1.8.1 found.** The 1.8.1
plan handed it two capability amendments: SIP-0086 §12a (self-evaluation becomes the model's
compile loop) and SIP-0096 §17a (a contested result: the producer's dispute becomes evidence),
with #1581 beside them. The 1.8.1 line then added three kinds of inheritance:

- **A mechanism, found twice.** When a qa-owned suite fails, the loop tends to *re-author* the
  suite rather than repair it in scope. Deploy A found it on both stacks (§10e there). The window
  found it again on a Solo roll (pair 6: a dev repair verified, its retest failed, the suite
  re-authored and passed).
- **Seams that matter the moment cycles run unattended.**
  - A cancelled run's already-dispatched task still runs, and the isolation gate cannot see it
    (#1648).
  - The SIGSEGV is bounded, not contained (#1626).
  - The repair brief's decision section cannot be read from any stored source (#1661).
- **Instrument and housekeeping debts.**
  - The screenshot capture seeds from a fixed file that fits only one authored interface (#1665).
  - The verification driver writes its records into whichever checkout launched it. That left
    the only copies of the 1.7.4 and 1.7.5 records inside worktrees, and a routine cleanup would
    have deleted them (§1, the last row).

Three facts shape it, stated once:

1. **SIP-0107's flip precondition is unmet twice, for the same cell.** 1.8.0 read 5 of 6 and 1.8.1
   read 4 of 6, both with qa × Next.js empty. **Whether 1.8.2 re-supplies N is §7 decision 1.** A
   count on a deploy that fixes the mechanism would be a new measurement, not a retry. But the
   window showed the qa × React cell *can* supply (pair 3's squad repair: a qa scoped edit of 4%,
   verified and retest-passed), so the empty cell is Next.js-specific. And the flip itself is not
   on Campaign's path.
2. **The scoped repair targets small but does not always fix.** Across 1.8.0–1.8.1, 18 repair
   responses were recorded: 12 scoped edits, 2 fills, 4 empty, and **0 whole-file fallbacks**.
   Convergence among correcting rolls rose from 38–60% (1.6.5–1.7.3) to 67–80% (1.8.x), but that
   is descriptive, confounded and small-N. And the recorded "span" overstates edits: pair 5's
   Solo repair replaced 95% of a file's region to make a change of about 12 lines. 1.8.2 measures
   this properly (§3.2 items 1 and 12) before it fixes anything.
3. **The amendments' diagnostics are fixed and are not re-derived.** `compile-loop` and
   `false-criterion` are as the 1.8.1 review settled them, reproduced in §4.1.

Rules carried without discount:
- one kind of change per measured deploy
- no fault, no prediction
- every field three-state
- every diagnostic reaches its seam on the pinned deploy
- §5a amendments go in the SIP, in the PR that diverges
- a counted set is a shakeout round
- a seam reached is not a cell supplied, and the per-cell tally is read at each diagnostic's
  clearance (§4.4)
- **new from 1.8.1:** a registration's reading source must be able to hold the reading. I2 and
  H3's rule section were registered on LangFuse's 10,000-character input and could never be
  read (#1661).

---

## 1. What the 1.8.1 line says this release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| **N read 4 of 6, qa × Next.js empty**: the registered supplier (five runs) produced no scoped qa transaction; the two Next.js counted rolls produced none | deploy-A pre-registration §10e | the flip did not land. **Whether it is re-counted here is §7 decision 1** |
| **the loop re-authors instead of repairing**: on React, three accepted anchored qa edits (5%, 3%, 3%) each failed their retest and the qa task re-emitted the suite; on Next.js the qa repair never produced a patch | `cyc_3ba9057e5cdf`, `cyc_38cbb5b54693`, `cyc_9e47702af705` | **an instrument first** (§3.2 item 1), then the fix it names (item 6) |
| **the same shape, and its counterexample, on the window**: Solo pair 6, a dev repair verified with its retest failing, then re-authored and passing; squad pair 3, a qa scoped edit of 4% whose retest passed (the qa × React supply A lacked) | window pre-registration §10e; `cyc_04190c786d73`, `cyc_3a3d9ee8f12d` | the retest readout reads both. The counterexample says the mechanism is not "qa scoped repair never works", which narrows item 6 |
| **two cap-exhausted emissions, one per stack**: each spent the flat 12,288-token cap on reasoning and emitted nothing | `cyc_b98c45fcd5c8`, `cyc_4d9602ce0a66` | the cap fix (§3.2 item 2). A count of two is stated as a count |
| **the qa repair's second attempt is a re-emission, not a repair** | deploy-A §10b | §12a's "the pass sees what it edits" applies to the re-take (§3.3) |
| **a wrong-locus round**: a qa-suite failure routed to a dev repair whose patch broke the build | `cyc_5bbf85db4622` | §17a's dispute is the mechanism (§3.4) |
| **the SIGSEGV is bounded, not contained** (#1627 bounds, #1628 moved the crash) | #1626 | **containment in the prelude** (§3.2 item 3) |
| **two instrument defects on first diagnostics** (#1623, #1631), and a class-closing test that could not be made sound (#1632) | deploy-A §3d, §6 | a runtime marker self-check at launch (§3.2 item 4) |
| **a stale identity pin** refused the first counted roll | deploy-A rev 5 | a pin-staleness assertion (§3.2 item 5) |
| **the window: 0 / 0 / 6, "neither"**, cost within about 2%, all 12 rolls accepted-functional; the arms as built differ in the identity fragment and the correction protocol only | window pre-registration §10e; SIP-0108 §10o | **no arm axis on this line** (§4.3). The Free-Solo window and the placement experiments are 2.0 planning inputs. Solo stays declared for them |
| **SIP-0108 implemented; Solo kept as a declared mode; no teardown** | the 1.8.1 cut record §10f; SIP-0108 §10o | nothing to tear down. The `solo` profiles stay seeded and the Han image stays buildable |
| **a cancelled run's dispatched task still runs** (#1648), and the isolation gate reports a quiet box while it does | window §10a; #1648 | **the agent-side fix is this line's** (§3.2 item 10). A campaign cancels, retries and forks cycles; a ghost task behind the next cycle's first task is the #1648 shape, systematically |
| **I2 and the Solo rule section are unaskable**: the repair brief exceeds the stored prompt's cap | #1661, carried by ruling | record which decision section rendered (§3.2 item 11) |
| **a repair "span" overstates the change**: pair 5's structural edit spans 95% of the file for a diff of about 12 lines | window §10e; the pair-5 records | the convergence replay measures emitted size, actual diff and entity share, by mode (§3.2 item 12) |
| **the screenshot capture fits one authored interface**: the squad's app used `location` and `/participants` and had no `/` route, and a blank page passed as a capture | #1665; v1.8.1 package PR #1664 | the capture reads the run's own manifest and refuses a blank page (§3.2 item 13) |
| **verification records stranded in worktrees**: the driver writes `var/` into the checkout that launched it; the 1.7.4 and 1.7.5 records existed only inside two driver worktrees (97 and 81 files); 18 stale worktrees and 86 stale branches were found | the post-cut cleanup of 2026-09-24, preserved and verified byte for byte | **records land in one place, and hygiene runs at every cut** (§3.2 items 8–9; §7 decisions 7–8) |
| **the 1.8.1 ops rider was not run**: #1177, #176 recipe 2, #1176, #1408 and #1412, re-placed here by ruling (fourth plan) | the 1.8.1 cut record §10f | bounded on the idle box after the set (§3.6) |

---

## 2. Why this release, on the roadmap

### 2.1 The tranche: two amendments, each with the diagnostic that forces its mechanism

A release whose central change is meant to be easy to interpret should not gain two
behaviour-changing mechanisms at once, and 1.8.1 measured the substrate 1.8.0 measured. 1.8.2 is
where the substrate changes, and the change is measured the same way: one fault per mechanism,
one prediction per fix, read on a pinned deploy.

### 2.2 The empty cell is a capability finding, not a supply accident

The qa repair on the App Router stack produced no patch in any of its opportunities. Where the
React qa repair produced one, most retests failed and the loop re-authored. §12a was drafted
because the compile loop is one shallow pass on truncated evidence, and the same shallowness shows
as a repair that edits the named file without fixing the named failure. The window adds the
counterexample: a React qa scoped edit that passed its retest. **The amendment and the finding are
one question**, and it is narrower than rev 0 stated.

### 2.3 What this line is for: unattended cycles, and the flip if N is met (§7 decision 1, ruled)

**The ruled shape (rev 3): both, with campaign readiness first.** 1.8.2's headline claim is *a
cycle you can leave running unattended*. The line keeps:
- **the capability work:** §12a, §17a with #1581, the qa-lane fix scoped from the readout, and the
  cap fix
- **the seams a campaign exercises by construction:** #1648 agent-side (a campaign cancels, retries
  and forks cycles), #1626 containment (a crash must not take a chain down), #1661 (the record says
  what each round was told)
- **the housekeeping that keeps unattended evidence safe:** §3.2 items 8–9

**The flip rides beside it, strictly conditional.** N is registered on runs deploy A makes anyway:
the 1.8.1 supply diagnostics and the counted set, which now does two jobs, the regression bar
(L1 and functional yield) and the N count. No extra rolls. **Deploy B happens only if N is met**,
and it carries the flip alone, as 1.8.1 designed it. If N comes up short a third time, nothing is
spent past the reading, SIP-0107 stays `accepted` with the third count stated, and the 1.9 plan
names step 7 as a 2.0 decision. The flip barely touches the unattended seams: its refusal bites
only on an unauthorized whole-file repair, and 1.8.0–1.8.1 recorded none in 18 responses. It is
also explicitly droppable (§3.9), so a slow N or a deploy-B shakeout finding cannot hold up the
campaign-readiness cut. The honest odds: qa × Next.js has been empty twice because the qa repair
on Next.js never produced a patch, and the qa-lane fix may not reach that stack. Meeting N is
possible, not likely.

The headline follows the owner's stated priority (Campaign, then cycle memory) and the roadmap's rule that a campaign
automates over trustworthy cycles: every recurring failure a single cycle has, a campaign
multiplies.

**What "unattended" means here, and what it does not.** A cycle is safe to leave running when
four things hold:
- it always reaches a terminal state within a bound
- a cancel leaves nothing running behind it
- a crash or a hang is contained and recorded as a typed fact
- the next cycle starts on a genuinely quiet box

The `unattended-chain` diagnostic (§4.1) asserts all four on K back-to-back cycles. **It does not
cover who decides a cycle's review gate.** `validated-fullstack` has a human gate
(`progress_plan_review`), and today the driver approves it by a registered policy constant
(`--as-agent`, the decider recorded). A campaign needs a declared decider for that gate. That
belongs to Campaign's own design, where its `escalate` outcome already maps to a gate decision
(`sips/proposed/SIP-Campaign-Orchestration.md` §7.1). 1.8.2 does not build it. The chain uses the
driver's policy and says so on its record (§8).

*For the record:* rev 0 recommended the flip line alone; rev 1 and rev 2 recommended campaign
readiness alone. The owner ruled both on 2026-09-24, on the argument above that the flip's
incremental cost is a registration on existing runs plus a conditional deploy.

---

## 3. The content

### 3.1 Preconditions, before the first code PR

- The 1.8.1 line cut by its seven steps (done: v1.8.1, `7f9af662`, the Release, package #1664).
- This plan merged on the owner's review, with §7 decision 1 ruled, and the SIP sections' target
  lines amended (§12a and §17a already say 1.8.2; the amendment is the date and this plan's path).
- Main's every CI job green at the branch point.

### 3.2 The prelude: deploy A, behind the diagnostics and a counted set

One PR per causal unit. Items 1, 4, 5, 8, 9, 12, 13, 14 and 16 are `scripts/dev` or tooling (no
deploy). Items 2, 3, 6, 10, 11 and 15 move the framework. Item 15's compose line is the owner's
edit (CLAUDE.md's Docker rule), carried in its PR's body as Han's service block was.

1. **The retest readout: instrument only, `scripts/dev/`.** For every patch retest the driver reads
   the retest's `test_report.md` against the repair's revision form:
   - which tests failed after the patch
   - whether the failing test's frame lies inside the edited region
   - whether a test that passed before the patch fails after it

   That gives three typed fields on `loop_texture` (`retest_failures_in_edited_region`,
   `retest_failures_outside`, `retest_regressions`), each with its unaskable state. **Replayed
   first on the 1.8.1 corpus**: deploy A's four failed qa retests, Solo pair 6's failed dev retest,
   and the two retests that passed (squad pair 3, Solo pair 5) as controls.
2. **A cap-exhausted pass is retried with its fact, or the budgets are separated.** Two readings on
   main decide which, and are read before the PR is scoped:
   - whether the provider's completion limit counts reasoning tokens
   - whether the flat cap is the request profile's or the squad profile's

   The fix follows the R1 shape (#1372): an emission that hit the cap with zero fenced output is
   retried once with the fact "your previous response reached the output limit before any file".
   #1176 is read beside it (§3.6).
3. **#1626 containment.** The JSX structural parse runs in a subprocess. A child that dies (`-11`)
   returns `None`, which the repair path already treats as a structural miss. About 180 lines at one
   seam. #1626 closes when the `redelivery` diagnostic (§4.1) reads the parent surviving.
4. **The marker self-check at set launch (driver only).** At preflight, one synthetic line per
   collector marker goes through `_runtime_lines_of_interest`, and a marker the filter drops refuses
   the launch by name. Closes #1632.
5. **The pin-staleness assertion (driver test).** A line's config-hash and snapshot prefixes must
   differ from every prior line's unless annotated with why they didn't move.
6. **The qa-lane fix, scoped from item 1's reading.** Not designed here. There are two likely
   shapes:
   - (a) the edit lands outside the failing test's frame, which the repair brief fixes by showing
     the failing assertion
   - (b) the edit lands in the frame and the suite still fails on a re-authored assertion, a fill
     interaction on Next.js

   Either way, the re-take after a refund becomes an edit request on the shown suite (§12a change
   3). The window's passing qa × React edit is the control any fix must not regress.
7. **#1621 and the title case (tooling).** `check_pr_closure.sh` reads the title and the commit
   messages beside the body. **#1639** (`regen_fragment_manifest.py --write` rewrites the wrong
   entry when one stored hash is a prefix of another) rides with it: same shape, tooling that
   corrupts a record it guards.
8. **The driver's records have one home (from the cleanup).** `verification_set_driver.py` writes
   records under the **main checkout's** `var/`, found with `git rev-parse --git-common-dir`,
   whichever checkout runs it. It refuses to write elsewhere, and the record names the checkout
   and HEAD it launched from. **Failure it prevents:** a driver launched from a worktree leaves
   write-once evidence, gitignored and invisible to `git status`, inside a directory that looks
   disposable. This happened to the 1.7.4 and 1.7.5 records.
9. **Worktree and branch hygiene (tooling plus the cut procedure).** A new
   `scripts/dev/worktree_hygiene.py`:
   - lists every worktree and local branch with its PR state, its uncommitted and **ignored**
     content (`var/`, a real `data/`), and whether that content exists in the main checkout
   - preserves missing records into main's `var/` (a file that differs is kept under a suffixed
     name) and archives them
   - removes what is merged
   - previews by default and acts only with `--apply`

   It is written from the 2026-09-24 cleanup, which it must reproduce on a fixture. **CLAUDE.md's
   release-cut procedure gains a housekeeping row**: `worktree_hygiene.py --apply` after step 7,
   so it runs at least once per line.
10. **#1648 agent-side: a task whose run is cancelled is dropped.** Before running a consumed task,
    the agent consults its run's status, and it re-checks at the natural await points of a long
    handler (after the LLM call, before persisting). How it consults the run's status is the PR's
    design, table-checked against every consume path. A cancelled run's task is acked and recorded as
    `skipped: run cancelled` rather than run to completion. The executor side (#586) already stops
    between tasks. **Wiring test** entered at the agent's consume path with a run cancelled after
    dispatch. The window's #1648 guard becomes unnecessary once this is loaded.
11. **#1661: the rendered decision section is recorded.** The repair handler records which decision
    section rendered (`lead`, `rule`, or none) as a field on the repair's output metadata and a log
    line. That fact is what I2 and H3 ask, and it needs no 10,000-character prompt store.
12. **The convergence replay: scoped against whole-file (driver-side harness, no platform
    change).**
    - **Inputs:** stored failing correction rounds.
    - **Tree:** rebuilt from `run_checkpoints` and the vault, and **admitted only if the failed
      task's typed checks reproduce the stored failure signature on it**. Non-reproducing rounds
      are dropped and counted.
    - **Arms:** each round is repaired through the product's own `CorrectionRepair` (with an
      injected dispatcher) under two prompt variants. The scoped arm uses today's
      `request.cycle_repair_task`. The whole-file arm uses the pre-1.8 revision instruction inside
      today's brief, loaded from a separate fragments directory by the harness, not through a
      product flag.
    - **Samples:** three to five per arm per round.
    - **Judge:** the deployed `PatchAcceptance` with a sandbox retest.
    - **Measures, per response:** retest pass, regressions, **emitted size, actual diff and the
      entity's share of the file, by mode** (the pair-5 lesson), empty responses, tokens and wall
      clock.

    Predictions are registered before it runs. It runs overnight on the idle box. The seams it
    needs were confirmed injectable on 2026-09-23. It still has to be confirmed whether the repair
    handler can be built outside its container; if not, it runs through `docker exec`.
13. **#1665: the capture reads the run's own interface.** `capture_delivered_app.py` maps the
    seed's fields and endpoints onto the run's `interface_manifest.yaml`, or refuses with the
    mismatch named. It takes client routes from the manifest or the delivered router rather than
    assuming `/`, and it refuses a screenshot with no rendered content.
14. **The driver can run a chain (`scripts/dev/`, for `unattended-chain`).** A
    `chain --set … --cycles K` command launches K cycles back to back with no human action between
    them. Gates are decided by the set's registered policy, as today. It injects the chain's
    registered faults at registered points: a cancel at a named task of cycle *i*, an agent crash on
    cycle *j*, an agent hang on cycle *k*. **Between launches it asserts a quiet box by more than
    run state and leases:** no dispatched task without a reply, and no agent mid-task (the signal
    §3.2 item 10 makes readable). It records, per cycle, the terminal state, the terminal kind,
    whether any ghost generation followed a cancel (LangFuse or the agent logs, by cycle id), and
    whether the assessment was read. The 1.8.1 window runner is the model: state written after
    every cycle, and `--resume`.
15. **The per-task wait is declared, not inherited (the hang bound).**
    - **Today:** each dispatched task is bounded by `task_timeout_seconds()` =
      `dispatch.task_timeout or llm.timeout` (`src/squadops/config/schema.py:862`, #1147), and a
      timeout is a typed fact on the result (#995). The run's time budget (10,800 s for
      `validated-fullstack`) is checked between tasks and at correction dispatch
      (`adapters/cycles/dispatched_flow_executor.py:1752`, `:2771`). **So a hang is bounded, but
      by inheritance:** deploy B″ leaves `SQUADOPS__DISPATCH__TASK_TIMEOUT` empty, so the
      hung-agent detector is `SQUADOPS__LLM__TIMEOUT` (1,800 s). Raising the model-call timeout
      for a long emission silently raises the hang detector with it. That is the default at a seam
      the owner's ruling of 2026-09-14 forbids ("require, don't default").
    - **The change:** `dispatch.task_timeout` becomes required (schema non-blank, compose without a
      `:-` fallback, the factory and both composition roots), set explicitly on the deploy, and
      recorded in the deploy identity. The `unattended-chain` diagnostic proves the bound live: a
      hung agent's task fails at the declared timeout as a typed fact, and the run proceeds to
      correction or termination rather than hanging.
    - **Why here:** a campaign stuck on one silent cycle is the unattended failure in its purest
      form.
16. **Each line's records are attached to its Release, after a credential scan (decision 7,
    ruled).** A new `scripts/maintainer/attach_release_records.py <version>`:
    - tars `var/verification_sets/<line>*`, and the line's records under the archive path if any
      were preserved there
    - **scans the tarball's contents for credentials before anything leaves the box:** the
      `SQUADOPS__*` secret values in the running deploy's environment, `secret://` expansions, key
      prefixes (`pk-lf-`, `sk-lf-`, `sk-`), JWTs, and anything matching the repo's `.env` values.
      A hit refuses the upload and names the file and line.
    - uploads the tarball with `gh release upload vX.Y.Z` and writes its sha256 into the release
      package

    CLAUDE.md's cut procedure gains it as part of step 7, after the package. **Failure it
    prevents:** the only copy of a line's evidence living on one box (the 1.7.4 and 1.7.5 records
    survived only because the worktrees were checked). The repo is public, so the Release is too;
    the package pages already publish each cycle's id, verdict and checks, and the tarball adds the
    log-derived texture and deploy identities, never a secret.

### 3.3 SIP-0086 §12a: the compile loop

As drafted, with four changes on the self-evaluation seam:
- depth comes from the request profile
- every error, not the first
- the pass sees what it edits
- one evaluation per pass on the verifier's tree

It is amended as built, in the PR that builds it. **One addition from deploy A:** change 3 applies
to the qa task's re-take after a refunded repair. Diagnostic: `compile-loop` (§4.1).

### 3.4 SIP-0096 §17a: the contested result, with #1581

As drafted:
- a typed `disputed_checks` block
- `contested` on the row, never a fourth family
- the analyzer answers each dispute
- a confirmed dispute refunds through `blocked_unverified`

#1581 closes here. Diagnostic: `false-criterion` (§4.1). **A second prediction from deploy A:**
Next.js roll 2's wrong-locus round reads as a dispute naming the suite, not as a 35% patch that
breaks the build.

### 3.5 The flip: deploy B, only if N is met on A

SIP-0107 §38 step 7 exactly as the 1.8.1 plan §3.3 specified it: the authority path, the historical
replay, the §30.2 negative fixtures, the positive control, and one checkpoint pair predicting zero
refusals. It is applied on this line's deploy B **only if N is met on deploy A** (§4.1). If N is not
met, this section does not run, and step 7 is named for 1.9's plan as a 2.0 decision with the third
count stated. If the line runs long, this section is the second to drop (§3.9).

### 3.6 After the set: #1039 and the ops rider, bounded

#1039 (the docs site design pass): prose and assets, never a cut blocker. The **ops rider**
(#1177, #176 recipe 2, #1176, #1408 and #1412; this is its fourth plan) runs on the idle box after
the set, each given its recipe once. A terminal result closes it; a finding becomes a new issue and
does not expand the line (the 1.8.1 plan §3.8 bound, unchanged). **The cut waits for their runs,
not their findings.**

### 3.7 The cut criterion: three gates

| gate | criterion |
|---|---|
| **implementation** | §3.2 items 1–16 merged, with 1 and 12 read on the 1.8.1 corpus before items 6 and 12's predictions are finalized; §12a and §17a merged with their SIP sections amended as built; the flip merged **iff** A's N was met, with the authority path and both controls |
| **experimental** | L1 holds on every counted roll; `compile-loop`, `false-criterion` and `redelivery` read as predicted; **the `unattended-chain` diagnostic reads as predicted: K cycles, every run terminal within its bound, no ghost generation after the injected cancel, the crash contained, the hang ended at the declared timeout as a typed fact, a quiet box before every launch, an assessment on every cycle, and zero manual actions besides the registered gate policy**; the retest readout's fields on every patch; the replay's pre-registered predictions read; **N read on A as registered**, and if met, **the flip's checkpoint pair on B reads zero refusals** |
| **evidence** | every record three-state; the marker self-check passed at every launch; every record written under the main checkout's `var/` (item 8); the hygiene run at the cut with nothing stranded (item 9); the line's records attached to its Release after a clean credential scan (item 16); the SIP sweep stated before the sweep |

**The SIP sweep, stated now.**
- **SIP-0086:** §12a amended as built, stays `implemented`.
- **SIP-0096:** §17a amended as built, stays `implemented`.
- **SIP-0107:** `implemented` iff the flip landed on B and §39 holds on this line's records; else
  `accepted`, with the third count stated and step 7 named for 1.9's plan.
- **SIP-0108:** `implemented` at the 1.8.1 cut. No change.

### 3.8 Merge discipline

The 1.8.1 plan §3.11, verbatim, plus:
- **A PR title never carries an issue number after a closing keyword**, however negated.
- **A body edit and a merge never share a breath.**
- **A worktree is removed in the same step its PR merges** (item 9 makes the leftovers visible;
  this rule stops them forming).

### 3.9 Capacity: what drops first, and what cannot

The line carries 16 prelude items, two SIP amendments, 13 diagnostics, a counted set doing two
jobs, a conditional deploy B, an overnight replay and the rider. When it runs long, it sheds in this order, and each drop is recorded in the
cut record with the item's new home:

1. **#1039** (the docs site pass) → 1.9's idle-box time.
2. **The flip and deploy B** → 1.9's plan names step 7 as a 2.0 decision, with the count A read
   stated. N is still read on A, since it costs no rolls.
3. **The ops rider** → 1.9, with its count at 5. It is never allowed to sit between the set and the
   cut.
4. **#1665** (the capture reads the run's interface) → 1.9. The cut captures by hand with per-app
   seeds, as 1.8.1's did, and says so.
5. **The convergence replay** (item 12) → 1.9. The retest readout (item 1) still runs, because
   item 6 is scoped from it.
6. **§12a's diagnostic depth**: the `compile-loop` diagnostic stays, and any further §12a
   refinements beyond the four drafted changes wait.

**What cannot drop**, because these are the claim:
- the unattended seams: items 10 (#1648), 3 (#1626), 15 (the hang bound) and 11 (#1661)
- the chain driver (item 14) and the `unattended-chain` diagnostic
- the records' home, hygiene and Release attachment (items 8, 9 and 16), because a line that runs
  unattended must not strand its evidence
- the retest readout (item 1) and the qa-lane fix it scopes (item 6)
- §17a with #1581

If any of these cannot land, the line does not claim campaign readiness. It reports the part it
measured, and the claim moves to 1.9.

---

## 4. The verification sets

### 4.1 Deploy A: the tranche's diagnostics, and a counted set

The 1.8.1 nine, unchanged, plus four:

| diagnostic | fault | invariant | readout | N cell |
|---|---|---|---|---|
| `compile-loop` | two independent, non-cascading TypeScript type errors in one existing file on `nextjs_ts`, each with a unique marker and each reported by `tsc` | §12a: the task compiles until clean | both repaired before the task completes; the final compile clean; zero correction rounds; every pass in the usage ledger | none |
| `false-criterion` | a valid `@/lib` alias import against a **planted** verification row that rejects it | §17a: the producer disputes, the framework reads it | the producer leaves the correct implementation unchanged and emits a typed dispute; the row reads `contested`; the analyzer confirms; the round refunds through `blocked_unverified`. **Falsified by** a refunded round with no dispute, or a dispute never read | none |
| `redelivery` | the qa agent's process killed mid-repair on the roll's own path (the fault injected in the producing role's container, #1251) | #1627's rule and #1626's containment | a typed `FAILED` for the original task id; the queue drains; the handler is not re-run by the broker; **the run leaves `running`**; with item 3 built, a child parse crash returns `None` and the parent survives | none |
| `unattended-chain` | **K = 4 React cycles back to back** through the chain driver (§3.2 item 14), with three registered faults: **a cancel** of cycle 2 while its first implementation task is in flight; **an agent crash** (the process killed mid-task, #1251's shape) on cycle 3; **an agent hang** on cycle 4 (the handler sleeps past the declared task timeout, item 15) | **the line's claim**: a cycle is safe to leave running unattended | per cycle: a terminal state within its bound; **zero ghost generations** after the cancel (no LangFuse generation or agent emission carries cycle 2's id after its cancel is acknowledged); the crash recorded as a typed fact and the run leaving `running`; the hang ended at the declared timeout as a typed `task_timeout` fact and the run proceeding to correction or termination; a quiet box (no reply outstanding, no agent mid-task) before each launch; the assessment read on every cycle; **zero manual actions** except the registered gate policy, which the record names. **Falsified by** any ghost generation, any run left `running`, a hang past its bound, or a manual step | none |

**The counted set:** four React and two Next.js rolls, as in 1.8.1, doing two jobs. It is **the
regression bar** (L1 on every counted roll, functional yield reported) and, with the 1.8.1 supply
diagnostics, **the N supply**: N is re-fixed at 6 with one per required cell, the supply table
registered as predictions (§4.4), and the tally read at each diagnostic's clearance.

### 4.2 Deploy B: the flip alone, only if N is met on A

The 1.8.1 plan §4.2, verbatim: the pre-registration, one checkpoint pair predicting zero refusals,
and the shakeout loop to its exit rule with a budget of three rounds. It runs after the
campaign-readiness readings on A are recorded, so a finding here cannot reach back into them.

### 4.3 What this line does not measure

The Squad-versus-Solo question was 1.8.1's, and it read 0 / 0 / 6. Its successors (Free-Solo, the
placement axis) are 2.0 planning inputs. **No arm axis is exercised on this line.** Every config
carries `arm` empty, and Solo stays declared but unused (SIP-0108 §10o).

### 4.4 Registration rules this line adds, before its first launch

1. **A seam reached is not a cell supplied.** The supply table is a §3b-class prediction with a
   falsification condition, and the per-cell tally is printed at every diagnostic's clearance.
2. **The counting definition governs, and the supply column forecasts.**
3. **Every reading's source must be able to hold it** (new, from #1661). For each registered
   prediction, the pre-registration names where it is read and shows that the source can contain
   the fact: no reading registered on a capped or sampled store without saying so.
4. **No launch-and-cancel to read a pin** (new, from #1648). Config hashes are computed with the
   CLI's own code on the deploy's tree and confirmed by the first launch, as rev 3 of the 1.8.1
   window did.

---

## 5. Re-placements by name: nothing silently carried

28 open issues on 2026-09-24.
- **In this release (9):**
  - #1626 (containment, §3.2 item 3)
  - #1632 (item 4)
  - #1621 and #1639 (item 7)
  - #1648 (item 10)
  - #1661 (item 11)
  - #1665 (item 13)
  - #1581 (§3.4)
  - #1039 (§3.6)
- **The ops rider, on the idle box after the set (5):** #1177, #176, #1176, #1408, #1412.
  #1176 is read beside item 2.
- **Read at the cut, stays open by design (1):** #1469.
- **1.9, unchanged (7):** #1507, #567, #353, #1031, #1448, #1522, #414.
- **2.0, with Campaign (1):** #316.
- **At design review (4):** #949, #950, #194, #557.
- **Not scheduled (1):** #1122.

That is 9 + 5 + 1 + 7 + 1 + 4 + 1 = **28**, each placed once. (Rev 0 counted 24: the four since
are #1639, #1648, #1661 and #1665, all placed here.)

---

## 6. Sequencing

1. **This plan**, merged on the owner's review (rev 3, decisions 1 and 7 ruled).
2. **The prelude, no-deploy items first:**
   - items 8 and 9 (records and hygiene: before any set runs, so this line's records are born in
     one place)
   - item 14 (the chain driver), with its fault injection proven on a stub before any deploy
   - 1, 4, 5, 7, 13 and 16
   - then 12's harness, with 1 and 12 read on the 1.8.1 corpus
3. **The framework items:** 10, 11 and 15 (the unattended seams), then 3, then 2, then 6 once
   item 1 has read the corpus.
4. **§12a**, then **§17a**, each with its diagnostic registered before its PR merges.
5. **Deploy A. The 1.8.2 pre-registration** is committed before the first launch: the thirteen
   diagnostics, the supply table as predictions (§4.4), the counted set as regression bar and N supply, and
   the pins read from the deploy without launch-and-cancel, and the declared task timeout in the
   deploy identity. Then the diagnostics, then **the `unattended-chain` diagnostic**, then the
   counted set.
6. **N read** on A. **The campaign-readiness readings are recorded first.** Then the flip PR iff N is
   met, then deploy B and its pair.
7. **#1039, then the ops rider** on the idle box, bounded.
8. **The final record; cut 1.8.2 by the seven steps and the new housekeeping row.** Then the 1.9
   plan: #1507, the completion boundary Campaign lands through, with SIP-0107 step 7 named as a 2.0
   decision if the flip did not land.

---

## 7. Decisions: ruled (1, 7) and adopted at merge (2–6, 8)

1. **The line's shape. RULED 2026-09-24: both** (§2.3). Campaign readiness is the headline,
   measured first on A. N is registered on A's existing supply with no extra rolls. The flip goes
   on deploy B only if N is met, and it is the second thing to drop.
2. **The qa-lane fix is scoped from the retest readout**, not designed in this plan. Recommended.
   The window's passing qa × React edit is the control.
3. **The cap finding is fixed by the R1 retry shape** unless the adapter reading shows the budgets
   can be separated. Recommended. The reading precedes the PR.
4. **#1626 closes on the `redelivery` diagnostic**, not on the containment PR's tests. Recommended.
5. **The four registration rules of §4.4 are written into the pre-registration before its first
   launch.** Recommended.
6. **The crew reviews the pre-registration at every revision and the cut record before the tag**,
   one round with all blockers together, when the crew budget allows. **When it does not, the
   record says so at the revision**, as the 1.8.1 window's rev 3 did. Recommended. On 1.8.1, five
   deploy-A revisions merged unreviewed without saying so; the window's rev 3 merged unreviewed
   and said so.
7. **Each line's full verification records are attached to its GitHub Release. RULED 2026-09-24:
   attach**, after a credential scan (§3.2 item 16). The repo is public and so is the Release. The
   tarball adds the log-derived texture and deploy identities to what the package pages already
   publish, never a secret; the scan refuses the upload otherwise.
8. **The housekeeping row joins CLAUDE.md's release-cut procedure** (item 9): hygiene at every cut,
   and a worktree removed in the same step its PR merges. Recommended.

---

## 8. What this plan does not decide

- **The 1.8.2 pre-registration's text:** the pins, the field producers, the supply predictions and
  their falsification conditions. The rules are fixed in §4.4.
- **The qa-lane fix's design:** §3.2 item 6, scoped from item 1's reading.
- **The replay's predictions:** registered after item 1's corpus reading and before the replay
  runs.
- **Campaign's own design:** its SIP's design review is 2.0's. This line supplies the cycle-level
  properties it depends on, not its mechanics.
- **Who decides an unattended cycle's review gate.** Campaign's design places it (its `escalate`
  outcome maps to a gate decision). Until then, the chain and every set use the driver's registered
  gate policy, and the record names the decider. Whether an undecided gate waits without bound is
  not asserted here; Campaign's design answers it.

---

## 9. Revision history


- **Rev 0 (2026-09-22):** drafted at the 1.8.1 deploy-A N reading on the owner's ask. Recommended
  re-supplying N and landing the flip; §1's window rows and §5's recount left for rev 1.
- **Rev 1 (2026-09-24):** after the 1.8.1 cut. §1's pending rows written (the window read 0 / 0 /
  6; SIP-0108 implemented; Solo kept, no teardown), plus seven rows from the window, the cut and
  the post-cut cleanup. §3.2 gains items 8–13 (records' home, hygiene, #1648 agent-side, #1661,
  the convergence replay, #1665) and #1639 rides item 7. §4.4 gains two registration rules. §5
  recounted at 28. **Decision 1's recommendation changes** to the campaign-readiness shape, with
  rev 0's kept as the alternative. Decisions 7 and 8 are new. The ops rider is carried here by the
  1.8.1 cut's ruling.
- **Rev 2 (2026-09-24):** at the owner's ask, four additions so the campaign-readiness claim has a
  test.
  - The `unattended-chain` diagnostic (§4.1) and its chain driver (§3.2 item 14).
  - The hang bound, verified on B″ (per-task wait = `llm.timeout` = 1,800 s by inheritance) and
    made a declared value (§3.2 item 15).
  - The review gate's decider placed in Campaign's design, with the chain using the registered
    policy (§2.3, §8).
  - §3.9, the capacity section, with a drop order and what cannot drop.
- **Rev 3 (2026-09-24):** the owner's rulings. Decision 1: both, with campaign readiness first and
  the flip conditional on N and second to drop. Decision 7: attach records to the Release after a
  credential scan (new item 16). Decisions 2–6 and 8 adopted at merge. §2.3, §3.5, §3.7, §3.9,
  §4.1, §4.2, §6 and §7 rewritten to match.
