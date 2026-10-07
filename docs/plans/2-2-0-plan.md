# 2.2.0 plan — Cross-Cycle Memory Phase 1: reviewed lessons from earlier campaigns, measured before the cut

**Status: DRAFT (2026-10-06), revised the same day, for the owner's review in the same PR as SIP-0110's
acceptance.**

**The first draft** was written while the 2.1 cut was being prepared: the final deploy built, its
diagnostics running, its set waiting for registration (#2090).

**The revision adopts two things:**
- **An external design review** of SIP-0110 revision 4 and of the first draft. It is now SIP-0110 revision 5:
  §0 is the normative Phase-1 contract, and §5c records the change.
- **The owner's choice of release shape B** ("go with B"): 2.2.0's cut waits for the bounded measurement
  window's finding (§3).

**The 2.1 cut's two open sections are now read (2026-10-07):**
- **the cut's findings** (§2.4) were all fixed within 2.1, and none is placed here;
- **#1964's cut readings** are in SIP-0110 §5b and do not change the re-read's finding. The whole 2.1 line returned no
  proposal, so the corpus is built by 2.2's own campaigns.

**This PR changes prose only.** It merges before the 2.1 set registers or after the 2.1 cut, and never while
the set is open (#2090 §7).

**What 2.2 is.** An even minor, a feature release (CLAUDE.md, #281), led by one headline: **SIP-0110 Phase 1**,
the line's one change to what the squad generates (`sips/PORTFOLIO.md` Q2).

**Beside it: #1708's auto tier and escalation queue.** They change who decides a gate, not what the squad
generates. Decisions shape later application state, prompts and failures, though, so the tier's activation is
held outside the measurement window (D3). Hardening rides along.

**The question it answers:**

> **When the proposer is supplied reviewed lessons from earlier campaigns' proposal returns, does a named
> defect recur less in later proposals, measured by replay against today's prompt, without degrading the
> proposals? And can plan reviews be decided under a declared policy while the owner is away, escalating
> everything the policy does not cover?**

**What Phase 1 is, precisely** (SIP-0110 §0.1):
- **cross-campaign learning, with lessons written by people;**
- observations are recorded while a campaign runs, but new guidance never activates within it;
- the owner approves a lesson, and it reaches campaigns admitted afterwards;
- correction within a proposal stays SIP-0109 §9.2's revision note.

**Why the headline is shaped this way.** The memory SIP was written for the plan gate. 2.1's re-read (SIP-0110 §5b)
found that gate dormant: no framing re-rolls in 36 framings, and every plan review approved. The recurrence that is
live is at the campaign's proposal gate:
- **6 of 22 increment rulings were returned.**
- **One behavior recurred in three campaigns:** a new criterion already satisfied by the accepted application.
- **It recurred after a prompt rule (#1947),** and again after the proposer was shown the return.

So the headline is a measurement, not an expected win.

**The corpus is small.** The target behavior has about three independent historical cases, none captured before
authoring. The test corpus is built by the 2.2 line's own campaigns, and **"inconclusive" is a likely and legitimate
finding** (SIP-0110 §0.13).

---

## 1. The open issues, every one placed

26 issues are open on 2026-10-07, counting the four Phase-1 slices (#2096, #2105–#2107). #1964 closes with this PR.

| where | count | issues |
|---|---|---|
| **2.2: the headline** | 4 | #2105 (slice 1: capture and the source-case inspection), #2106 (slice 2: the replay), #2096 (slice 3: the mechanism), #2107 (slice 4: the template and the measurement window) |
| **2.2: beside it** | 1 | #1708's remainder: the auto tier and the escalation queue (placed 2026-10-03, 2.0 plan rev 9 §5a.5; kept 2026-10-04, Q2) |
| **2.2: hardening, placed by the owner during the 2.1 line** | 3 | #2079 (the realm's admin password), #2082 (two console test files depend on their order), #2083 (the realm sync never applies a service account's roles) |
| **2.1's, read at its cut** | 3 | #1964 (closed by this PR: the cut's readings are SIP-0110 §5b's last part). #1911 and #1469 carry, each waiting on its evidence: #1911 on its replay of #1788's bundles, and #1469 on a failing build of a second module shape (the cut window had none) |
| **2.3** | 6 | #316 (the owner, 2026-10-06: "2.3 is fine just let's not forget about it"), #1976, #1977, #1992, #1993, #1994 |
| **2.3, recommended here** (§4, D6) | 1 | #2062 (hoisting #1985's deferred imports: 606 import sites, a structural change for the stabilization line, next to #1992's move) |
| **2.4 or later** | 4 | #1966, #557, #949, #950 (they follow Outcome Evaluation, Q2) |
| **2.6** | 1 | #1978 |
| **the crew's** | 2 | #1756, #1965 |
| **rides any release** | 1 | #1039 |

---

## 2. The work

### 2.1 The headline: SIP-0110 Phase 1, in four slices

**Built to SIP-0110 §0.** Every part ships inert until the owner approves a pattern. Only an approved revision in
a campaign's pinned snapshot is supplied (§0.6–§0.7), so building the parts does not move the regression baseline.

| slice | what | the seam that owns it | size | deploy |
|---|---|---|---|---|
| 1, #2105 | the source-case inspection, then a `ProposalReplayEnvelope` captured immediately before `strategy.propose_increment`, complete beyond #1756's 10,000-character cut (§0.11) | the proposal handler's input assembly (`capabilities/handlers/planning/proposal.py`); the vault for storage | M | yes |
| 2, #2106 | the proposal replay: three arms over captured inputs, temporal validity, isolation from production memory, one fixed rubric (§0.11–§0.12) | `scripts/dev/`, beside the increment replay (#1959) | M | no |
| 3, #2096 | the mechanism (§0.2–§0.10). Its parts are listed below | see the parts | L | yes |
| 4, #2107 | the template for the one target behavior, written on development cases; the pre-registration; the window; the finding (§0.4, §0.12–§0.13) | `src/squadops/prompts/fragments/` for the template; `docs/plans/` for the pre-registration | M, plus the window's box time | yes |

**Slice 3's parts, each with the seam that owns it:**
- observations, pattern revisions, approvals and exposures, in `src/squadops/memory/models.py`;
- the idempotent projection from the campaign control log, through the campaign domain;
- the classification-disposition rail (D2), with its SIP-0109 amendment;
- the campaign snapshot pinned at admission;
- the recall policy behind `FailurePatternRecallPort` (`src/squadops/ports/memory/recall.py`, #2058), with the
  LanceDB adapter (`adapters/memory/lancedb.py`) and its factory;
- injection into `strategy.propose_increment` in its own slot (`capabilities/context_assembly.py`);
- per-exposure assessment;
- approval and revocation.

**Renamed when touched:** three docstrings and a comment name the draft (`SIP-Cross-Cycle-Memory §5`):
- `src/squadops/memory/recall.py`;
- `src/squadops/ports/memory/recall.py`;
- `src/squadops/cycles/task_plan.py`;
- `adapters/cycles/run_provisioning.py`.

They are left in this PR so that it stays prose only and the 2.1 tree does not move.

**Slice 1 comes first,** for two reasons:
- **The inspection may show the information was on screen.** Version 2's return said "the manifest above already
  declares capacity", so the failure may be reasoning, not access. That changes what the template should say. An
  evidence-access gap, if found, is fixed as a separate change, held identical across the arms.
- **Every campaign after the capture ships adds faithful cases** to the corpus the window needs.

### 2.2 Beside it: #1708's auto tier and escalation queue

**The authority comes from a declared policy,** settled in a SIP-0109 amendment. Thirty-six approvals in thirty-six
plan reviews do not show that review can be removed: the same evidence shows those reviews answering design
questions. Historical approval rates inform the policy; they never grant authority. An automatic decision needs:
- the gate kind and action the policy permits;
- the objective's and resources' bounds;
- the evidence it requires;
- no unresolved owner or product decision, unless an authoritative decision already resolves it;
- explicit escalation conditions.

The decider is recorded on the gate decision.

**2.2's tier covers plan reviews only (D3, D4).** #1995's typed link from each PRD-delta item to what carries it is
necessary for proposal auto-approval and not sufficient. Proposal auto-approval would also need checks for:
- unsupported added scope;
- omitted obligations;
- already-satisfied criteria;
- exact accepted-state references;
- evidence that the stated behavior is carried by the artifacts;
- an explicit "cannot establish" that escalates.

Those checks do not exist, so proposal rulings stay with the supervisor in 2.2. After any automation, an assessed
sample or holdout stays independent, and auto-approved, unassessed work is never memory feedback.

**The escalation queue's contract,** designed in the same amendment:
- an escalation's identity is tied to the objective, campaign, gate, proposal revision and accepted baseline;
- its states are pending, resolved, expired, cancelled and superseded;
- creation and resolution are idempotent, and the digest's delivery survives a restart;
- a stale approval never authorizes a changed proposal;
- the campaign continues only with independently eligible work, and work that depends on a parked increment waits;
- repeated escalation, reproposal, retries and resources are bounded;
- a campaign whose every available increment needs the owner ends with completed and unresolved work kept distinct;
- the answer to an owner's late response, after the campaign closed, is defined;
- silence is never approval, and a parked problem is never regenerated in a loop.

**The purity boundary** (SIP-0110 §7, §0.8): the continuation decision never queries mutable memory. It may consume
ordinary evidence from memory-informed proposals.

### 2.3 Hardening placed by the owner

| issue | the defect | the fix | size | deploy |
|---|---|---|---|---|
| #2079 | the realm's `squadops-admin` signs in with the password every realm file commits; #2006 left the realm's human users out | generate it per deploy, as #2006 does for service credentials, and rotate it with the same runbook (`docs/ops/credential_rotation.md`) | S | yes |
| #2082 | `test_cycle_command_handlers.py` stubs `auth_bff` in `sys.modules`, and `test_auth_bff.py` imports the real one, so the pair fails 5 tests in one order | one fixture that owns the module for both files and restores its prior state | S | no |
| #2083 | the realm sync's `partialImport` leaves out `users`, so a service account added after a realm was created never gets its realm roles | apply each service account's roles from the export, repeatably, without importing human users | S | yes |

Each issue carries its acceptance criteria (posted 2026-10-06).

**`docker-compose.yml`:** the owner's exception was for the 2.1 line (2.1 plan §5 ruling 13). A 2.2 item that needs a
compose change asks first.

### 2.4 From the 2.1 cut (open)

The cut found four defects, and each was fixed within 2.1, so none is placed here:
- #2094: a refused run could not leave `queued`;
- #2099: the rotation's `.env` copy was not ignored by git;
- #2101: the retry rows were asked after the blocked rows (SIP-0109 §24bh);
- #2103: LangFuse's health check.

The counted set passed 4 of 4 (the 2.1 pre-registration §10).

### 2.5 Not in 2.2 (ruled)

- **#557, #949 and #950** follow Outcome Evaluation's scenarios, in 2.4 or later (Q2).
- **The recurring design questions** (7 of 8 unresolved questions asked how the runs list is ordered or paged) are
  decision records. They are the Design Decision Register's payload, and arrive with its home, #950 (SIP-0110 §5b,
  Q12).
- **Phase 1.5** (the correction lane), **Phase 2**, semantic ranking, LLM-generated lessons, autonomous promotion and
  the other deferrals of SIP-0110 §0.14 stay unplaced. Phase 2 begins only on the owner's ruling after the window's
  finding.
- **Proposal auto-approval** (§2.2).
- **#316** is 2.3's (2.1 plan §5 ruling 14).

---

## 3. Sequencing (shape B: the cut waits for the window)

1. **Inherit the 2.1 cut's findings** (§2.4). They are live evidence.
2. **Rule before building:**
   - this PR (SIP-0110 revision 5 and this plan);
   - the SIP-0109 amendments for D2's rail and for #1708's policy and queue.
3. **Slice 1 (#2105):**
   - the source-case inspection, posted;
   - pre-proposal capture, proven live by a byte-exact reconstruction of a real proposal's prompt.
4. **Hardening:**
   - #2082 (tooling, no deploy);
   - then #2079 and #2083 together, since both are the realm's, with a rebuild and the regression pair.
5. **Slice 3 (#2096),** inert, with the acceptance matrix (SIP-0110 §0.15) held on a controlled corpus. A rebuild
   and the regression pair follow. Nothing is supplied, because nothing is approved.
6. **Slice 2 (#2106):** the replay, proven end to end on the historical cases, which are exploratory and diagnostic
   only.
7. **#1708** is built, and its activation is held until the window closes (D3).
8. **Slice 4 (#2107):** the template on development cases, then the pre-registration with its budget cap and
   stopping rule (D8). Then **the window opens**:
   - the deploy is frozen;
   - campaigns build the captured corpus;
   - the owner approves the pattern at a campaign boundary;
   - the replay compares the arms;
   - **main is closed to code merges.** Prose merges stay free, because the drift check reads only `src/` and
     `adapters/`.
   - 2.3's work waits on branches: its refactors need rebuild pairs, and the box is held.
9. **The finding** is recorded in SIP-0110: instrument validity first, then benefit, no benefit, harm or
   inconclusive. The owner's disposition for Phase 2 is recorded with it. "Inconclusive" at the budget cap is a
   valid finding, and the cut goes ahead on it.
10. **#1708's plan-review tier is activated** under its declared policy, and validated by the cut's shakeout.
11. **The cut:**
    - a regression set on both stacks;
    - one campaign shakeout;
    - the release cut procedure (CLAUDE.md);
    - a record that states separately the mechanism's correctness, the experiment's validity and result, the
      activated patterns and their applicability, the auto-gate scope enabled, and the owner's disposition for the
      next phase.

### The cut's criteria

- **The mechanism:** SIP-0110 §0.15's acceptance matrix holds, and an empty or unapproved snapshot leaves the
  rendered prompt byte-identical.
- **The instrument:** valid, by #2106's validity check.
- **The finding:** recorded, whichever of the four. **A benefit is not a cut criterion.**
- **#1708:** its tier escalates every case its policy does not cover, read in the shakeout.
- **The regression set:** passes, under its own pre-registration.

---

## 4. Decisions for the owner

Each has a recommendation. None is built before it is ruled.

| # | decision | recommendation | why |
|---|---|---|---|
| — | **the release shape** | **decided: B** (the owner, 2026-10-06: "go with B") | the cut waits for the bounded window's finding |
| D1 | **the instrument** | **proposal replay, conditional on slice 1's verified pre-authoring fidelity** | replay runs identical inputs under each arm. The boundary is immediately before authoring, never "at the ruling": later rulings and notes reveal what the author did not have |
| D2 | **a return's classification disposition** | **a `ProposalClassification` class or an explicit `unclassified` with rationale; a return with neither is refused** (a SIP-0109 rail and amendment) | 3 of the 6 historical returns carry their class only in prose. A novel defect must stay returnable without being forced into a wrong class |
| D3 | **memory and the auto tier, in order** | **proposal rulings stay supervised through the window. #1708's tier covers plan reviews, under its declared policy, activated after the window** | the window's evidence comes from the supervisor's classified rulings. A tier active during it would change the cases it measures |
| D4 | **#1995's typed link** | **a prerequisite for proposal auto-approval, never its authorization. No proposal auto-approval in 2.2** | §2.2's further checks do not exist |
| D5 | **this plan** | adopt as revised, or amend | — |
| D6 | **#2062** | **2.3,** with the structure batch | 606 import sites move for no behaviour, and #1992's move rewrites many of the same imports |
| D7 | **snapshot and activation semantics** | **as SIP-0110 §0.7:** pinned at admission; changes reach campaigns admitted later; concurrent campaigns keep their own | otherwise a confidence or status update changes the next prompt mid-campaign, and the comparison moves under itself |
| D8 | **the experiment's arms and the window's bound** | **as SIP-0110 §0.12–§0.13,** with the budget cap set in the pre-registration. A proposed default: about five campaigns, with "inconclusive" at the cap | a bounded window cannot hold the release open indefinitely |
| D9 | **emergency revocation** | **as SIP-0110 §0.7:** halt or restart the affected work under a new snapshot, and invalidate or set apart the affected measurements | harmful guidance must be removable without silently changing a counted intervention |
| D10 | **the escalation queue's resumption** | **designed in #1708's SIP-0109 amendment against §2.2's contract** | it is SIP-0109's surface (SIP-0110 §0.14) |

---

## 5. What this plan does not decide

- **The 2.1 cut's findings** (§2.4) and **#1964's cut readings** (SIP-0110 §5b).
- **The cut's numbers:** the regression set's size, and the window's N, budget cap and minimum worthwhile effect.
  They are written as pre-registrations when their batches are built.
- **The standing authority for 2.2.** The owner's grant of 2026-10-04 covers the 2.1 line. 2.2's authority is the
  owner's to give when this plan is adopted.
- **Any compose change** (§2.3).
