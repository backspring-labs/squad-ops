# 2.1.0 plan — hardening after Campaign: close the debt 2.0 deferred, no new capability

**Status: ADOPTED (2026-10-04), written while the 2.0 counted set ran.** The owner agreed the
recommendations in §5: "go ahead, record them and file the three issues". They are recorded there as
rulings, and §3's three issues are filed (#1956, #1957, #1958). The plan merges after the set closes,
since nothing merges while it is open (#1908 §7). Every issue it names was read in full, and its
placement is quoted from the issue. **Amended the same day** with the structure audit's ten issues
(§2.8) and its three for 2.3 (§6), on the owner's word (§5 ruling 11). **And again after the 2.0
cut** with the cut's three findings (§2.9, §5 ruling 12). **The line started the evening of 2026-10-04**,
on the owner's grant and stop list (§5 ruling 13). **Amended on 2026-10-05** with the line's own first
findings (§2.10) and the owner's rulings on the day plan (§5 ruling 14): #316 moves to 2.3, and #1469
leaves 2.1. The night's record is §7's last part.

**What 2.1 is.** An odd minor, a stabilization release (CLAUDE.md, #281): **feature-free by rule.** It
is the home for:
- the structural refactors kept out of 2.0;
- the defects and gaps the 2.0 shakeouts found and placed here;
- the evidence instruments that change no verdict.

**The question it answers:**

> **Does every path the 2.0 campaign relies on hold on its own terms, without a supervisor catching
> what the framework should have?**

The shakeouts answered "can a campaign run". 2.1 closes what they showed is held up by care rather
than by the framework:
- a retry row nothing reaches;
- a replay that misses proposal tasks;
- a stack whose proposal is told nothing;
- an audit that passes a page no browser can reach;
- the instruments behind the 2.0 record, which live outside the repository.

**What counts as 2.1 work:** a defect fix, a structural refactor proven behaviour-neutral, an evidence
instrument (reporting-only), a design question answered as a SIP amendment, or a guard on a step that
is guarded today only by memory. **Not 2.1:** any new capability a user or role gains. Those go to 2.2,
the next feature release, which carries Cross-Cycle Memory. The squad authoring its own backlog is
2.4. **The one exception is #1940** (§5 ruling 13): the `campaign-supervisor` role gains `create`,
`start`, `resume` and `abort` on a campaign, and nothing else. No other item may grant a capability
under it.

---

## 1. The open issues, every one placed

28 issues were open on 2026-10-04.

| where | count | issues |
|---|---|---|
| **closed at the 2.0 cut** | 3 | #1710 (the package renderings, after the set), #1711 (the runbook, after the set), #1941 (closed by #1953). **#1884 does not close:** the set read P9 falsified (pre-registration §10b), and it is inherited below (§4 step 1) |
| **features: 2.2 or later** | 4 | #557 (a post-retest governance review: a new LLM step, its SIP drafted), #949 (a revision boundary derived from the note), #950 (a review packet at the plan gate), #1708's remainder (the auto tier and the escalation queue) |
| **2.1: hardening** | 17 | §2 below |
| **2.1: the owner's scope request** | 1 | #1940, kept in 2.1 (§5) |
| **the crew's, listed in 2.1** | 1 | #1756 (the owner's ruling, 2026-10-03: not to be built outside the crew) |
| **out of 2.1's committed scope** | 1 | #1039 (the docs site's design pass; it rides any release, §5) |

**So 2.1 closes 18 of the 24 that stay open after the 2.0 cut** (17 hardening and #1940), plus the
new issues placed since:
- §3's three gaps (#1956, #1957, #1958);
- the crew's two enablers (§2.0: #1959, #1960);
- the memory SIP's 2.1 part (§2.6: #1964);
- **the SIP-portfolio rulings' nine** (§2.7): the anti-drift guards #1969, #1979, #1980, #1981; SIP-0109's
  #1971, #1972, #1973; SIP-0101's #1974; SIP-0105's #1975, with #1967 and #1968;
- the 2.0 set's findings (§4 step 1: #1961, #1962, #1995, and #1884 from P9);
- **the structure audit's ten** (§2.8): two latent defects (#1982, #1983) and eight structural issues
  (#1984–#1991);
- **the 2.0 cut's three** (§2.9): #2006, #2007, #2008;
- **the line's own findings** (§2.10): #2028, #2029, #2042.

**Moved out on 2026-10-05** (§5 ruling 14): #316 to 2.3, and #1469 until #2028's corpus exists.

#1756 and #1965 are the crew's, and #1039 rides any release. #1965 (Verification Yield: the test-value
audit, fault corpus and deletion experiment on the framework's own suite) is the crew's first
optimization experiment, placed in the 2.1 window as crew work by the owner's ruling of 2026-10-04. It
is listed so that its placement is visible, not to be built here.

---

## 2. The work, by theme

### 2.0 First: what the optimization crew needs to run the outer loop

The Nostromo IDEA (`docs/ideas/nostromo-framework-optimization-crew.md`) has the crew dispatch a
campaign, supervise it, and turn its results into framework fixes validated against a preserved
baseline. 2.0 built most of what that needs:
- the supervision interface and the box lease;
- the control log, with actor, reason and key on every operation;
- the evidence package, with per-cycle tokens and wall clock.

Four things stand between the crew and running that loop end to end. They lead 2.1 because they make
the rest of 2.1 measurable.

| issue | what it gives the crew | size | deploy |
|---|---|---|---|
| #1940 | **authority to dispatch.** Only `admin` holds `campaigns:control` (create, start, resume, abort). `campaign-supervisor` can read and rule, not launch. Without it the owner launches every campaign, and the IDEA's first acceptance criterion fails. **2.1's one feature exception, bounded to those four operations** (§5 ruling 13) | S | yes |
| #1956 | **the supervisor's instruments, tracked:** the watcher, the live-lease proof, the binding replay and the loaded checks, so the crew starts from what supervised 2.0 | M | no |
| #1959 | **a comparison:** replay any increment of any campaign outside it, on the current deploy, from its composed baseline (the PROMOTE row's `tree_ref`), its approved change request and the frozen criteria in force. The reference launcher (#1804) generalized; a script over the existing API | M | no |
| #1960 | **comparable numbers:** a per-increment scorecard from the records alone (executing vs waiting, tokens by role, rounds, repairs, criteria). The same arithmetic on a replay and its original | M | no (yes if the run persists its box wait) |

**#1756** (the full rendered prompt kept per generation) stays the crew's commission. The crew's own
investigations need it first: it has already cost two.

**The crew's first campaign** can run on the first 2.1 rebuild that carries #1940 (§4 step 3). It
re-runs the 2.0 set's pinned objective and policy, so the 2.0 set is its baseline at no extra cost.
After that, each framework change the owner approves gets:
- a prediction, written first (the IDEA's §7 schema);
- a replay of the same increments (#1959);
- the scorecards compared (#1960).


Size is relative: **S** is one PR, **M** is a few PRs or one with a design note, **L** needs a replay
proof or a SIP amendment and its own shakeout. Each row says whether it moves the deploy, because
deploy-moving work batches into rebuilds.

### 2.1 Defects the 2.0 shakeouts placed here

| issue | the defect | the fix | size | deploy |
|---|---|---|---|---|
| #1934 | proposal runs get `uuid4` task ids, so #1929's replay cannot recognise a re-attached proposal task, and it runs twice (seen on rebuild 18) | deterministic ids for every workload, as framing and implementation have (`task_plan.py:1309`) | S | yes |
| #1950 | the Next.js stack declares nothing for an optional field left out, so its proposals can repeat #1948 in mirror form | read a real Next.js emission; declare it (the template then says "left out" as well as a value) or record why it cannot | S | yes |
| #1913 | a qa task's own suite and typed checks run on a tree holding a file the runtime then drops as unauthorized, so the agent's verdict and the stored one read different trees | authorize before the agent-side evaluation, or evaluate on the authorized tree | M | yes |
| #1469 | `frontend_build` contributes one aggregate signature element, so a repair that fixes two of three unresolved imports reads as an exact repeat | one element per failing module, parsed from the bundler's output, validated on the corpus #1468 has been keeping since it stopped discarding stderr | M | yes |
| #1930 | an OpenTelemetry console exporter thread outlives pytest's capture and crashed an xdist worker at shutdown, with the run green | find the test that installs the provider; shut it down in a fixture | S | no |

**#1469 leaves 2.1** (§5 ruling 14). Its corpus count (posted on the issue, 2026-10-05) found one error,
repeated: three cycles of 2026-09-10, all `./app/layout.tsx` failing to resolve `./globals.css`. A failed
check's reason is never persisted, so the corpus cannot grow. #2028 persists it, in 2.1 (§2.10). #1469 is
placed again once that corpus holds failures of more than one module shape, and is re-read at 2.1's cut.

### 2.2 Campaign decisions that are written but not reachable

| issue | the gap | the work | size | deploy |
|---|---|---|---|---|
| #1824 | §10's retry rows (10–11) need `rejected` with an environment attribution. No cycle produces that: failed checks carry no locus, and an infrastructure failure ends the run `failed` | give attribution the locus (SIP-0108), so an environment-classed failure reads as one. Until then rows 10–11 stay reachable only by a constructed assessment, as the 2.0 record says | M | yes |
| #1757 | what `rewind` means for an unattended run: the same classification and equivalent evidence chose `patch` once and ended the run twice | **ruled (§5): run death is not its meaning.** A `rewind` on a `model_limitation` with repair unspent resolves to `patch`, a third anchor beside #994's two (`correction_policy.py:124-135`). A run that still ends is absorbed at cycle level by the campaign's repair and retry rows. Measured first: the stored decisions' model-limitation rewinds and what followed. The contentless-builder diagnostic then reaches its failure every time | M | yes |
| #1727 | whether the qa re-take path asserts SIP-0107 §20 (verified equals persisted), and what the transaction is when a self-evaluation pass completes a re-take | **ruled (§5): assert §20 on the re-take path, as the patch path does.** That also catches #1913's class. **The transaction is the re-take plus the pass**, because §20 is asserted on the tree that passed. The record names each part (the edit, the file the pass added), so an edit-only count stays derivable. A SIP-0107 amendment | S–M | yes |

### 2.3 Verification and evidence gaps

| issue | the gap | the work | size | deploy |
|---|---|---|---|---|
| #1796 | the boot audit checks the API calls the UI makes, not that each declared client route renders its view. #1794's rolls passed it with a page no browser could reach | the boot audit's half, reusing the render check the campaign evaluation already runs (§24p) and the release capture uses | M | yes |
| #1954 | `campaigns create` records nothing about the file that made the campaign. Shakeout 10 reconciles with seven identical definitions, and which one was passed is recorded nowhere | the create request carries the file's sha256 and path, stored on the create row; provenance becomes a lookup checked by the reconciliation | S | yes |
| #1937 | no linter runs on the delivered app, so there is no debt signal for 2.4's lead-proposed refactors | ruff and ESLint with fixed, repository-declared rule sets, recorded **as evidence, never as a gate** (the owner's placement, 2026-10-03) | M | yes |
| #1911 | a dev correction repair can spend its whole 12,288-token completion on reasoning and emit nothing | **measure first:** how often, on which tasks, and whether scoped revision drives it. A budget changes only on that evidence | S then ? | no, then maybe |

### 2.4 Structural refactors, each proven behaviour-neutral

These are the odd minor's reason to exist. Each lands alone, with its proof, so that a regression in
the release is attributable to one refactor.

| issue | the refactor | the proof it carries | size | deploy |
|---|---|---|---|---|
| #567 | the fenced parser's recognition moves to a CommonMark-spec engine, with the mapping strategies kept on top. Five malformation classes were each found live (#430, #470, #502, #528, #566) | **the owner's gate (2026-09-29):** every stored real emission replayed through the new engine with identical results; a difference is a finding, read before merging | L | yes |
| #316 | the request-profile taxonomy: 15+ names drawn from four axes. Campaign now selects profiles by name in its policy, the condition the issue set for doing this | `SIP-Cycle-Request-Profile-Naming-Taxonomy` (proposed) accepted first. Persisted names on terminal rows keep their historical labels (no cosmetic migration) | L | yes |
| #414 | the correction budget is one severity-blind pool. **Its deferral trigger has fired:** "a request profile declaring SIP-0096 `required_checks`". `campaign-increment` and `validated-fullstack` both declare them (`tests_pass`, `frontend_build`, `required_files`), each with 3 attempts | **ruled (§5): the priority reserve.** Each required check keeps one reserved attempt, so completeness failures cannot take the last one. Proven by replaying stored correction ledgers: which runs would have spent differently | M | yes |

**#316 moves to 2.3** (§5 ruling 14). Its SIP is still proposed, the work is L, and nothing in 2.1
depends on it. It joins the structure audit's batch (§6). The SIP's placement and its portfolio row move
with it.

### 2.5 Generation quality, placed here by the owner

| issue | the gap | the work | size | deploy |
|---|---|---|---|---|
| #1031 | the manifest author designs APIs with no conventions in frame (`participant_not_found` → 400, where 404 never entered the decision) | a stack-scoped design primer through PromptService, plus a schema-gate finding for an unexamined deviation | M | yes |
| #1692 (remainder) | the prior-cycle brief is built for repair, retry and the proposal after an abandoned increment. Not built: the correction chain's own record, and the recurrence measure | both, from typed records only (SIP-0096's integrity rule) | M | yes |

### 2.6 Placed in 2.1 by a SIP, not by an issue

| SIP | what it places in 2.1 | size | deploy |
|---|---|---|---|
| `SIP-Cross-Cycle-Memory` (proposed; **#1964**; placement by the owner's ruling of 2026-09-12, the 1.8.0 plan §8 decision 2) | **the recall port, inert:** a NoOp that answers *empty* (not `NoOpMemoryPort`, which raises), injected explicitly by the composition root, and the call site through `plan_rejection_context` (declared on six task types). **And a re-read** of the SIP's Phase-1 value hypothesis against the recurrence evidence available at 2.1's cut, so 2.2 activates memory on a workload that is actually live. The port answers empty, so no verdict, prompt or gate changes | M | yes |
| `SIP-Outcome-Evaluation` (proposed 2026-10-04, PR #1963) | **phase 0 only:** #1959 and #1960, already in §2.0. Its reporting-only instruments are 2.3's, and its feature half heads 2.4 | — | — |

**Missed in this plan's first draft, found reading the memory SIP on 2026-10-04.** It has no issue,
and the ruling places it here. Filed as **#1964**.

### 2.7 From the SIP-portfolio rulings (2026-10-04)

The owner ruled on the read-only audit of every accepted, proposed and implemented SIP
(the SIP portfolio, PR #1970): "I accept all your other recommendations to keep SIPs current,
reflecting what gets delivered, and where the work is targeted". He also asked how to prevent the
drift the audit found.

| issue | what | size | deploy |
|---|---|---|---|
| **#1969** | the ledger guard: every accepted SIP has a delivery ledger; placed rows name open issues; shipped rows name a tag or PR; no header names a tagged release as a future target | S | no |
| **#1979** | a `sip:NNNN` label per SIP; the guard matches ledgers to labelled issues; closing a `sip:` issue requires the ledger change | S | no |
| **#1980** | `sip_sweep.py`: the cut's SIP sweep, read from the ledgers | S | no |
| **#1981** | the SIP template's intake check and ledger, required in new proposals | S | no |
| #1967 | the S5 admission gate's empty-string blind spot (SIP-0105) | S | no |
| #1968 | `proposed → deprecated` in `update_sip_status.py`, so the 12 ruled deprecations can execute | S | no |
| #1971 | a launch the preflight refuses is escalated (SIP-0109 §24e) | S | yes |
| #1972 | the sweep re-hears an ended cycle between restarts (SIP-0109 §24v) | S | yes |
| #1973 | a Next.js render profile (SIP-0109 §24p), with #1950 and #1962 | M | yes |
| #1974 | the benchmark registry's replay-exclusion test (SIP-0101 §4.1) | S | no |
| #1975 | delete SIP-0105's four falsified fields | S | yes |

**The anti-drift four lead,** with #1956, before 2.1 ships any SIP part: this line is the first to be
held to the ledgers.

### 2.8 From the structure audit (2026-10-04)

A read-only audit of `src/` (99k lines) and `adapters/` (28k) checked for best practice, drift, dead
code and structure, with 2.x and 3.x in view. Every number below was measured on `b09883c9`. **What
held:**
- the 24 architecture guards;
- no real `TODO` in source;
- no blocking subprocess call in async code;
- the route lanes, with zero recorded deviations.

**What did not hold** is where no guard reaches.

| issue | what | size | deploy |
|---|---|---|---|
| #1982 | **defect:** the sandbox service crashes at startup when its token is a `secret://` reference (`SecretManager()` with no provider). Latent: compose passes a literal. Found by the audit's mypy run | S | yes |
| #1983 | **defect (plausible, not observed live):** a timed-out `npm` or test subprocess is killed without its children; 14 sites re-implement the timeout by hand. One bounded-run helper with a process-group kill | S | yes |
| #1984 | **dead code, about 1,900 lines no composition root builds:** the in-process flow executor (and its 18 tests of a path production never runs), the SIP-0.8.8 task and agent services every agent constructs and never calls, the task registry port and its adapters, the health auth deps | M | yes, neutral |
| #1985 | **the package root's eager import** makes any `squadops.*` import load ~144 modules (4–20 with it thinned), hiding the `capabilities` ↔ `cycles` graph behind 91 deferred imports. Thin the root and two package `__init__`s; a direction guard | M | yes, neutral |
| #1986 | **three hand-assembled gate-decision recorders,** and `gate.decided` already has two shapes (keyed on the gate from the route, on the run from the machine paths). One recorder, before #1940 and #1708's auto tier add deciders | S–M | yes |
| #1987 | **the executor's wiring:** dependencies pass through `**kwargs` and default to `None`, and `box_verdict=None` reads no box. Typed parameters; safety-relevant dependencies required (the 1.8.2 `task_timeout` treatment) | S | yes, neutral |
| #1988 | **tooling:** ruff and mypy target Python 3.11 under a 3.12 project, `[tool.black]` is dead config, and mypy never runs (451 errors on one run, #1982 among them). 3.12 targets; mypy in CI as a ratchet | S–M | no |
| #1989 | **the architecture map:** CLAUDE.md omits 9 of 25 core packages (`campaigns` among them) and names closed issues as open deviations; three architecture docs date from 2025. One overview with a two-sided guard, the #1969 pattern | S | no |
| #1990 | **small duplicates:** CLI `_get_client` ×10, `_sha256` ×4, `_parse_str_list` ×3, the scaffold-integrity emitter ×2 (a 1.7.5 landmine never filed), and the unreadable-vault-ref rule ×5, silent where the rule is a warning | S | yes, neutral |
| #1991 | **environment variables outside the config loader:** ~15 with no inventory, `LLM_MODEL` as a model selection path, `SQUADOPS_BASE_PATH` read around `PathResolver`. An inventory and a guard | S | yes, small |

**Folded into existing issues, not filed:**
- **#1976 (API contract hardening, 2.3):**
  - the cycle list's documented N+1 (one query per cycle, 694 cycles today, and campaigns multiply them);
  - the three per-router error-envelope builders;
  - the plain-string error bodies left on the health, agent-status and auth routes;
  - 500 responses that carry the exception's text.
- **#1983:** the 14 subprocess sites.

**Placed in 2.3, not here:** the structural batch (#1992, #1993, #1994; §6). Each is L or M–L and
depends on #1985's direction guard.

**Not worth doing, and why:**
- **Blocking file reads in async code (43 sites):** KB-sized files on one box, and no stall has been
  measured.
- **Import time (168 ms):** irrelevant to long-running processes, and #1985 fixes it anyway.
- **Regrouping `cycles/` (78 flat modules) for navigation alone:** only the moves with a
  dependency-direction payoff earn their churn.
- **The 307 broad `except` blocks:** mostly deliberate fail-open observability. The 25 silent ones were
  read; the vault ones are #1990's.

### 2.9 From the 2.0 cut (2026-10-04)

Found while cutting v2.0.0 and v2.0.1. Each surfaced from a step of the release cut, not from a
campaign.

| issue | what | size | deploy |
|---|---|---|---|
| #2006 | **a bootstrapped deploy keeps the default credentials the repository commits.** The records scan named fifteen of the deploy's credential values as already public, among them the Keycloak DB password, which `docker-compose.yml` sets as a literal. The work: bootstrap generates per-deploy secrets; compose reads every credential from env or secrets with no literal (**the compose step needs the owner's explicit OK**, given at the line's start, §5 ruling 13); `.env.example` keeps placeholders; `doctor` refuses a committed default; a rotation note for existing deploys | M | yes, plus a rotation |
| #2007 | **a runtime restart leaves the interrupted run's Prefect flow runs open forever.** Nine stayed `RUNNING` for 20–30 hours after their runs completed: the proposal and framing flow runs of three recovery-diagnostic campaigns, with the framing run duplicated by the re-attach. Cleared by hand on the owner's go-ahead. The fix: the startup re-attach and sweep close the dead process's flow runs | S | yes |
| #2008 | **the delivered-app capture cannot photograph a reference-scenario cycle:** it stores no `interface_manifest.yaml`, only the seeded candidate manifest, so the v2.0.1 package shows the Prefect run only. The fix: read the seeded manifest, and check the tree for #2000's stub shape on the first capture | S | no |

**Fixed at the cut, not here:**
- **#2000:** the capture rebuilt a campaign increment from its run's scaffold stubs rather than its accepted tree. Fixed in #2001.
- **The records scan's false refusal:** it refused on a secret value the repository already commits. Fixed in #2005.

### 2.10 Found during the line (2026-10-05)

| issue | what | size | deploy |
|---|---|---|---|
| #2028 | **a failed check's reason reaches no durable store.** #1470 put the bundler's stderr on the `frontend_build` row's `reason`, and that row is transient: `cycle_failure_records.event` has no reason field, and the run's summaries and reports say "frontend build failed (exit 1)". Found measuring #1469's corpus (§7 item 8). The fix: the failing row's reason, bounded as the row bounds it, on its failure record, every check, with a test at the seam that writes the failure set | S | yes |
| #2029 | **a gate approved with refinements stores its notes after the run's artifacts are promoted, and nothing reads them.** Found doing #1986. A reader would be a feature, so the 2.1 fix is the smallest: the notes are promoted when they are stored, so they stay on the record and forward with the plan, and the CLI's help says they are recorded for the operator, not acted on | S | yes |
| #2042 | **a restart between a run's completion and its queued successor's start strands a campaign cycle.** `reattach()` continues only a latest run that is running or completed, `_start_first_run()` only an earliest run that is queued, the sweep looks at neither, and `max_elapsed_s` is read only when a cycle ends. The fix: startup starts a queued run that follows only completed runs, once, and a recovery diagnostic restarts in that window. Rides step 3 with the restart work (#1934, #2007) | S–M | yes |

---

## 3. Gaps the 2.0 run exposed, filed on adoption

Found while running the 2.0 shakeout loop and the registration. Each is a guard that today is
held by memory or by one session's scratch files.

1. **#1956: the supervisor's instruments live outside the repository.** The 2.0 record cites outputs whose
   producing scripts were session-local:
   - the live-lease proof (#1802's five steps, with the audit read);
   - the #1943 binding replay (each promotion's frozen statements recomputed through the runtime's
     lookup);
   - the loaded-check script whose readings are #1908's §6 pins;
   - the campaign watcher.

   A reader of the record cannot re-run them. **The fix:** each under `scripts/dev/`, with tests, and
   the record citing the tracked path. **Size:** M. **Deploy:** no.
2. **#1957: release-cut steps 4 and 8 are unguarded** (CLAUDE.md says so): the ROADMAP timeline entry and the
   worktree sweep. **The fix:** a check per step, in the shape of `check_release_packages.py`.
   **Size:** S. **Deploy:** no.
3. **#1958: a pinned input carries mutable prose.** The 2.0 set's two policy files name "rebuild 19" in their
   header comment. They were written before rounds 8–10, and the pin is to their bytes, so the comment
   cannot be corrected without moving the pin. **The fix:** a rule in
   `examples/*/campaigns/README.md`: a pinned definition's comment says what the file is, never which
   deploy it will run on. A lint can enforce it. **Size:** S. **Deploy:** no.

---

## 4. Sequencing

Deploy-moving work batches into rebuilds, and each structural refactor gets a batch of its own.

1. **Inherit the 2.0 set's findings.** Whatever the set and the cut place in 2.1 goes first: they are
   live evidence, and their fixes may touch the same seams as the rows above. **So far:**
   - **#1961**: the proposal rails accept a feature whose derived footprint holds no source file (an
     empty manifest delta), so no build could satisfy it. Found at campaign 1's increment 2 gate; the
     supervisor's gate caught it, so nothing was fixed during the set.
   - **#1962**: the proposer is told one of the stack's frozen conventions (#1948), not the rest. A
     required request string is already trimmed and refused blank (#593), so a name-normalization
     proposal was new behaviour only on paper. Same campaign and increment, version 2. Built with
     #1950, as one declaration.
   - **#1995**: a proposal's PRD delta can state more than its manifest delta, criteria and footprint carry
     (campaign 2, increment 1 v1: the display in the text, nowhere else). The supervisor returned it; the rails
     did not notice. Read with #1962: both concern what the proposer is told.
   - **#1884**: **the set read P9 falsified** (pre-registration §10b). The frozen criterion files add rules the
     approved requests never stated: campaign 1 T1's tie order, and campaign 2 T4's white-box check that the store's
     order is untouched. The supervisor cannot see a criterion file at the gate, because it is authored after approval.
     So the fix is on the qa author's side, or in what the evaluation freezes (#1884's two directions).
     **Ruled by the owner (§5 ruling 13):** a qa author may add tests only for behaviour already
     required by the frozen criteria or another explicitly accepted artifact. Behaviour it judges
     desirable but unsupported is returned as a proposal, never encoded in a test that gates or repairs
     the current run, and where the test file lives does not change that. §7 item 4 says how.

   **The set closed PASS** (both campaigns success, every safety guarantee held). These four are its findings.
2. **The SIP record's guards** (#1969, #1979, #1980, #1981, #1967, #1968: tooling, no deploy), so every
   later step updates the ledgers it touches. **The audit's tooling rides with them:** #1988 (3.12 targets,
   the mypy ratchet) and #1989 (the architecture overview and its guard). So does #2008, the
   reference cycle's capture, which is a release script. Then **the crew's tooling and the instruments, before
   anything they would measure:**
   - #1956 (the supervisor's instruments, tracked), #1959 (the increment replay) and #1960 (the
     per-increment scorecard);
   - #1911's measurement, #1469's corpus count, and #1757's read of the stored model-limitation
     rewinds.

   Nothing deploys.
3. **Defects, batch 1, with the crew's authority:**
   - #1940, #1934, #1950, #1913, #1930 and #1954 (deploy-moving, small), and #1960's box-wait field
     if taken;
   - #1957 and #1958 (tooling, no deploy);
   - #1964's inert recall port and its call site: a seam that answers empty, so nothing it touches
     changes behaviour;
   - #1971, #1972 and #1975 (small, deploy-moving), and #1974 (a test);
   - **the audit's defects and ground-clearing:** #1982 and #1983 (the two latent defects); #1984 (dead
     code, behaviour-neutral) and then #1987 (the executor's typed wiring, which #1984's deletion
     simplifies); **#1986 (one gate-decision recorder) lands before #1940** in this batch, so the supervisor's
     authority arrives on one recording path;
   - **#2007** (a restart's orphaned flow runs), with #1934, since both are the restart re-attach's. The
     batch's overlapping recovery diagnostics restart the runtime mid-cycle, so they read it: no flow run
     may stay open after its run ends;
   - **#2042** (a restart between two runs strands the cycle), with them, and its own diagnostic: a
     restart after the successor is created and before it starts;
   - **#2029** (refinement notes promoted when stored), beside #1986.

   Then a rebuild, the regression pair, and the overlapping recovery diagnostics
   (`restart-at:at_proposal` for #1934). **The crew's first campaign can run on this deploy** (§2.0).
4. **The ruled answers:** #1757 (the third rewind anchor) and #1727 (§20 on the re-take path, read
   with #1913). Each becomes a SIP amendment in the PR that implements it.
5. **Verification gaps:** #1796, #1937 (reporting-only), #1824's attribution locus, #2028 (a failed
   check's reason persisted, which #1469's corpus needs), and #1973 (a Next.js render profile, with #1950
   and #1962), with a rebuild and the regression pair. **Steps 4 and 5 share that rebuild** (ruling 14):
   neither is a refactor. **The audit's small consolidations ride here:** #1990 (duplicated helpers; adds
   a warning where the vault rule was silent) and #1991 (the environment inventory and guard). **So
   does #2006** (per-deploy credentials), which #1991's inventory informs. It rotates every credential
   in place before its rebuild. Its compose step has the owner's OK (§5 ruling 13).
6. **Refactors, one per batch, each with its replay proof:** #1985 first (the package imports and the
   direction guard, so later refactors' import moves are visible), then #414, then #567. Each gets a
   rebuild and the regression pair before the next begins. #316 moved to 2.3 (ruling 14).
7. **Generation quality:** #1031 and #1692's remainder. These change what the model is shown, so they
   go last and are read on the cut's evidence, not mixed into a refactor's batch. **Their rebuild is the
   final deploy** (ruling 14): the cut's regression set and shakeout run on it.
8. **The cut:** a regression set on both stacks, one campaign shakeout on the final deploy, and the
   release cut procedure (CLAUDE.md). **#1964's re-read** of memory's Phase-1 hypothesis happens here,
   against the evidence the line produced, and is recorded as an amendment to that SIP before 2.2
   begins.

---

## 5. Ruled by the owner, 2026-10-04

The supervisor recommended, and the owner agreed: "go ahead, record them and file the three issues".

1. **The placements in §1 are adopted as drafted.**
2. **#1940 stays in 2.1** (the supervisor role creates and manages campaigns; escalation stays the
   owner's). It is a scope change the owner asked for, small, and moves no verdict. It revises SIP-0109
   §24al's split between the owner's authority and the supervisor's seat, so it carries that amendment.
3. **#1039 is out of 2.1's committed scope.** It is not hardening and does not depend on any release;
   it rides along whenever the docs are next touched.
4. **#1757: run death is not the meaning of `rewind` for an unattended run.** A `rewind` on a
   `model_limitation` with repair unspent resolves to `patch`, the same shape as #994's two anchors. A
   run that still ends is absorbed at cycle level by the campaign. The stored decisions are read first.
   The second question follows: the contentless-builder diagnostic reaches its failure every time.
5. **#1727: the re-take path asserts SIP-0107 §20, as the patch path does,** which also catches
   #1913's class. **The transaction is the re-take plus the self-evaluation pass,** with each part
   named in the record. The count it was to decide stopped mattering when the flip was ruled; the
   answer is about the record's correctness.
6. **§3's three issues are filed** (#1956, #1957, #1958), and **#1956 leads 2.1**: until the
   instruments are tracked, no one but their author can re-run what #1908 cites.
7. **#414: the priority reserve**, proven by replaying the stored correction ledgers.
8. **The order in §4 holds:** measurements before the changes they inform; one refactor per rebuild,
   each with its replay proof; prompt-content items (#1031, #1692) last, never in a refactor's batch.
9. **#1756 stays the crew's** (the owner's ruling, 2026-10-03). It is listed so that its placement is
   visible, not to be built here.
10. **The optimization crew's enablers lead 2.1** (§2.0). The owner, on the Nostromo IDEA: "yes, file both
    and add them to the 2.1 plan". The new issues are #1959 (the increment replay) and #1960 (the
    per-increment scorecard). They join #1940 and #1956, so the crew can run its first campaign on 2.1's
    first rebuild, with the 2.0 set as its baseline. Not built for it:
    - supervisor-authored PRD increments. SIP-0109 keeps proposing with the strategy role, and the
      supervisor steers through notes and the objective's bounds. Changing that is a design change,
      2.2 at the earliest;
    - a ship's recorder inside SquadOps. It is the crew's (Mother), over SquadOps' API.
11. **The structure audit's placements are adopted.** The owner, on the audit: "go ahead, file them and add
    to the 2.1 plan, plus the 2.3 recommended items". Placed:
    - **in 2.1:** #1982–#1991 (§2.8), sequenced in §4;
    - **in 2.3:** #1992–#1994 (§6);
    - **into #1976:** the small API items.

    **The `capabilities` package keeps its name.** 1,209 import sites would move for no behaviour. 3.x's
    bindable-competence work (Capability-Backed Agents) takes a distinct package, recorded in that SIP's
    intake note.
12. **The 2.0 cut's three findings are placed here** (§2.9). The owner, on the default credentials:
    "file it for 2.1"; on the three: "go ahead and add them to the 2.1 plan". #2006's compose change
    is still the owner's to approve when it is built (CLAUDE.md: compose is never changed without an
    explicit request).
13. **The line starts, 2026-10-04 evening.** The owner: "I want to start the 2.1 line and I give you the
    authority to merge PRs, address issues as you find them and use your best judgement to address the
    spirit of the fix", and then "yes to rebuilds, stop list approved, can't you also make a docker yaml
    change?". The owner's decisions on this PR's review (2026-10-05, recorded on PR #2010) settle three
    points the review raised:
    - **Covered:** merging a 2.1 PR when every check is green and its own evidence reads clean (main's
      whole run read before the next merge); rebuilds; and uncounted validation runs (the regression
      pair, the recovery diagnostics, shakeouts).
    - **`docker-compose.yml`: an explicit owner exception for the whole 2.1 line,** not derived from
      #2006. A compose change a 2.1 item needs is made under it, and the PR names this ruling. Service
      and container names stay as they are, since nothing in 2.1 needs a rename.
    - **#1940 is 2.1's one feature exception,** bounded to the `campaign-supervisor` role's `create`,
      `start`, `resume` and `abort` on a campaign. The odd minor's feature-free rule otherwise holds.
    - **#1884's rule:** "a QA author may add tests only for behavior already required by frozen
      criteria or another explicitly accepted artifact. Unsupported desirable behavior must be returned
      as a proposal, not encoded in a test that gates or repairs the current run. Test-file placement
      does not alter the rule." It applies to both the planning and the `qa.test` render paths, with
      testable refusal and proposal behaviour (§7 item 4).
    - **The stop list:** a tag, a Release or any public upload; #316 until its SIP is accepted; a
      security finding (handled privately); a red on main that cannot be explained; anything that would
      reverse a ruling above; the crew's items (#1756, #1965, the crew's first campaign).
14. **The day plan, 2026-10-05.** The supervisor proposed the day's order and four decisions, and the
    owner answered: "go and good with all your recommendations". Recorded:
    - **#316 moves to 2.3,** with the structure audit's batch (§2.4). Its SIP is still proposed, the
      work is L, and nothing in 2.1 depends on it. The stop list's #316 item lapses with it.
    - **#1469 leaves 2.1** (§2.1). Its corpus is one error repeated, and it cannot grow until #2028
      persists the check's reason. #2028 ships in 2.1.
    - **Steps 4 and 5 share one rebuild batch.** Refactors stay one per rebuild (#1985, #414, #567),
      and step 7's rebuild is the final deploy the cut's set runs on.
    - **#2006's credential rotation is brought to the owner before it runs,** with a backup written
      first and the exact commands. Its compose change is under ruling 13.
    - **The line's own findings are placed** (§2.10): #2028, #2029, #2042.
    - The tag, the Release and the records upload stay the owner's.

## 6. What this plan does not decide

- **The 2.0 set's own findings:** placed in §4 step 1 (#1961, #1962, #1995, #1884). A finding of
  2.1's own regression set or shakeouts is placed when it is found.
- **The cut criteria's exact numbers** (the regression set's size, the shakeout's exit rule): written as
  the pre-registration when 2.1's last batch is built, as 1.9 and 2.0 did.
- **The line after 2.1**, ruled 2026-10-04 and recorded in the ROADMAP's horizon:
  - **2.2:** Cross-Cycle Memory, the line's only change to squad behaviour, with #1708's auto tier and
    escalation queue;
  - **2.3:** Outcome Evaluation's reporting-only instruments, the comms (#1977) and API-contract
    (#1976) hardening, the request-profile taxonomy (#316, ruling 14), and **the structure audit's
    batch**, ahead of 2.4's executor-heavy feature work:
    - the orchestration move out of `adapters/cycles` (#1992);
    - the `stacks` extraction (#1993);
    - the largest units split by the 1.7.5 method (#1994);
  - **2.4:** Outcome Evaluation's feature half, with #1966 and then #557, #949 and #950;
  - **2.6:** the squad-authored backlog (no SIP yet), and Test-First's greenfield gate (#1978);
  - **3.x:** the runtime-mode family (SIP-0088, 0090, 0091), duty work, and Capability-Backed Agents.

## 7. The first night (2026-10-04 → 2026-10-05)

The order the line starts in, under ruling 13. The owner reviews this section before any of it merges.
It covers more than one night holds, on purpose: the measured steps set the pace (a PR's CI takes
4–9 minutes, and main's run after each merge is read before the next merge), not the writing.
**Expected by 08:00 ET:** step 1 merged, and step 2 under way. #1884's outlet and #1961's vault
replay make step 1 larger than it read before the review. The first rebuild comes after 08:00.

**How each PR is held:**
- **One issue per PR,** or the pair §4 names together. The PR body carries `Closes #N` (or
  `Refs #N — remaining: …`). Every test answers "what bug would this catch". A changed seam
  gets a wiring test that enters at the live caller.
- **Gate before merging:** the full local regression, run with `pipefail`, and its count line read.
  A prompt change goes through PromptService, with the template's version bumped and a render test.
- **A change to SIP-0109 behaviour carries its amendment and ledger row in the same PR.** That
  covers the rails, what the proposer is told, and what the qa author asserts.
- **Merge** when every check is green and the PR's own evidence reads clean, squashed, with the
  branch deleted. Then main's whole run is read before the next merge. A red on main stops merging
  until it is explained.

**Step 1: the 2.0 set's findings.** These are deploy-moving, so they ride step 3's rebuild.

**The seams step 1 touches, and what each sees.** The 2.0 rework clustered where one fact has several
readers, so each item below names the seams it changes, and the table says what each seam reads today.

| seam | where | what it sees | step 1 changes it? | when the declaration or file is absent |
|---|---|---|---|---|
| proposal rails | `validate_proposal`, `campaigns/change_request.py:438`; the footprint, `:398` | the authored request and its context: the accepted manifest's text, the allowed scope, the prior criteria ids. No tree | #1961: a new refusal | a `feature` or `fix` whose footprint is only the qa test namespace is accepted today. After #1961 it is refused, and the refusal returns to the proposer inside its task. A `refactor` is unaffected |
| proposal rendering | `StrategyProposeIncrementHandler.handle`, `handlers/planning/proposal.py:112-119` | the run's `campaign_proposal` block (the manifest's text, the objective, the prior criteria with their statements, the PRD, a supervisor note) and the stack, by `build_profile` | #1962 and #1950 (conventions); #1961 and #1995 (template lines); #1884 (a section of proposed behaviours) | a stack that declares no convention, or is not registered, gets no section, as #1948's line does today. A campaign with no stored proposed behaviours gets no section |
| plan-author rendering | `render_surfaces`, `handlers/_plan_authoring.py:89-99`; its indexes, `cycles/task_plan.py:681-690` | in a framing run: the approved change request (`increment_change_request`), each new criterion's file, the frozen files | #1884: a new `INCREMENT_SURFACES` entry (`_plan_authoring.py:65`) renders `request.increment_test_scope_appendix` from `increment_test_scope`, which `_inject_increment_indexes` (`task_plan.py:657`) composes for every increment framing. #1886's section leaves the criteria appendix | **#1886's rule rides inside the criteria appendix, which renders only when the change has criteria (`:96`).** So a `refactor` increment's plan authors never see it. After: it renders for every increment framing, and for no framing outside a campaign |
| `qa.test` author | `QATestHandler.handle`, `handlers/cycle/qa_test.py:1614` (`request.qa_test.test_validate` and its appendices); its increment inputs, `task_plan.py:760-770` | the plan's task, the frozen surface, the behaviour contract, its own earlier attempt on a self-evaluation pass (`cycle/base.py:1078`). **Nothing of the change request:** an implementation run's `qa.test` gets `{}` from `_increment_inputs` | #1884: `increment_test_scope`, composed by `_increment_inputs` for each task type that declares the new context-contract property (`TaskType.QA_TEST`, `context_assembly.py:213`), and rendered through `request.increment_test_scope_appendix`. A re-take re-dispatches this same envelope (`dispatched_flow_executor.py:186`), so it carries the key. **It is the one author that may emit the proposal block** | absent from every run today. After: a run outside a campaign still gets none of it |
| `qa.test_repair` author | `QATestRepairHandler`, `handlers/impl/repair_handlers.py:1316`, through `_RepairPromptMixin` | reached only on the own-artifact locus (the suite missing, unparseable or uncollectable, never a behavioural failure): the failed task's suite and its failure evidence, re-authored as files or fills (`:1343`). **Its envelope is built by the correction loop** (`adapters/cycles/correction_repair.py:1021-1080`), **not by `_increment_inputs`.** It forwards the failed task's inputs only through a fixed key list and `REPAIR_PRESENCE_KEYS` (`context_assembly.py:466`, applied at `correction_repair.py:1058`) | #1884: `increment_test_scope` joins `REPAIR_PRESENCE_KEYS`, and the same asset renders through `_RepairPromptMixin` (`repair_handlers.py:253`). **It may not emit the proposal block:** a repair re-authors a broken suite, and proposing belongs to the authoring task | **without the forwarding, a repair never sees the rule.** A repair outside a campaign carries no key. A block in a repair's emission is kept out of its artifacts (never a workspace file) and named in its evidence as ignored |
| the proposal block's parser | new: `squadops.campaigns.proposed_behaviours`, called where `QATestHandler` splits its emission into files | one fenced block, `yaml:proposed_behaviours.yaml`, in the `qa.test` emission | #1884: new | **absent:** nothing stored, no row. **Valid:** one artifact of type `qa_proposed_behaviours`. **Malformed:** see item 4 |
| which artifacts enter a tree | two rules: the allow-list `WORKSPACE_ARTIFACT_TYPES` (`cycles/delivered_tree.py:29`), and the correction runner's deny-list `_NON_WORKSPACE_ARTIFACT_TYPES` (`adapters/cycles/correction_runner.py:1504`), which picks a repaired suite's retest files | a run's stored artifacts by type | #1884: the deny-list gains `qa_proposed_behaviours` | **the allow-list already excludes the new type. The deny-list does not:** without the change, a retest would run the proposal file as a test |
| the next proposal's launch | `_propose_launch`, `campaigns/progress.py:991` → `increment_launch`, `campaigns/launch_requests.py:56` | the accepted cycle, the control log's frozen criteria, the abandoned increment's brief | #1884: the stored entries join the `campaign_proposal` block | no stored entries: no key. **A vault read that fails raises,** and the re-hearing retries it. It never launches without them (the launch is a function of stored data alone, #1943's rule) |
| baseline evaluation | `discrimination`, `campaigns/acceptance.py:89`; the verdict, `:238` | the accepted tree as seeded and the candidate, each running the criterion's own file alone | no | a criterion file collected on neither tree reads `not run`, so the increment is blocked, never accepted (`:247-252`) |
| criterion freezing | `freeze_bundle`, `campaigns/evaluator_trees.py:153`; `_freeze_bundles`, `campaigns/progress.py:773` | the candidate tree: the criterion's file, the test-surface files it imports, the stack's config files | no. #1884 changes what a file asserts, not how it is frozen | a missing file or import raises `BundleIncomplete`, and nothing is frozen. The increment is blocked (`campaigns/acceptance_run.py:118`, `:154`) |

1. **#1961, the issue's option 1.**
   - **The rail:** after the footprint is derived, a `feature` or `fix` whose footprint holds nothing
     outside the qa test namespace is refused with a new kind, `nothing_to_build`: "this change
     declares nothing for a build to implement; a behaviour change needs the manifest delta that
     declares it".
   - **The template** adds one line: the accepted manifest is what the application does, so every
     endpoint, error code and field it declares is already implemented.
   - **Acceptance:**
     - the stored bytes of `prop_5fb2d8136c36` v1 (campaign 1, increment 2: empty delta, criterion T2),
       copied as a fixture with its baseline manifest, are refused `nothing_to_build`;
     - the same request carrying a delta that declares its change passes this rail, and a `refactor`
       with an empty delta is not refused by it;
     - every stored `change_request` artifact in the vault is replayed through `validate_proposal` with
       its stored context, on the box, and listed in the PR by artifact id. An approved request the new
       rail refuses is a finding, read before merging;
     - a wiring test through the proposal handler's `handle()` finds the template line in the prompt
       sent.
2. **#1962 with #1950: one declaration of a stack's frozen conventions,** as data on `ScaffoldStack`.
   It replaces `unset_optional_response`, so there is one mechanism, not two. Each convention renders
   through one managed asset that replaces `request.proposal_unset_optional`, and each is held to the
   generated bytes by a test.
   - **FastAPI declares four:**
     - an optional field left out comes back as `null` (today's test);
     - a required request string is trimmed, and refused with 422 `validation_error` when blank (#593).
       Held by the generated model declaring it `NonBlankStr` (`stack_fastapi_react.py:164`) and the
       frozen validation handler (`:315-326`);
     - a declared `success_status` is pinned in the route decorator, held by `status_code=` in the
       generated route (`:266`);
     - an error comes back as the frozen envelope `{"error": {"code", "message"}}` with the contract's
       status, held by the frozen error seam's source (`_envelope`, `:312`).
   - **Next.js declares two.**
     - **The value an optional field left out comes back as is not fixed:** it depends on the build.
       A criterion does not depend on it unless the change itself requires a value, and then the
       criterion states that value.
       - The evidence is on #1950 (comment of 2026-10-05). The proof is structural: the frozen types
         write `field?:`, the frozen store adds no default, and every route handler is a fill slot.
       - The corpus shows the consequence. Of the 225 distinct stored `POST /runs` handlers (402 files,
         corpus pin `c5c5ca6b…`), 187 leave the field out, 17 return `null`, 17 return `""`, and 4
         never handle it. All three representations occur in runs that completed.
       - Held by a test that the frozen types still write `field?:` and the store still adds no
         default. If the scaffold ever freezes a value, the test fails and the declaration changes
         with it.
     - **The frozen error envelope,** `{error: {code, message}}` through `errorResponse`, held to
       `_errors_source`'s bytes.
   - **Acceptance:**
     - each convention's byte test above;
     - a wiring test through the proposal handler's `handle()` for each stack finds that stack's
       conventions and no other's;
     - an unregistered stack gets no section.
3. **#1995: template-only.**
   - **The template** says the PRD delta states only what the manifest delta, criteria and footprint
     carry.
   - **Its example is the stored case:** `prop_450986544201` v1 stated a capacity display in run
     detail that no client-route change, criterion or footprint file carried. Version 2 narrowed the
     text and was approved.
   - **No rail, because the disagreement is in prose.** A deterministic predicate needs a typed link
     from each PRD delta item to the manifest entries and criteria that carry it. That is a change to
     the change request's schema (SIP-0109 §9), so it is a design change, not a 2.1 fix.
   - **Who catches it until then:** the supervisor reads every PRD delta through 2.1 (§3a). The typed
     link is recorded on #1708, because the auto tier (2.2) is when nobody reads them.
   - **Acceptance:** a wiring test through the proposal handler's `handle()` finds the rule and its
     example in the prompt sent.
4. **#1884, by the owner's rule (§5 ruling 13).**
   - **"Explicitly accepted" means:**
     - the approved change request (its criteria and its PRD delta);
     - the frozen criteria (their statements, stored beside each bundle since #1938);
     - the accepted PRD;
     - the accepted interface manifest.
   - **What changes beyond #1886,** which put a narrower rule in the criteria appendix for plan
     authors only. Each change names the component that makes it.
     - **One asset states the rule for every reader:** `request.increment_test_scope_appendix`
       (new). It carries:
       - the ruled rule;
       - its example: campaign 1 T1's tie order, a rule T1's statement never made, so it is
         proposed, not tested;
       - the approved criteria (id, statement, observable);
       - the frozen criteria's statements.

       #1886's section leaves `request.plan_increment_criteria_appendix` (v3), so the rule has
       one author. It covers any test in any file, not only "every test the plan asks for".
     - **One input key carries its data:** `increment_test_scope` =
       `{criteria: [{id, statement, observable}], frozen: [{criterion_id, statement}]}`.
       - It is composed from the approved change request and `campaign_proposal.frozen_criteria`,
         where each entry carries its statement since #1938.
       - It is present for every increment, with `criteria` empty for a `refactor`, and absent
         outside a campaign.
     - **Planning:** a new `INCREMENT_SURFACES` entry (`_plan_authoring.py:65`), whose index
       `_inject_increment_indexes` (`task_plan.py:657`) composes for every increment framing. The
       qa and dev proposers and the merger then see it whether or not the change has criteria.
     - **`qa.test`:**
       - a new context-contract property, `increment_test_scope`, on `ContextAssemblyContract`
         (`context_assembly.py:89`), declared on `TaskType.QA_TEST` (`:213`). `_increment_inputs`
         (`task_plan.py:760`) composes the key for an increment's implementation-run envelopes
         whose task type declares it: a property, not an identity check (CLAUDE.md's task-type
         rule 3);
       - `QATestHandler` renders the asset when the key is present;
       - a re-take re-dispatches the same envelope (`dispatched_flow_executor.py:186`), so it
         carries the key;
       - the retest (`_handle_retest`, `qa_test.py:1452`) generates nothing, and renders nothing.
     - **`qa.test_repair`:**
       - its envelope is built by the correction loop (`correction_repair.py:1021-1080`), which
         forwards the failed task's inputs only through a fixed key list and `REPAIR_PRESENCE_KEYS`
         (`context_assembly.py:466`, applied at `correction_repair.py:1058`). Without a change
         there, the repair never sees the rule;
       - `increment_test_scope` joins `REPAIR_PRESENCE_KEYS`. It is presence-keyed, so a repair
         outside a campaign carries none;
       - `QATestRepairHandler` renders the same asset through `_RepairPromptMixin`
         (`repair_handlers.py:253`) when the key is present.
     - **The proposal outlet,** specified below.
     - **Outside the rule's text: dev-role emissions.** The owner's rule names the QA author, and
       what a dev task may write is its SIP-0100 write grant, which this does not change.
   - **The outlet: who may emit it.** Only `qa.test` in an increment's implementation run.
     `qa.test_repair` is told the rule but not given the outlet. A repair re-authors a suite that was
     missing, unparseable or uncollectable, and proposing belongs to the authoring task. A block in a
     repair's emission is kept out of its artifacts and named in its evidence as ignored.
   - **The block's contract:** one fenced block whose header carries `proposed_behaviours.yaml`:

     ```yaml
     proposed_behaviours:          # a list of 1 to 10 entries; no other top-level key
       - behaviour: "..."          # required, non-blank: what the application should do, one sentence
         why: "..."                # required, non-blank: why it matters, one sentence
         surface_kind: endpoint    # required: endpoint | client_route
         surface: "GET /runs"      # required, non-blank: "METHOD /path", or a client route's path
     ```

     An unknown key, a missing or blank field, a `surface_kind` outside the two, or more than 10
     entries is malformed. The surface is not checked against the manifest: a proposal is judged
     later, by the proposer's rails.
   - **The parser and where it is stored.** `squadops.campaigns.proposed_behaviours` parses the
     block. `QATestHandler` calls it at the point it splits its emission into files, so the block is
     taken out before any file is extracted.
     - **Absent:** nothing is stored, and there is no row.
     - **Valid:** the handler returns one artifact, `proposed_behaviours.yaml`, of type
       `qa_proposed_behaviours`, holding the parsed entries. The executor stores it as it stores
       every artifact. Of the final emission only, so it is stored once per task execution.
     - **Malformed:** a blocking validation row carrying the parse error, so the self-evaluation
       pass returns it to the author inside the task's `max_self_eval_passes` (`cycle/base.py:1078`).
       If the passes run out with the block still malformed, the block alone is dropped. The task's
       evidence records why, and its verdict is decided by its tests as if the block were absent. An
       optional proposal never fails the task that wrote it.
   - **Never in a tree.** The allow-list (`delivered_tree.py:29`) already excludes the new type. The
     correction runner's deny-list (`correction_runner.py:1504`) gains it, or a retest would run it.
   - **The next proposal.** `_propose_launch` reads the stored entries of the cycle whose tree is
     accepted and, for a proposal that replaces an abandoned increment, of that increment's cycle.
     They go into the `campaign_proposal` block as `qa_proposed_behaviours`, deduplicated by
     `behaviour`, at most 10. The read is a function of stored data alone: a failed read raises, and
     the re-hearing retries it. `StrategyProposeIncrementHandler` renders them in a section of their
     own (a new asset, `request.proposal_qa_proposed_behaviours`). The supervisor reads them as the
     run's artifact.
   - **What stays with the author:** the judgement that a test invents a rule. No deterministic check
     can make it without guessing (#1884, comment of 2026-10-03), so it is measured, not gated.
   - **Acceptance, each failing on today's main:**
     - **planning:** a wiring test through the qa proposer's and the merger's real `handle()`, on a
       `refactor` increment's framing with no criteria, finds the rule and each frozen criterion's
       statement in the prompt sent. A framing outside a campaign finds neither;
     - **`qa.test`:** a wiring test builds an increment's implementation plan from
       `load_profile("campaign-increment")` defaults, with a stored change request and frozen
       criteria. It calls `QATestHandler.handle()` on the plan's `qa.test` envelope. The prompt sent
       carries the rule, each approved criterion's id, statement and observable, and each frozen
       criterion's statement;
     - **`qa.test_repair`, at both of its seams:**
       - **the forwarding:** a test drives the correction loop's repair dispatch for a failed
         increment `qa.test` whose locus is its own suite. It follows the pattern of
         `test_correction_runner.py::test_repair_envelopes_carry_failed_task_contract`. The captured
         repair envelope carries `increment_test_scope`, equal to the failed envelope's. A failed
         `qa.test` outside a campaign gives a repair envelope without the key;
       - **the render:** `QATestRepairHandler.handle()` on that captured envelope, with a stubbed
         emission that also carries a `proposed_behaviours.yaml` block. The prompt sent carries the
         rule, each approved criterion's id, statement and observable, and each frozen criterion's
         statement. The block is not among its artifacts, and its evidence names it ignored;
     - **no leakage:** `QATestHandler.handle()` on a `qa.test` envelope of a cycle outside a campaign
       renders none of it;
     - **the outlet, entered through each real handler:**
       - `QATestHandler.handle()` with a valid block returns exactly one `qa_proposed_behaviours`
         artifact holding each entry, and no `proposed_behaviours.yaml` among its workspace-typed
         artifacts;
       - the same handler with a malformed block, corrected on the self-evaluation pass: the pass's
         prompt carries the parse error, and the corrected block is stored once;
       - malformed on every pass: no proposal artifact, the evidence names the drop, and the task's
         verdict equals the same run's verdict without the block;
       - the executor stores the qa task's proposal artifact once, and `reexecute_repaired_suite`
         excludes it from the retest files;
       - `_propose_launch` with a stored proposal artifact on the accepted cycle puts its entries in
         the launch block. A vault read that fails raises, and with none there is no key;
       - `StrategyProposeIncrementHandler.handle()` renders the entries when the block carries them,
         and nothing when it does not;
     - **live, measured and not gated:** 2.1's shakeout repeats P9's read on every test file each
       increment's qa author wrote, and reports the unsupported rules per increment. The 2.0 set's two
       (campaign 1 T1's tie order, campaign 2 T4's non-mutation) are the comparison.

**Step 2: tooling and measurements, with no deploy.**
5. The SIP guards: #1969, then #1979, #1980, #1981, #1967 and #1968.
6. #1988 (3.12 targets, and mypy in CI as a ratchet at today's count), #1989 (the architecture
   overview and its guard), and #2008 (the reference cycle's capture).
7. The crew's tooling: #1956 (the four instruments under `scripts/dev/`, with tests), #1959 (the
   increment replay, as a script over the API) and #1960 (the per-increment scorecard, from the
   records).
8. The measurements, each posted on its issue with its numbers and query: #1911 (reasoning-only
   repairs), #1469 (the bundler-stderr corpus) and #1757 (the stored model-limitation rewinds).

**Step 3: defects batch 1, in §4's order** (if the night reaches it).
9. #1986 before #1940; #1984 before #1987; #1934 with #2007.
10. Then the rest: #1913, #1930, #1954, #1957, #1958, #1964, #1971, #1972, #1974, #1975, #1982
    and #1983.
11. Then a rebuild, the regression pair, and the `restart-at:at_proposal` diagnostic. The crew's
    first campaign is the crew's, and is not launched here.

**Stops (ruling 13):** a tag, a Release or any public upload; #316; a security finding; a red on main
that cannot be explained; anything reversing a ruling in §5; the crew's items. A stop is recorded and
left for the writeup, and the work moves on to the next item that does not depend on it.

**The writeup at 08:00 ET:** what merged, what closed, what was filed, what stopped and why, the
state of the box and of main, and what comes next. It is written at about 07:45 whatever state the
work is in, with a push notification when it is posted.

### The night's record (written 2026-10-05, in place of the 08:00 writeup)

**Merged, with main's whole run read green after each (17):** #2010 (this plan), #2011 (#1961), #2013
(#1962 with #1950), #2014 (#1995), #2012 and #2019 (#1884, in two parts), #2015 (#1968), #2016 (#1969),
#2017 (#1967), #2018 (#1981), #2021 (#1989), #2022 (#1979), #2023 (the portfolio's ruled deprecations,
Q14), #2024 (#2008), #2025 (#1956), #2026 (#1959) and #2030 (#1986). **So step 1 is complete; step 2 is
complete but for #1960 and #1988, both in open PRs; step 3 has #1986.**

**Open at the stop, every check green (12):** #2027 (#1960), #2031 (#1984), #2032 (#1980), #2033 (#1934
with #2007), #2034 (#1930), #2035 (#1982), #2036 (#1974), #2037 (#1975), #2038 (#1972), #2039 (#1958),
#2040 (#1957) and #2020 (#1988, which merges last). #1987's branch was pushed, built on #2031.

**Measured and posted (§7 item 8):**
- **#1911:** a capped reasoning-only generation is rare on live rounds: 3 of 469 runs, all `qa.test`
  rounds, none since 2026-09-23, and no dev correction repair recorded as capped. Whether the scoped
  prompt drives it is not readable, because an absent emission does not record its revision form. The
  replay of #1788's bundles remains, and recording the form is the instrument.
- **#1469:** one error repeated, blocked on #2028 (§2.1).
- **#1757:** all 7 of the stored `model_limitation` rewinds ended their run, so the ruled third anchor
  (§5 ruling 4) stands as ruled.

**Filed:** #2028 and #2029 overnight, and #2042 on the morning of 2026-10-05 (§2.10).

**The stop, and why.** At 02:08 ET the session ran `pytest tests/unit/capabilities` on #1983's
uncommitted first draft. A test mocked the subprocess, the draft's timeout path passed the mock's `pid`
to `os.killpg`, a mock's `pid` converts to 1, and `killpg(1)` is `kill(-1)`. Every process of the user
running the suite was killed: the SSH session, tmux, the session itself, the 07:50 writeup backstop, and
the Keycloak container, whose process runs under the same uid. A 07:58 resume did the same. Main and the
open PRs lost nothing, and the 08:00 writeup was not posted. The fix is #2043: the bounded-run helper
refuses such a target, and `tests/conftest.py` refuses it for every test run. It merges first on
2026-10-05, before the remaining conversions, whose tests also mock subprocesses.

**The box:** the 2.0.1 deploy, unchanged overnight. No rebuild ran.

### The first day's record (2026-10-05)

**Merged (22), main's whole run read green after each but the last:** #2043 and #2046 (#1983), #2044 (this
plan's rulings), #2031 (#1984), #2033 (#1934 with #2007), #2038 (#1972), #2035 (#1982), #2034 (#1930),
#2051 (#1987), #2036 (#1974), #2058 (#1964's inert recall port), #2037 (#1975), #2047 (#1940), #2048
(#2042), #2049 (#2029), #2050 (#1954), #2057 (#2045), #2052 (#1971), #2027 (#1960), and the rebuild's
tooling, #2064 (the tracked loaded checks) and #2065 (the restart diagnostics); then, during the pair,
#2032 (#1980), whose run is the one the Actions incident below holds. **So steps 1–3 are complete.**

**Rebuild 1** (§4 step 3), built from `bb7e16e0`; the checkout read `c814fb32`, which adds tooling and no
source. A backup was written first and every container's log saved.
- **Loaded:** all 26 tracked rows (`scripts/dev/loaded_checks.yaml`, #2064) answered with the new code.
  Each had been run against the merged tree, where it prints its expected line, and against the 2.0.1
  deploy, where it does not. Since #2064 a set records these rows and preflight refuses a deploy that
  answers otherwise.
- **The sandbox service** (`--profile sandbox`, which `all` skips) was rebuilt so #1982 reached it.
  Recreated, it refused to start: its token has no home in `.env` or `secrets/`, and the container it
  replaced had been started with one exported in a shell. It was restarted with a fresh token held in
  its environment only. The provider is `noop`, so no client calls it. This is #2006's twelfth
  credential (comment on #2006, built into #2069).
- **The regression pair, both accepted clean.** FastAPI+React `cyc_356895cd0440`: 21/21 criteria, zero
  correction rounds, the boot audit PASS, 50 min. Next.js `cyc_0dcd556f4fea`: 16/16, zero rounds, the
  boot audit PASS, 57 min. Both match the 2.0 baseline.
- **The restart diagnostics** run on campaign `cmp_fb99bbe417ad`, of one increment
  (`examples/03_group_run/campaigns/2-1-0-rebuild1-diag.yaml`):
  - `restart-at:at_proposal`, which reads #1934: the re-attach asks for the proposal task by its id,
    and the proposer answers from its stored reply;
  - `restart-queued-successor`, which reads #2042: a foreign model holds the box while the ruling's
    successor waits queued, the runtime restarts, and the successor must start once;
  - `duplicate-completion`;
  - every record reads #2007: no flow run of an ended run left open.

  Their records are written to `var/campaigns/cmp_fb99bbe417ad/diagnostics/`. **All three passed**, on
  rebuild 1's runtime image (`6c1a718c0bb3`):
  - `restart-at:at_proposal` (#1934): one proposal task dispatched before the restart and the same one
    after, answered from the store. The ledger held at 7 rows.
  - `restart-queued-successor` (#2042): `llama3.1:8b` held the box (66 GB free before, 43 GB loaded),
    the successor stayed queued through the restart, and it started once.
  - `duplicate-completion`: one continuation and one launch. The ledger held at 9 rows.
  - #2007: no flow run left open in any of the three.

  The first attempt timed out at its four-hour wait for `at_proposal` and injected nothing. The
  calibration gate below had held the campaign for about three of those hours. It was relaunched on the
  same campaign at 00:20Z and passed within four minutes.

**Batch 2 merged (steps 4 and 5), after the pair was read:** #2053 (#1757), #2054 (#1991), #2055 (#1911's
instrument), #2056 (#2028), #2059 (#1973), #2060 (#1796), #2061 (#1727 with #1913), #2066 (#1990) and
#2069 (#2006, the code; the Spark's own rotation waits for the owner). Also merged: #2040 (#1957) and
#2039 (#1958). #2039's guard caught the diagnostics definition's own comment, which named the deploy it was
written for, and it was reworded.

**Built and held:**

| batch | PRs |
|---|---|
| refactors (§4 step 6), each its own rebuild | #2063 (#1985), then #2067 (#414, rebased with the one `correction_budget` call #2055 added) |
| generation quality (§4 step 7, the final deploy) | #2070 (#1031), #2071 (#1692's remainder; SIP-0109 §24be) |
| tooling, last | #2020 (#1988) |

A trial merge of every held PR in order passed 12,576 tests before batch 2 merged. Its one interaction was
#2067's budget argument against #2055's new tests, which #2067's rebase added.

**Measured:**
- **#414:** the priority reserve replayed against the 106 stored runs with correction rounds. Two would
  have ended a round sooner. None lost a required repair to completeness rounds (SIP-0086 §12c).
- **#1031:** the error-status convention fires on 8 of 244 authored manifests. Every departure is the
  issue's class: `participant_not_found` answering 409, 422, 400 or 424, and `duplicate_participant`
  answering 400. It lands advisory (#820).
- **#567:** 7,468 stored emissions replayed through CommonMark fence recognition. It truncates 426 of
  9,605 files, and moves or drops about 80 more. The parser's two departures from the spec are rulings,
  #430's nesting and #431's end-of-file recovery. Recommended not built (comment on #567); **the owner's
  to rule**.

**Filed:** #2068. The console's service client has no realm client and no secret, so its command
handlers call the runtime API unauthenticated. The API refuses those calls, so nothing is exposed, but
the console's commands do not work.

**Paused, then resumed:** merges stopped from 19:20Z for GitHub's Actions incident ("delays in assigning
GitHub-hosted runners"). The run on #2032's merge held one job that never got a runner, cancelled twice. Actions
recovered at 21:55Z. The job was re-run green, and merging resumed.

**Main's dependency audit went red after 59505573:** an external advisory published against a locked
package, `python-jose` 3.5.0 (GHSA-3qf3-8w2g-rqmx). No fix version exists, and no merge introduced it. The
owner approved two steps:
- **#2074:** the advisory is accepted with its reason, because the one verifier pins `algorithms=["RS256"]`
  and takes RSA keys from the JWKS. Reproduced locally, the forgery verifies only when HS256 is allowed. A
  test forges the advisory's token against a real key set and fails if the restriction loosens. A second
  advisory published while it ran, multidict 6.7.1 (GHSA-54p9-h82j-f925), has a fix, so it moves to 6.9.1.
- **#2075 (#2073):** python-jose is retired and the verifier moves to PyJWT, riding rebuild 2. The
  adapter's tests now sign real tokens, and the old behaviour's 27 pass on both libraries. PyJWT refuses
  three tokens python-jose accepted (no `aud`, no `kid`, an `iat` beyond the skew ahead). None comes from
  the deploy's clients. ADR §15, "`jose` over `PyJWT`", is amended with the evidence.

**Held at a gate, then decided:** the diagnostics campaign's calibration framing stopped at
`progress_plan_review` on an `unresolved: true` manifest question: the PRD states no page size for the runs
list. It was escalated, and the owner ruled it is not theirs: an unresolved question on an uncounted run is
the operator's. It was approved at 00:01Z with the manifest's unbounded list (MVP scale). Rebuild 2 runs
after the campaign completes.

**For the owner:**
- #2006: the rotation, a backup first (`docs/ops/credential_rotation.md`). Rotate Langfuse's `SALT`?
  Realm users as a follow-on?
- #567: not built?
- #1824: option 1 with the producer, or option 2?
- #1937: the reporting-only lint, or 2.3?
