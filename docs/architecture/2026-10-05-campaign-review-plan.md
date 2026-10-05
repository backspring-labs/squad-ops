# Campaign review and objective plan — 2026-10-05

**Basis:** `main` at `2fb7745b` and the GitHub issue and pull-request state read on
2026-10-05. This is a design and sequencing note, not authorization to run a campaign or
an implementation plan for the Campaign engine.

## Rule

**The first 2.1 diagnostic campaign reuses the pinned 2.0 counted-set definition as its baseline;
codebase-review findings may select later hypotheses, but they do not alter this campaign's
objective, policy or accepted-app scope.**

This preserves a comparison. A new objective on a new 2.1 deploy would change the framework and
the workload at once, so a result could not be attributed to either.

## A. Roadmap state

### Shipped and closed behind this work

- 2.0.0 shipped Campaign Orchestration. SIP-0109 remains accepted because its placed 2.1 parts are
  still open.
- 2.0.1 is the current release and is a security patch, not a new Campaign slice.
- The 2.0 counted set passed: two campaigns reached success and held the registered safety
  guarantees. Its four findings — #1961, #1962, #1995 and #1884 — are already fixed on `main`.

### 2.1 in progress

2.1 is the active stabilization line. Its governing question is whether every path Campaign relies
on holds without a supervisor catching framework defects. The line is feature-free except for the
owner-approved, narrowly bounded #1940 authority grant to `campaign-supervisor`.

Completed on `main` at the stated basis include:

- the inherited 2.0-set findings;
- the SIP portfolio and delivery-ledger guards;
- the architecture overview and guard;
- the tracked supervisor instruments (#1956);
- replaying an increment outside its campaign (#1959);
- reference-cycle capture (#2008); and
- the single gate-decision recorder (#1986), which must precede supervisor control.

In progress, rather than complete:

- #1960's per-increment scorecard has an open green PR (#2027);
- #1934 and #2007's restart/re-attach work has an open green PR (#2033);
- #1930 has an open PR (#2034);
- several first-batch hardening and ground-clearing PRs are open; and
- #1940, the authority required for the crew to create, start, resume and abort a campaign, remains
  open with no implementation PR attached at the time of this reading.

Therefore 2.1 is not campaign-ready yet. Preparation can proceed, but the campaign must not start
until the deploy gate below is met.

### Where 2.2 begins

2.2 begins only after the 2.1 cut, including the cut-time re-read of Cross-Cycle Memory's Phase-1
hypothesis and its recorded SIP amendment. Its feature boundary is:

- Cross-Cycle Memory, the line's only planned change to squad behaviour; and
- #1708's auto-decision tier and escalation queue.

The inert recall port, NoOp implementation and call site are 2.1 ground preparation (#1964), not the
2.2 feature. Outcome Evaluation's feature half and the post-retest/revision/review-packet work are
2.4, not 2.2. Capability-Backed Agents is later still.

### Gaps and ambiguities to keep visible

1. The forward-cadence paragraph still presents 2.2 inside the 2.0 row; the horizon table and the
   adopted 2.1 plan are clearer and should be treated as the current placement.
2. Cross-Cycle Memory is proposed, not accepted. The 2.1 cut-time evidence re-read is an entry gate
   to its design review, not permission to implement memory.
3. The 2.1 plan says the first crew-controlled campaign may run on the first rebuild carrying #1940,
   while its outer-loop section also makes #1960 part of the comparison instrument set. #1960 is
   required for this comparison. Whether tonight is owner/admin-operated or waits for #1940 is an
   owner decision; an admin-operated run cannot claim it tested supervisor authority.
4. #1756's complete rendered-prompt record is crew-owned and still open. Its absence does not block
   a baseline campaign, but it blocks a strong diagnosis of prompt-information loss. Any such finding
   must be labelled incomplete until #1756 exists.

## B. Campaign input decision

### No new objective PR

Do not add a new campaign definition. Use the existing pinned
`examples/03_group_run/campaigns/2-0-0-set-1.yaml` at sha256
`74cb2f031c055fc250937c8282be66c0cb25a3d0fef6752762fdf91d129d27fe`.

The existing definition is already the exact workload contract the rule selects. Copying it would
add no information, and the provenance generator deliberately reconciles every semantic match rather
than assigning identical content to one campaign. The create reason, not a duplicate filename, names
this diagnostic run. This architecture PR is the complete pre-run GitHub record; no Parker
implementation PR is warranted for the objective itself. Runtime prerequisites remain separate PRs
and follow the deploy gate below.

### Objective contract

- **Class:** diagnostic baseline, not a counted campaign and not a release-acceptance run.
- **Statement:** exactly the 2.0 counted objective: evolve `group_run` toward its PRD's expansion
  scope, one increment at a time.
- **Allowed scope:** `backend/**` and `frontend/**` only.
- **Machine success:** three accepted increments.
- **Policy:** domain-equal to the 2.0 counted-set policy, including calibration, cycle and elapsed
  bounds, repair/retry limits, ruling and lease bounds, and the same profiles.
- **Baseline:** the pinned 2.0 counted set is the comparison; this run changes the deployed framework,
  not the workload contract.
- **Bounded claim:** the result may diagnose already-deployed 2.1 Campaign paths and the fitness of
  their instruments. It cannot confirm an unmerged 2.1 change, accept 2.1, or establish that the
  proposed 2.2 Cross-Cycle Memory feature is ready to implement.

### Pre-registered prediction

Owner acceptance of this plan, before creation of the stored campaign, registers this prediction:

> On the named deploy, the repeated 2.0 objective will reach three accepted cumulative increments
> without framework repair, lease takeover, campaign resume, abort, rebuild, runtime-configuration
> change or accepted-app edit; authorized increment and plan-gate rulings are expected supervision,
> not intervention. Each gate decision will have one durable record, the named pre-run recovery
> diagnostics will preserve campaign attachment, and the archive, replay, digest and per-increment
> scorecard will all be derivable from stored records.

The close-time review tests each clause separately. A failure is diagnostic evidence, not a failed
counted set. "Recovery" here means only the diagnostics named in the launch record; it is not a claim
that every crash window recovers. In particular, in the paths reviewed no recovery path picks up a
successor left `QUEUED` by a process death after insertion and before execution; `max_elapsed_s` is
evaluated only after a cycle ends, so it does not bound this state. No restart is planned during this
supervised run. After every completed run, the supervisor queries the next run at the first
300-second watcher interval. The supervisor makes the same check after every gate decision that lets
the cycle continue, because that ruling may be what creates the successor. If it remains `QUEUED`,
the supervisor issues a campaign pause with the stuck run in the reason and escalates the known
framework finding; silence must not be read as an empty or slow result. A reduced shakeout or a
second campaign would need its own property list and pre-registered prediction.

### Launch-input record

1. The create command reads the pinned existing definition without modifying it.
2. Its `--reason` names the diagnostic purpose, definition path and sha256, deployed commit and
   `dep_...` identity.
3. The launch record carries the accepted prediction and the completed B1–B4 fields below.
4. After the stored campaign exists, provenance is regenerated and merged with the close-time package
   identity. It may list other semantically identical definitions; the create reason disambiguates
   the run's selected input.

### Acceptance criteria

The launch input is acceptable only if a deterministic check can establish all of these:

1. The tracked file's sha256 equals the pinned value above, it loads successfully and its project is
   `group_run`.
2. Objective and policy remain domain-equal with the second 2.0 counted-set definition.
3. `allowed_scope` contains only `backend/**` and `frontend/**`, and the target is exactly three
   accepted increments.
4. The create reason records the diagnostic class, definition path and hash, deploy commit and
   deployment identity before creation.
5. No new definition is added and the pinned definition contains no mutable fact about this deploy or
   run.
6. Post-run provenance lists the stored campaign, the selected definition among all semantic matches,
   and the close-time evidence package; the create reason identifies which input the operator chose.

Campaign success is separate from launch-input acceptance. The run succeeds only if it opens with calibration,
accepts three cumulative increments, preserves all earlier frozen criteria, closes by the objective
row, emits its bounded evidence package and digest, and yields per-increment scorecards comparable
with the 2.0 baseline. Any intervention enumerated in the prediction voids the comparison claim;
authorized objective-bound gate rulings do not. A merge to GitHub does not change the subject, but a
rebuild, configuration change or mutation of the accepted app during the run does; all conclusions
are attributed to the recorded deploy SHA, never to whatever `main` points to in the morning.

### Target components

- **Input:** the pinned existing `2-0-0-set-1.yaml` definition.
- **Subject:** the deployed Campaign and cycle paths against the accepted `group_run` app.
- **Observers:** the tracked watcher, lease proof, binding replay and loaded checks (#1956).
- **Comparison:** increment replay (#1959) and per-increment scorecards (#1960).
- **Record:** the stored Campaign control log, close-time package and digest, then regenerated
  definition provenance.
- **Explicitly excluded:** `src/`, `adapters/`, profiles, prompts, permissions, continuation policy,
  Cross-Cycle Memory and any codebase-review fix.

### Evaluation seams

| Evaluator | Tree or record it sees | If the definition or evidence is absent |
|---|---|---|
| pre-run input check | the operator's pinned Git tree | launch is blocked if the tracked definition, expected hash or semantic contract is absent |
| `campaigns create --file` | the operator checkout plus the deployed API's schema | no campaign is created; a schema-invalid or drifted definition is refused |
| Campaign runtime | the stored objective, policy and control log | after creation, deleting the checkout file does not change execution, but destroys reproducible provenance |
| definition-provenance generator | tracked definitions plus stored campaigns and close-time package identities | the campaign is unmatched and the file is an example, not evidence |
| close-time evaluator | stored cycles, control log, frozen criteria and evidence records | a missing tracked definition does not change the verdict, but the result cannot support the reproducible-baseline claim |
| replay and scorecard readers | accepted tree, approved request, frozen criteria and close-time package | missing inputs produce no comparison; they must not be inferred from prose or raw logs |

### Launch gates resolving B1–B4

These are launch gates, not facts established by this architecture PR:

| Gate | Required recorded answer | Current disposition |
|---|---|---|
| **B1 — change and rebuild boundary** | No objective implementation PR exists. For every separate runtime PR, record its full-green merge, rebuild owner, scheduled window, 150 GB disk-floor check, loaded-code check and post-deploy reference run. | The architecture PR needs no rebuild. The runtime batch's owner, window and idleness reading remain open; Parker measured 483 GB available, above the floor. |
| **B2 — execution identity** | Record the deployed commit and its `dep_...` identity before creation. From certification through evidence closure, do not rebuild or mutate runtime configuration. Later GitHub merges are allowed only if morning analysis remains explicitly pinned to the deployed SHA rather than `main`. | Deploy SHA and deployment record can exist only after the prerequisite batch lands; until then launch is blocked. |
| **B3 — supervision and reachability** | Name the holder who can create/start, the person who rules increment and plan gates, the owner who may authorize and resume an escalation, and each reachability window. Prove the operator can reach the Spark API and holds the required current role; do not infer either from crew membership. | Owner decision requested. The current rule is `campaigns:control` on the admin role; actual holders and API reachability are unknown. |
| **B4 — claim and prediction** | Record the campaign as diagnostic, bind it to the pinned input and prediction above before creation, and list which predicted 2.1 properties are actually present on the deploy. A counted run would require a separate owner-approved registration. | The design supplies the class and proposed prediction; owner acceptance and deploy binding remain open. |

Operational readiness is an additional launch gate: the box is idle and above the disk floor; the
log archiver starts with the campaign; no Buzz rebuild competes for the box; and rollback language
names either final campaign abort or an older-code rebuild. An older-code rebuild occurs only between
campaigns, or while the campaign is paused or escalated with nothing in flight.

## C. Recommended sequence for tonight

1. **Freeze the baseline now.** Accept or reject this rule and PR outline before Parker prepares an
   edit. Do not invent a new product objective from tonight's code review.
2. **Parallel read-only review:** Ash explores code and operational friction; Dallas independently
   attacks this objective's attribution, measurability and scope. Neither review changes the baseline.
   Findings are classified as: prerequisite to safe execution, 2.1 hardening candidate, later feature,
   or observation needing evidence.
3. **Dallas returns before implementation prep is accepted.** A blocking objection is one that shows
   the repeat is not comparable, cannot be supervised safely, or cannot produce attributable evidence.
   Preference for a different feature objective is non-blocking for this baseline run.
4. **Do not prepare an objective implementation PR.** Parker verifies the pinned file and records its
   hash in readiness evidence while the separate prerequisite implementation PRs finish.
5. **Land and verify prerequisites in the adopted 2.1 order:** #1960, #1934/#2007 and the first
   batch's overlapping recovery checks. #1940 is required if this is the first crew-controlled
   baseline. If the owner instead chooses a current-admin-operated diagnostic, record that exception
   to the intended operator mode and do not claim the run tests #1940. Read main's full CI after each
   merge; rebuild once the deploy-moving batch is complete.
6. **Certify and freeze that one deploy:** record the commit and `dep_...` identity; verify main's
   full run is green; loaded checks match the commit; the regression pair is green; recovery
   diagnostics including `restart-at:at_proposal` are green; supervisor instruments pass; the
   selected current-admin or #1940 authority path works and remains bounded; the scorecard renders
   from records alone; the box is idle and above the disk floor; and the pinned definition still has
   the registered hash. Name the rebuild operator and window. No rebuild or runtime mutation follows
   certification until evidence closure.
7. **Resolve the owner-operated launch gate:** record the B3 names, reachability windows, API-access
   proof and the owner's acceptance of the diagnostic prediction. Start the log archiver with the
   campaign. If any field is absent, do not start tonight.
8. **Run one diagnostic campaign, not a set.** GitHub work may continue, but results remain pinned to
   the certified deploy and no merge may trigger a rebuild during the run. Dallas may observe
   adversarially; Ash may classify findings; Parker does not repair a live run. The supervisor rules
   proposals only against the accepted objective and records every ruling.
9. **Close before changing anything:** materialize the package and digest, regenerate provenance,
   compute scorecards and replay comparisons, then classify findings. Framework fixes become separate
   2.1 PRs with predictions written before the edit. The comparison report names #1611's changed
   profile resolution as a framework difference from 2.0. Any proposed new rule returns to
   architecture before Parker implements it.

The sequence deliberately separates three claims: the launch input is pinned, the deploy is
safe enough to run, and the campaign result is comparable. Passing one does not imply either of the
others.
