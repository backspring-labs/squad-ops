# 2.1.0 plan — hardening after Campaign: close the debt 2.0 deferred, no new capability

**Status: ADOPTED (2026-10-04), written while the 2.0 counted set ran.** The owner agreed the
recommendations in §5: "go ahead, record them and file the three issues". They are recorded there as
rulings, and §3's three issues are filed (#1956, #1957, #1958). The plan merges after the set closes,
since nothing merges while it is open (#1908 §7). Every issue it names was read in full, and its
placement is quoted from the issue.

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
2.4.

---

## 1. The open issues, every one placed

28 issues were open on 2026-10-04.

| where | count | issues |
|---|---|---|
| **closed at the 2.0 cut** | 4 | #1710 (the package renderings, after the set), #1711 (the runbook, after the set), #1884 (closed when the set reads P9), #1941 (closed by #1953) |
| **features: 2.2 or later** | 4 | #557 (a post-retest governance review: a new LLM step, its SIP drafted), #949 (a revision boundary derived from the note), #950 (a review packet at the plan gate), #1708's remainder (the auto tier and the escalation queue) |
| **2.1: hardening** | 17 | §2 below |
| **2.1: the owner's scope request** | 1 | #1940, kept in 2.1 (§5) |
| **the crew's, listed in 2.1** | 1 | #1756 (the owner's ruling, 2026-10-03: not to be built outside the crew) |
| **out of 2.1's committed scope** | 1 | #1039 (the docs site's design pass; it rides any release, §5) |

**So 2.1 closes 18 of the 24 that stay open after the 2.0 cut** (17 hardening and #1940), **plus
six new issues: 24 in all.** Three are §3's gaps, two are the crew's enablers, and #1964 is the
memory SIP's 2.1 part (§2.6). (§3's are #1956, #1957, #1958; the crew's enablers, §2.0, are #1959 and #1960.) #1756 is the
crew's, and #1039 rides any release. That count does
not include what the 2.0 set itself will find.

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
| #1940 | **authority to dispatch.** Only `admin` holds `campaigns:control` (create, start, resume, abort). `campaign-supervisor` can read and rule, not launch. Without it the owner launches every campaign, and the IDEA's first acceptance criterion fails | S | yes |
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
2. **The crew's tooling and the instruments, before anything they would measure:**
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
     changes behaviour.

   Then a rebuild, the regression pair, and the overlapping recovery diagnostics
   (`restart-at:at_proposal` for #1934). **The crew's first campaign can run on this deploy** (§2.0).
4. **The ruled answers:** #1757 (the third rewind anchor) and #1727 (§20 on the re-take path, read
   with #1913). Each becomes a SIP amendment in the PR that implements it.
5. **Verification gaps:** #1796, #1937 (reporting-only), #1824's attribution locus, and #1469's
   per-module elements, with a rebuild and the regression pair.
6. **Refactors, one per batch, each with its replay proof:** #414, then #567, then #316 (after its SIP
   is accepted). Each gets a rebuild and the regression pair before the next begins.
7. **Generation quality:** #1031 and #1692's remainder. These change what the model is shown, so they
   go last and are read on the cut's evidence, not mixed into a refactor's batch.
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

## 6. What this plan does not decide

- **The 2.0 set's own findings:** inherited at the cut, placed then.
- **The cut criteria's exact numbers** (the regression set's size, the shakeout's exit rule): written as
  the pre-registration when 2.1's last batch is built, as 1.9 and 2.0 did.
- **2.2's scope:** Cross-Cycle Memory, the gate loosening (#949, #950, #1708's remainder, decided from
  the 2.0 proposal ledger), and #557.
