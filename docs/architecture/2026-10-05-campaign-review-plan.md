# Campaign review and objective plan — 2026-10-05

**Basis:** `main` at `2fb7745b` and the GitHub issue and pull-request state read on
2026-10-05. This is a design and sequencing note, not authorization to run a campaign or
an implementation plan for the Campaign engine.

## Rule

**The first Nostromo-run 2.1 campaign repeats the 2.0 counted set's objective and policy as a
baseline; codebase-review findings may select later hypotheses, but they do not alter this first
campaign's objective, policy, or accepted-app scope.**

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
3. The 2.1 plan says the first crew campaign may run on the first rebuild carrying #1940, while its
   outer-loop section also makes #1960 part of the comparison instrument set. For tonight, require
   both: authority without comparable readings proves operation, not optimization.
4. #1756's complete rendered-prompt record is crew-owned and still open. Its absence does not block
   a baseline campaign, but it blocks a strong diagnosis of prompt-information loss. Any such finding
   must be labelled incomplete until #1756 exists.

## B. Proposed campaign-objective PR

### PR purpose

Register one reproducible input for Nostromo's first 2.1 baseline campaign. The PR does not change
Campaign mechanics, permissions, prompts, profiles or continuation policy.

Suggested title:

> `examples(campaigns): register Nostromo's first 2.1 baseline campaign`

### Objective contract

- **Statement:** exactly the 2.0 counted objective: evolve `group_run` toward its PRD's expansion
  scope, one increment at a time.
- **Allowed scope:** `backend/**` and `frontend/**` only.
- **Machine success:** three accepted increments.
- **Policy:** domain-equal to the 2.0 counted-set policy, including calibration, cycle and elapsed
  bounds, repair/retry limits, ruling and lease bounds, and the same profiles.
- **Baseline:** the pinned 2.0 counted set is the comparison; this run changes the deployed framework,
  not the workload contract.

### PR structure

1. One campaign definition beside the `group_run` project definitions. Its comments identify its
   purpose and sources, never a mutable deploy or round.
2. A short objective note naming the baseline definitions, semantic-equality requirement and the
   pre-run gates below.
3. Deterministic validation that the new definition parses to the same objective and policy domain
   objects as the two 2.0 counted definitions. Byte equality is not required; semantic drift is
   forbidden.
4. No provenance claim in the pre-run PR. After the stored campaign exists, provenance is regenerated
   and merged with the close-time package identity as the run's record.

### Acceptance criteria

The PR is acceptable only if a test or deterministic check can establish all of these:

1. The definition loads successfully and its project is `group_run`.
2. Objective and policy reconcile domain-equal with both 2.0 counted-set definitions.
3. `allowed_scope` contains only `backend/**` and `frontend/**`, and the target is exactly three
   accepted increments.
4. The PR changes no Campaign engine, prompt, request-profile, permission or continuation-policy
   file.
5. The definition contains no deploy, rebuild, campaign id or other future mutable fact.
6. The post-run record can bind the definition hash to one stored campaign and its close-time evidence
   package; until then it is labelled an input, not evidence.

Campaign success is separate from PR acceptance. The run succeeds only if it opens with calibration,
accepts three cumulative increments, preserves all earlier frozen criteria, closes by the objective
row, emits its bounded evidence package and digest, and yields per-increment scorecards comparable
with the 2.0 baseline. Manual intervention or a merge during the run voids the comparison claim.

### Target components

- **Input:** `examples/03_group_run/campaigns/` — the new definition and its local documentation.
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
| PR checks | the proposed Git tree | the objective PR fails because its required definition or semantic-equality check is absent |
| `campaigns create --file` | the operator checkout plus the deployed API's schema | no campaign is created; a schema-invalid or drifted definition is refused |
| Campaign runtime | the stored objective, policy and control log | after creation, deleting the checkout file does not change execution, but destroys reproducible provenance |
| definition-provenance generator | tracked definitions plus stored campaigns and close-time package identities | the campaign is unmatched and the file is an example, not evidence |
| close-time evaluator | stored cycles, control log, frozen criteria and evidence records | a missing tracked definition does not change the verdict, but the result cannot support the reproducible-baseline claim |
| replay and scorecard readers | accepted tree, approved request, frozen criteria and close-time package | missing inputs produce no comparison; they must not be inferred from prose or raw logs |

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
4. **Parker prepares the objective PR only after the design review.** It contains the input contract
   and deterministic checks above, no engine changes. Parker may prepare it while the prerequisite
   implementation PRs finish, but it does not authorize a launch.
5. **Land and verify prerequisites in the adopted 2.1 order:** #1960, #1934/#2007 and the first
   batch's overlapping recovery checks, then #1940 on the single decision recorder. Read main's full
   CI after each merge; rebuild once the deploy-moving batch is complete.
6. **Pre-run gate on that one deploy:** main green; loaded checks match the commit; regression pair
   green; recovery diagnostics including `restart-at:at_proposal` green; supervisor instruments pass;
   #1940 authority works and remains bounded; the scorecard renders from records alone; the box is
   idle and the definition is semantically equal to the 2.0 baseline.
7. **Run one campaign, not a set.** No merges during it. Dallas may observe adversarially; Ash may
   classify findings; Parker does not repair a live run. The supervisor rules proposals only against
   the accepted objective and records every ruling.
8. **Close before changing anything:** materialize the package and digest, regenerate provenance,
   compute scorecards and replay comparisons, then classify findings. Framework fixes become separate
   2.1 PRs with predictions written before the edit. Any proposed new rule returns to architecture
   before Parker implements it.

The sequence deliberately separates three claims: the objective PR is reproducible, the deploy is
safe enough to run, and the campaign result is comparable. Passing one does not imply either of the
others.
