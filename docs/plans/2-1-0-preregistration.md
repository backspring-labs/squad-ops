# 2.1.0 — pre-registration of the cut's set (plan §4 step 8, §6)

**Status: DRAFT, 2026-10-06. Not registered.** The plan leaves the cut criteria's numbers (the
regression set's size, the shakeout's exit rule) to this document, written when the line's last batch
is built (plan §6), as 1.9 and 2.0 did. The last batch is built and held (§9). **Pre-approved by the
owner on 2026-10-06** (§9): the supervisor registers it as drafted once the four conditions below hold,
as 2.0's set was registered.

**What must be true before it can be registered:**
1. **The final deploy is built** from main with the whole last batch, and every tracked loaded check
   answers with the new code (the final configs track them, and preflight refuses a deploy that does
   not).
2. **The shakeout loop's exit rule holds** (§3): one shakeout campaign on that deploy with no new seam
   finding.
3. **The recovery diagnostics have run on that deploy** (§2): the restart set rebuild 1 ran, and #1824's
   infrastructure retry. Uncounted, run before registration.
4. **The pins are read** (§6), and nothing in the set has launched.

---

## 1. What the set measures

2.1 is a hardening line after 2.0's campaign headline. The set does not re-prove 2.0's claim. It
measures that the final deploy still does what 2.0 proved, and reads what this line changed where a
roll or a campaign exercises it.

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress, on either stack | each regression roll's verdict, criteria, correction rounds and boot audit, against the baselines in §2 | a clean campaign |
| the delivered app boots and every declared route renders (#1796, #2084) | the boot audit (`audit_delivered_app.py`), which now renders each declared route | the cycle's own verdict |
| the campaign still evolves the app unattended between rulings | the shakeout campaign's control log and evidence package, as 2.0's §1 reads them | the regression rolls, which run no campaign |
| what each run left behind is recorded (#2028, #2086, #1937, #1911) | the run summaries: each failed round's `failed_detail`, each qa task's `lint_findings`, each empty repair's `offered_scoped` | the agents' logs, which the next rebuild destroys |
| the recovery paths the line rebuilt work live (#1934, #2007, #2042, #1824) | the diagnostics' records under `var/campaigns/<cmp>/diagnostics/` | a set in which nothing failed |

---

## 2. The set

- **Regression rolls:** **two per stack** (recommended), `fullstack_fastapi_react` and `nextjs_ts`, on
  `validated-fullstack` with `full-38`, launched by the verification-set driver from configs carried from
  rebuild 4's, with the final deploy's tracked loaded checks.
  - **Baselines** (the line's own pairs, same profiles, every roll accepted):

    | rebuild | React: criteria, rounds, boot audit, wall clock | Next.js: criteria, rounds, boot audit, wall clock |
    |---|---|---|
    | 1 | 21/21, 0, PASS, 50 min | 16/16, 0, PASS, 57 min |
    | 2 | 21/21, 0, PASS, 50 min | 18/18, 1, FAIL on #2084 (PASS on its replay), 67 min |
    | 3 | 21/21, 1, PASS, 54 min | 16/16, 0, PASS, 48 min |
    | 4 | 21/21, 0, PASS, 47 min | 18/18, 0, PASS, 66 min |

    The boot audit renders routes from rebuild 2 on (#1796): rebuild 1's passes did not read them, and
    from rebuild 3 on every pass renders all three declared routes.
- **The shakeout campaign:** one campaign of **two increments** (`target_accepted_increments: 2`), on the
  React stack, opening with its calibration cycle, supervised by the owner's delegate under 2.0's §3a
  policy unchanged. It is the exit rule's shakeout (§3), and it is the set's campaign reading: it is
  uncounted, and a new seam finding in it is fixed and re-run before registration, never counted.
- **Diagnostics, before registration:** `restart-at:at_proposal`, `restart-queued-successor` and
  `duplicate-completion` on a one-increment campaign (as rebuild 1 ran them), and `box-held-past-the-lease`
  (#1824, #2089) on `2-1-0-infra-retry-diag.yaml`.
- **What the sample can say:** four rolls and one campaign show the deploy working and the line's changes
  recorded. They are not a reliability rate, and the record says so.

---

## 3. The frame

- **The shakeout's exit rule:** one shakeout campaign on the final deploy with no new seam finding (2.0's
  rule). A finding is fixed, the deploy rebuilt, and the shakeout re-run. The record reports how many
  rounds it took.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baseline beyond variance:** criteria verified all of their
    total, and correction rounds within the line's observed range (0–1);
  - **the run summaries carry the line's records** (§4, P1–P3) on every run that exercises them.
- **Fail:** a roll rejected, a boot audit failing, or a record missing where its run exercised it.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt. It is re-run under
  1.8.2's void rule and does not spend the budget.
- **Data, not failure:** a correction round, a repaired qa suite, lint findings (they are evidence, never
  a gate, #1937).
- **A framework fix during the set:** nothing merges while the set is open. A fix voids the set, and it
  restarts on a new deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every qa task of every roll records a lint reading, with both tools present on the stack's files and nothing `unavailable` (#1937) | each run's summary, `lint_findings` | a qa run with no reading, or a tool named `unavailable` |
| P2 | every failed round records its checks' own reasons, `tests_pass` included (#2028, #2086) | each run's summary, `round_failures[].failed_detail` | a failed round whose `failed_detail` is empty |
| P3 | a Next.js roll's detail page is seeded and renders (#2084) | the boot audit's route-render line | `/runs/{run_id}: not read` |
| P4 | the console's commands run as their caller (#2068) | a read command (`squadops.download_artifact`) posted to the console's command route (`:4040/api/commands/execute`) with a signed-in user's token, and again with none; the runtime's access log for both | the call with the token refused, or the call with none accepted. The console holds no credential (loaded check `#2068`), so an accepted call carried the caller's own token |

P4 is not exercised by a roll. It is read once on the final deploy, beside the diagnostics.

---

## 5. The shakeout campaign's policy

2.0's §5 values, carried, with two changes: the objective's target (2, §2), and `max_cycles` scaled to
it.

| field | value | basis |
|---|---|---|
| `objective.target_accepted_increments` | **2** | §2 |
| `max_cycles` | **7** | 1 calibration, 2 increments, one repair or retry each (2), 2 replacement increments: 2.0's rule for 3 increments, at 2 |
| every other field | 2.0's §5 | 2.0's shakeout basis, unchanged by this line |

---

## 6. Pins (read at registration)

| pin | value |
|---|---|
| deploy commit | read at registration |
| image ids | read at registration |
| deploy record | read at registration |
| model | `qwen3.8:27b`, digest read at registration |
| loaded checks | the final configs' tracked list, every row answering as expected at preflight |
| set configs | `docs/plans/verification-sets/2-1-0-cut-regression-{fastapi-react,nextjs}.yaml`, sha256 at registration |

---

## 6a. Readings so far (2026-10-06)

- **Precondition 1, the final deploy:** first built from `047d5d91`, with the whole last batch on main and
  main's CI green on it. All 48 tracked loaded checks answered with the new code: the console's (#2068),
  the qa and generalist images linting with ruff 0.16.6 and ESLint 10.12.0 (#1937), and #1031, #1692,
  #1824, #2086, #2084 and #414 among them. A backup was written first.
- **#1824's diagnostic found #2094 on that deploy.** The lease refusal fired and recorded its terminal
  kind, but `queued → failed` was not a legal transition, so the run stayed queued and the campaign
  stranded (`cmp_458a02ecc622`, aborted). The owner ruled the fix (a `fail_unstarted` edge, with SIP-0064
  §15a): #2095, merged as `6c3a1ca9`. **The final deploy was rebuilt from `6c3a1ca9` with that fix alone**
  (deploy record `dep_8bd6d707ca1d`), and all 49 rows of `scripts/dev/loaded_checks.yaml` answered with the
  new code, #2094's included.
- **The credential rotation (#2006) ran on that deploy** before the diagnostics, on the owner's go: a
  backup first, ten credentials rotated, and Langfuse's `SALT` and admin password kept. Every service
  answered after it. It changed no image. **Corrected:** the record said every container was healthy, but
  LangFuse's, recreated by the rotation, has failed its health check since. The check probes loopback,
  while the server binds the container's address, and the service itself answers (#2103).
- **#1824's diagnostic found a second defect on the rebuilt deploy** (`cmp_a17471e90130`). The refused
  run ended `infrastructure_failed`, and the cycle's attribution read the environment. But finalization
  records a verification summary for every run, so the cycle read `blocked_unverified`, and the
  continuation asked row 8 (repair) before row 10 (retry). The repair had no plan to work under, and the
  campaign escalated. The owner ruled the sequence (fix, abort, rebuild with the fix alone, re-run):
  #2102 (#2101, SIP-0109 §24bh), merged as `fcc7ce04`. **The final deploy was rebuilt from `fcc7ce04`**
  (`dep_5e77a9060e68`). All 50 rows answered with the new code, #2101's included, and the diagnostics
  chain re-runs on it (`cmp_9a26855746a9` first).
- **The set's configs are written** (`2-1-0-cut-regression-{fastapi-react,nextjs}.yaml`, carried from
  rebuild 4's): two rolls each, 48 tracked rows (#2068's and #1937-han's are left out, as #1982's is, because
  they ask services a set does not read), and the deploy pins read from the running deploy, re-read after
  #2101's rebuild. A counting
  preflight on 2026-10-06 refused only for the box being busy (the diagnostics' run and leases) and the
  main checkout's one untracked file. The image ids, the loaded checks and the framework matched.
- **P4, read once on that deploy:** with the CLI's token, the console's `download_artifact` command fetched
  its artifact (15,672 bytes; runtime `200`). With neither a token nor a session it was refused (runtime
  `401 Missing or invalid Authorization header`). Held.
- **Preconditions 2 and 3:** the diagnostics are re-running on the rebuilt deploy (`cmp_a17471e90130`,
  #1824's retry first, then the restart set), and the shakeout follows them on
  `examples/03_group_run/campaigns/2-1-0-cut-shakeout.yaml` (#2092).

## 7. Prohibited while the set is open

- **Merging to main.** A fix voids the set.
- **Rebuilding any service.**
- **Running anything else on the box,** the diagnostics included.

## 8. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or
  behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action.**

## 9. The owner's decisions at this stop

**Ruled 2026-10-06.** The supervisor recommended registering as drafted once the shakeout exits clean,
the diagnostics pass and the pins are read, and the owner agreed: "go with all". So decisions 1 to 4 are
taken as recommended below, and the supervisor registers.

1. **Register as drafted, or amend.** Nothing registers before the owner says so.
2. **The regression set's size:** two rolls per stack (recommended), or more.
3. **The shakeout campaign:** one campaign of two increments on React (recommended), or 2.0's three.
4. **Who supervises the shakeout:** the owner's delegate under 2.0's §3a policy (recommended, as 2.0).
