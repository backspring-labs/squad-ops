# Campaign runbook: running, supervising and recovering a campaign

The runbook the 2.0 plan asks for (§6 steps 12 and 15, #1711). It covers running a SIP-0109 campaign
on the Spark, ruling at its gates, recovering when it stops, and the outer loop around it: evidence,
then triage (§6), then a fix, a redeploy and the next campaign (§9), within the approval boundary (§10).

It is written from what ran:
- the ten shakeout campaigns of 2026-10-02/04, whose first four surfaced thirteen seam defects, each
  fixed between cycles;
- the 2.0 counted set, two campaigns supervised by these procedures with every safety guarantee held
  (`docs/plans/2-0-0-preregistration.md` §10).

Every procedure below is one that ran.
`docs/ops/NIGHT_TRIAGE_RUNBOOK.md` is the standard for diagnosing a failed cycle; this runbook points
at it rather than repeating it.

---

## 1. Before a campaign

| check | how | why |
|---|---|---|
| the deploy carries main | `./scripts/dev/ops/rebuild_and_deploy.sh runtime-api agents`, then read `rebuild_deploy.log` in the repo root for the `deploy record dep_…` line | the images bake the source tree; `docker compose up` alone restarts old code |
| the new code is loaded | in each container, `docker exec -i squadops-<service> python -` running a fact only the new code produces; compare `docker inspect squadops-<service> --format '{{.Image}}'` with `docker images squad-ops-<service>:latest` | a rebuild can exit 0 with a stale container |
| main is green | read every job of main's run for the deployed commit | an unexplained red is a stop |
| the box is idle | no run `running`, `queued` or `paused` in `cycle_runs` | a rebuild restarts agents mid-run |
| disk | `df -h /` stays above the 150 GB floor | each full rebuild costs 5–8 GB |
| the CLI is authenticated | `squadops login` | every command below goes through the runtime API |

**The policy file** holds `project_id`, `objective` (statement,
`allowed_scope`, measurement, and `target_accepted_increments`, the accepted increments that end the
campaign in success, §24ah) and every `policy` limit. Each limit is required, never defaulted
(SIP-0109 §9.5). `max_cycles` counts every cycle the campaign launches: the calibration, each
increment, each repair and each retry. The campaigns SquadOps runs to verify itself are tracked with
their project: `examples/03_group_run/campaigns/` (its README states the rule, #1941). Its
`shakeout-7.yaml` is a working example. A campaign's outputs (log windows, records) go under the main
checkout's `var/campaigns/<campaign>/`, which is not tracked.

```bash
squadops campaigns create --file examples/<project>/campaigns/<name>.yaml --reason "<why>"
squadops campaigns start <campaign_id> --reason "<why>"      # the calibration cycle launches
python scripts/dev/campaign_log_archive.py <campaign_id> --follow   # beside it, until it closes
```

**Start the log archive with the campaign** (#1710). The containers' logs are the triage
evidence, and the next rebuild destroys them. The archive keeps each cycle's window under
`var/campaigns/<campaign_id>/logs/<cycle_id>/`, with a manifest naming its window, each file's
sha256, and any window already lost to a rebuild. A run's revision forms do not depend on it: they
are kept on the run's summary and carried in the evidence package.

---

## 2. Watching

A campaign needs a human only in these states. Everything else is the campaign working.

| state, or what to look for | what it means | what to do |
|---|---|---|
| `awaiting_ruling` | the increment gate is open: a proposal waits (§9.2) | rule it (§3) |
| an open plan gate (`progress_plan_review` with no decision) | the framing asked a design question the manifest left `unresolved` | answer it (§4). Past its ruling bound it is recorded as `ruling_overdue`, and the digest asks for it; it is never answered for you |
| `escalated` | the decision named an action it could not launch, or a row that needs the owner | read why, fix if it is the framework, resume with an action (§5) |
| `paused` | a limit held the next action (§9.5), or the supervisor paused it | the owner's resume executes the held action |
| `launch_blocked` | the box refused a launch (§9.3): the supervisor holds it, or a model the deploy did not load is resident | it retries every `launch_blocked_interval_s`, then escalates; after the escalation, `resume` with no `--action` retries it once the box is free |
| `completed` | the campaign ended by its own rules | read the digest (§8) |

```bash
squadops campaigns show <campaign_id>                 # state
squadops campaigns log <campaign_id>                  # every row, refusals included: the authority
squadops cycles list <project> --limit 10             # the newest cycles (a full page says so)
squadops runs list <project> <cycle_id>
```

**The control log is the record.** Each decision row's `binding` names the §10 row, the action, the
cycle's verdict, and, for an escalation, `unbuilt`: the reason it could not launch. Read that before
anything else.

**A watcher that polls these states must not go blind.** An expired CLI token reads as an empty
response, not an error. Have the watcher print every reading, and stop with UNREADABLE after three
failed reads in a row.

---

## 3. Ruling at the increment gate

The proposal is a typed change request, stored on the proposal run as `change_request.yaml`.

**A supervisor that runs inference on the Spark takes the box first** (§9.3, §24ai). While it holds
the lease, no cycle launches and no run starts; a launch is refused (a 409 from the CLI, a
`launch_blocked` row in a campaign), and a run waits queued. Give it back, with the models unloaded,
before ruling:

```bash
squadops campaigns lease acquire <campaign_id> --expires-in 1800 --reason "reviewing prop_… v1"
squadops campaigns lease show <campaign_id>
squadops campaigns lease release <campaign_id> --reason "ruled; models unloaded"
```

The lease is taken only at an open increment gate, only with no run in flight, and only from the
squad. It expires on its own, so a supervisor that crashes cannot hold the box.

**A run starts only when a launch could** (§24an, #1928). If the lease comes back, released or expired,
with a model the deploy does not declare still resident, the next run keeps waiting, queued, until the
model is unloaded. Usually that is the framing run your ruling approved. Past one full lease
(`lease_expiry_s`) it fails unstarted, with the reason. The runtime-api log names the wait
(`run_start_waiting_for_box … refusal=box_not_quiet`) and its end (`run_start_box_free`).

```bash
squadops artifacts list --project <project> --cycle <cycle_id> --run <proposal_run_id>
squadops artifacts download <artifact_id> --out change_request.yaml
```

**Read it against four questions:**
1. **Scope:** one change, inside the objective's `allowed_scope`.
2. **Criteria:** each `statement` and `observable` names something the accepted app does not do yet,
   so it fails on the baseline (§8.2). A criterion the baseline already passes cannot discriminate.
3. **Footprint:** only the files the change needs. `backend/tests/**` and the frontend test globs
   are normal.
4. **`must_not_break`:** the earlier criteria this change could touch. Every criterion a promotion
   froze runs anyway (§8.1).
5. **Internal consistency:** the PRD delta states only what the manifest delta, the criteria and the
   footprint carry. The 2.0 set's campaign 2 returned a v1 whose PRD text added a display that nothing
   else in the request delivered (#1995).

**Check the accepted code, not only the accepted manifest.** A manifest says what was declared. The
delivered tree says what the app does, and the criteria are judged on that tree (§8.2). Each of these
cost a revision in the 2.0 set or its shakeouts:
- **a capability the accepted manifest already declares is usually already built.** Campaign 1's
  calibration had built capacity, so a capacity-enforcement criterion could not fail on it (returned,
  `criteria_not_checkable`);
- **the stack's frozen models already do some things.** On FastAPI, a required request string is
  trimmed and refused blank (#593), and an unset optional field comes back `null` (§24ar, #1948). A
  criterion asserting either holds already (#1962);
- **a new endpoint's path may already answer.** `POST /runs/seed` against a tree with
  `GET /runs/{run_id}` is a 405 today, which is the failure that makes it discriminate.

Read the tree in the runtime container, as root, by the rule every delivered-tree reader uses
(`squadops.cycles.delivered_tree.delivered_files`). An increment's composed tree is the PROMOTE row's
`tree_ref` (`accepted_tree.json`), which holds the whole app.

**Every return or rejection carries its classification** (§9.4, §24bi): `--classification <class>` on
the ruling, one of `scope_too_large`, `criteria_not_checkable`, `conflicts_with_an_earlier_increment`,
`ambiguous_manifest_delta` or `sound_proposal_built_badly`. When none fits, say so:
`--classification unclassified --classification-rationale "why none fits"`, rather than forcing a novel
defect into the nearest class. A return with neither is refused before anything is recorded. A later
reading of a version is still recorded with `squadops campaigns classify <campaign_id> --proposal <id>
--version <n> --as <class> --reason "…"`. The ledger is what the next pre-registration reads, and
Cross-Cycle Memory observes each return by its class (SIP-0110 §0.4).

```bash
squadops runs gate <project> <cycle_id> <proposal_run_id> progress_increment_ruling \
    --approve --change-request change_request.yaml \
    --idempotency-key <campaign>-rule-<proposal_id>-v<version> --notes "<the reason>"
```

- **The ruling binds** to the proposal id, version, content hash and accepted tree. A stale binding
  is refused and recorded.
- **Resending the same key replays the ruling.** A different key with a different payload is a
  conflict.
- **Request revision** (`--return-for-revision --classification <class>`) sends a note back to the
  strategy role, which writes the next version.
- **Reject** (`--reject --classification <class>`) ends the cycle `rejected_at_gate`; it counts toward
  `max_rejected_proposals_in_row`.
- **Never edit the proposal.** The supervisor is not an author (§9.2).
- **The ruling bound** (`ruling_bound_s`) is the supervisor's, whoever holds the seat, the
  owner or the crew (§24al). Once it passes, a `ruling_overdue` row is recorded and the digest
  names it. Nothing rules for you (§24ae).

---

## 4. Answering a plan gate

The framing stops at `progress_plan_review` only when the manifest declares an `unresolved: true`
decision: a question the PRD does not determine. Answer it in the notes. An agent answering under a
gate policy declares itself with `--as-agent`.

```bash
squadops runs gate <project> <cycle_id> <framing_run_id> progress_plan_review --approve \
    --notes "<the answer>"
```

An answer is asked once. The next proposal carries it into the accepted manifest as the decision's
`choice`, with a `warrant` naming the gate that answered it (§24ad, §24ag). An approval with blank
notes answers nothing, and the question is asked again.

---

## 5. Recovering

### An escalation
1. Read the decision row: `squadops campaigns log <id>`, the last `decide` row, its `binding.row` and
   `binding.unbuilt`.
2. **If it is a framework defect** (shakeout 4 seq 14: "the accepted cycle stored no interface
   manifest", #1902):
   1. file it;
   2. fix it on a branch, with a wiring test entered at the caller the live cycle uses;
   3. merge, and read main's run;
   4. rebuild and verify loaded (§1). The campaign is idle while escalated, so a rebuild is safe.
3. **Resume with the action the row could not take:**

```bash
squadops campaigns resume <campaign_id> --action propose --expected-state escalated \
    --idempotency-key <campaign>-resume-<action>-v1 --reason "<what was fixed, the deploy>"
```

The actions are `propose`, `abandon_and_propose`, `repair` and `retry`. A paused campaign resumes on
its held action: no `--action`, and a named one must match.

### A failed or rejected cycle
The decision is automatic (§10).
- **Rejected with repairs left:** a repair, row 12. It runs the build alone, from the failed cycle's
  candidate, with a **prior-cycle brief** of what failed and why (#1692).
- **Rejected for an environment cause with retries left:** a retry, row 10.
- **Otherwise:** the increment is abandoned and the next one proposed, row 13.

Do not intervene in a cycle. Diagnose it (`NIGHT_TRIAGE_RUNBOOK.md`) and let the decision run. A
manual repair or restart is an intervention, and it voids the campaign's claim of unattended
operation.

### A runtime-API restart, or a box halt
- **On startup the runtime API re-enters on its own** (§12a, §12b):
  - it launches any pending launch intent;
  - it starts a launched cycle's first run;
  - it re-hears every cycle that ended with no decision recorded.
- **Do not restart while a cycle is mid-sequence.**
- **Capture container logs before a rebuild.** A rebuild wipes them:
  `docker logs squadops-<service> > ~/squadops-deploy-logs/<campaign>/<service>.log` for each service.

### A stuck gate, or a wedged campaign
- **The brake:** `squadops campaigns pause <id> --reason …`.
- **The end:** `squadops campaigns abort <id> --reason …` is terminal, and it cancels the running
  cycle. Abort only when the campaign cannot continue by its own rules. Shakeout 3 was aborted on
  #1887: a partial accepted tree that no later cycle could converge on.

---

## 6. Triage during a campaign: the outer loop's first half

Reading is always allowed. The frontier models that triage do not load the Spark.

| question | where |
|---|---|
| how a cycle ended and why | `squadops cycles assess <project> <cycle>`: verdict, failed checks, attribution, correction movements, refunded rounds |
| what each brownfield mechanism did on an increment | `python scripts/dev/reference_report.py --cycle <cycle_id>`: delta framing, scoped repair, accumulated acceptance, discrimination, route rendering |
| what an agent did | `docker logs squadops-<role>`: emission shape and parse, typed checks, self-evaluation forms, the suite line |
| the artifacts at each step | `squadops artifacts list --project … --cycle … --run …` |

**A finding is a defect, with a file, a line and the evidence** (`NIGHT_TRIAGE_RUNBOOK.md`'s
standard). File it. Two examples from shakeout 4:
- **#1897:** `test_files=0` straight after a self-evaluation pass that took the edit form.
- **#1898:** a blocking check flagging a status assertion the suite never made.

**Fixes land between cycles, never inside one.** A safe window is a campaign that is `escalated`,
`paused`, or between a cycle's end and the next launch, with no run in flight. During a counted set
nothing merges at all; a fix voids the set (2.0 plan §4).

---

## 7. Two speeds of verification

- **The fast lane, between campaigns:**
  - the unit regression (`./scripts/dev/run_regression_tests.sh`, under `set -o pipefail`; read the
    count line, never a piped exit code);
  - main's CI run;
  - the calibration cycle the next campaign opens with.

  The next campaign is the soak.
- **Full pre-registered sets, for a release cut or a headline claim:**
  - predictions before the first launch;
  - readings per cycle;
  - drift declared.

  The pre-registration is the owner's to approve.

---

## 8. After a campaign

```bash
squadops campaigns digest <campaign_id>     # what was accepted, how each cycle ended, what waits
squadops campaigns ledger <campaign_id>     # each proposal version, its ruling and its outcome
```

**The evidence package** is materialized at close from records alone. Its identity is the hash of its
canonical form, so materializing it again is idempotent. **Check it is complete:** one record per
launch intent, none `unreadable`, and as many control-log rows as the database holds for the campaign.

**The safety reads** (the 2.0 pre-registration §3; each ran at both counted campaigns' close):
- one cycle per launch intent;
- every `rule` row binds the `content_hash` of the version its `submit` row put at the gate;
- every entry into `building` is an approving `rule`;
- every PROMOTE row carries `tree_ref`, and a `bundle_ref` on each frozen criterion;
- no `refused` row, no `ruling_overdue`, no lease or `launch_blocked` row you did not expect;
- the audit sink (`data/audit/runtime-api.jsonl`) holds the same campaign events as the control log,
  and no `cycle.launch_refused`; the runtime log holds no `run_start_waiting_for_box`.

**Record the campaign's run in your log:**
- its cycles and decisions;
- every defect it surfaced, with its fix PR;
- the deploy each stretch ran on;
- what it showed about each mechanism.

That record is what the next campaign's pre-registration reads.

---

## 9. The outer loop's second half: fix, redeploy, the next campaign

The first half is triage (§6): a finding with a file, a line and the evidence, filed. The second half
turns findings into a framework change and measures it.

1. **Batch the fixes.** Each finding's fix is its own branch and PR, with a wiring test entered at the
   caller the live cycle uses, and the evidence table CLAUDE.md asks for when it binds a typed check.
   Merge on full green and read every job of main's run after each merge.
2. **Rebuild once per batch, never mid-cycle.** `rebuild_and_deploy.sh`, then verify the new code is
   loaded in each container (§1). A rebuild between two campaigns is free. A rebuild inside one is
   safe only while it is `escalated` or `paused` with no run in flight (§6).
3. **Run the reference scenario on the new deploy**, before and after a counted set if one is coming:
   ```bash
   python scripts/dev/launch_reference_increment.py --notes "<why>"             # the build half
   python scripts/dev/launch_reference_increment.py --proposal --notes "<why>"  # the proposal half
   squadops cycles rate <project> <cycle_id> --rating-file <rating.yaml>      # rate what it proposed
   python scripts/dev/reference_report.py --cycle <cycle_id>                   # what each mechanism did
   ```
   It is one fixed increment on a pinned baseline, outside any campaign (SIP-0109 §11a). The same
   outcome on two deploys says the mechanisms held, and a different one is a finding. The 2.0 set
   ran it before and after its two campaigns with the same result both times.
4. **The next campaign starts from the same pinned definition.** Its **calibration cycle is the
   baseline**: it builds the app the increments then evolve, on the new deploy. Compare it with the last
   campaign's calibration, by verdict, framing attempts, correction movements and wall clock, before
   reading any increment. A calibration that reads differently is the framework change showing, and
   nothing the increments do is comparable until it is understood.
5. **Compare like with like.** The same objective, policy and squad profile, and the definition's
   sha256 in the create `--reason` (#1954 will record it on the create row). Per-increment replay on
   the new deploy (#1959) and the per-increment scorecard (#1960) are 2.1's. Until they land, compare
   the digests, the ledgers and `reference_report.py`'s readings.
6. **Record the loop:** the findings, their fixes, the deploy each stretch ran on, and what the next
   campaign showed about each fix. Write each prediction before the campaign that tests it.

---

## 10. The approval boundary

What the supervisor (the crew, or whoever holds the seat, §24al) does alone, and what stops for the owner.

| alone | stops for the owner |
|---|---|
| rule increment gates and answer plan gates; pause a campaign; classify a proposal; take the lease at an open gate with no run in flight (all `campaigns:supervise`, which the `campaign-supervisor` role holds) | a pre-registration, or any material change to one (a policy value, a prediction, the set's size or frame) |
| create, start and abort campaigns, materialize a package, and resume its own pause (`campaigns:manage`, which the `campaign-supervisor` role holds since 2.1, #1940, SIP-0109 §24az) | resuming an escalation, a limit's pause or the owner's own pause: the owner's word (§10's rows, `campaigns resume --action`; `campaigns:control`, the admin role alone) |
| file findings; fix them on branches; merge on full green, reading main's run | an unexplained red on main |
| rebuild between campaigns, verifying the new code is loaded | a fix needed while a counted set is open: it voids the set |
| run the reference scenario and the recovery diagnostics outside a counted set | anything touching security, and any public Release (tag, Release notes, records upload) |
| triage from records, which never loads the box | |

**During a counted set nothing merges and nothing rebuilds** (2.0 pre-registration §7). Findings
are filed and placed, and every fix waits for the set's close.
