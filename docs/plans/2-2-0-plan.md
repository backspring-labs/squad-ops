# 2.2.0 plan — Cross-Cycle Memory: a campaign learns from its returned proposals, and its gates run within scope

**Status: DRAFT (2026-10-06), for the owner's review in the same PR as SIP-0110's acceptance.** It was
written while the 2.1 cut was being prepared: the final deploy is built, its diagnostics are running,
and its set waits for registration (#2090). Two sections stay open until the cut:
- **the cut's findings** (§2.4), placed when they are found;
- **#1964's cut readings,** which are added to SIP-0110 §5b. If they change the re-read's finding, this
  plan is amended before 2.2's first build.

This PR changes prose only. It merges before the 2.1 set registers or after the 2.1 cut, and never
while the set is open (#2090 §7).

**What 2.2 is.** An even minor, a feature release (CLAUDE.md, #281), led by one headline: **SIP-0110
Phase 1**, the line's only change to squad behaviour (`sips/PORTFOLIO.md` Q2). Beside it is **#1708's
auto tier and escalation queue**, which change the control plane, not what the squad generates.
Hardening rides along.

**The question it answers:**

> **When the proposer is shown the classes a supervisor returned in earlier campaigns, do those classes
> recur less? And can a campaign's gates be decided within scope while the owner is away, without
> hiding the evidence that question needs?**

**Why the headline changed shape.** The memory SIP was written for the plan gate. 2.1's re-read
(SIP-0110 §5b, accepted with it) found the plan gate dormant: no framing re-rolls in 36 framings, and
every plan review approved. The recurrence that is live is at the campaign's proposal gate. There, 6 of
22 increment rulings were returned, and one class, a criterion the accepted app already satisfies,
recurred in three campaigns. It recurred after a prompt rule (#1947), and again after the proposer was
shown the return (SIP-0109 §9.2). So the headline is a measurement, not an expected win. If memory does
not lower that recurrence, the record says so, and Phase 2 does not begin (SIP-0110 §8).

---

## 1. The open issues, every one placed

23 issues are open on 2026-10-06, counting #2096, which this PR's SIP acceptance opened.

| where | count | issues |
|---|---|---|
| **2.2: the headline** | 1 | #2096 (SIP-0110 Phase 1 on the proposal gate, built and measured) |
| **2.2: beside it** | 1 | #1708's remainder: the auto tier and the escalation queue (placed 2026-10-03, 2.0 plan rev 9 §5a.5; kept 2026-10-04, Q2) |
| **2.2: hardening, placed by the owner during the 2.1 line** | 3 | #2079 (the realm's admin password), #2082 (two console test files depend on their order), #2083 (the realm sync never applies a service account's roles) |
| **2.1's, read at its cut** | 3 | #1964 (the re-read's cut readings), #1911 (the replay of #1788's bundles remains), #1469 (placed again once #2028's records hold failing builds of more than one shape) |
| **2.3** | 6 | #316 (the owner, 2026-10-06: "2.3 is fine just let's not forget about it"), #1976, #1977, #1992, #1993, #1994 |
| **2.3, recommended here** (§4, D6) | 1 | #2062 (hoisting #1985's deferred imports: 606 import sites, a structural change for the stabilization line, next to #1992's move) |
| **2.4 or later** | 4 | #1966, #557, #949, #950 (they follow Outcome Evaluation, Q2) |
| **2.6** | 1 | #1978 |
| **the crew's** | 2 | #1756, #1965 |
| **rides any release** | 1 | #1039 |

---

## 2. The work

### 2.1 The headline: SIP-0110 Phase 1 on the proposal gate (#2096)

Rails before mechanism. Every part below ships inert until the owner promotes a pattern. Only
`promoted` patterns inject into counted cycles (SIP-0110 §5a governance). So building the parts does not
move the regression baseline. Promoting a pattern does, and promotion lands between campaigns, with a
calibration cycle before and after it (SIP-0109 #1709).

| part | where it lands (the seam that owns it) | size | deploy |
|---|---|---|---|
| the typed `ReflectiveFailurePattern`, serialized into `MemoryEntry` (§5, §5a's origin model) | `src/squadops/memory/models.py` | M | yes |
| the real recall adapter behind `FailurePatternRecallPort`, selected by a factory with a required selector, and verified against LanceDB on its own corpus first (§5a) | `src/squadops/ports/memory/recall.py` (the port, from #2058); `adapters/memory/lancedb.py` and `adapters/memory/factory.py`; the composition roots | M | yes |
| one governed template per `ProposalClassification` class (five), reviewed as prompt content (#448). A class with no template is disclosed, and so is a return with no class | `src/squadops/prompts/fragments/` | S | yes |
| encode at the ruling: a classified return becomes one `validated` pattern (§5b) | the `classify` operation's path (`src/squadops/api/routes/campaigns/campaigns.py`, `classify_proposal`) through the campaign domain, not the route | M | yes |
| recall into `strategy.propose_increment`, through a managed fragment and its own slot, separate from §9.2's revision note | `src/squadops/capabilities/context_assembly.py` (the task type's contract); `handlers/planning/proposal.py` | S | yes |
| feedback and decay from the next ruling (§5) | beside the encode | S | yes |
| promotion by the owner, recorded | the campaign control plane (an owner operation) | S | yes |
| the instrument (§4, D1) and the measurement window, pre-registered | `scripts/dev/` and a pre-registration in `docs/plans/` | M | no |

**Renamed when touched:** three docstrings and a comment name the draft (`SIP-Cross-Cycle-Memory §5`):
`src/squadops/memory/recall.py`, `src/squadops/ports/memory/recall.py`, `src/squadops/cycles/task_plan.py`
and `adapters/cycles/run_provisioning.py`. They are left in this PR so that it stays prose only and the
2.1 tree does not move.

### 2.2 Beside it: #1708's auto tier and escalation queue

The shape #1708 settles in a SIP-0109 amendment:
- **Auto-decided within the objective's allowed scope,** by a declared policy, with the decider recorded
  on the gate decision.
- **An escalation queues and never blocks the box.** An out-of-scope or owner-reserved decision parks
  its increment, and the campaign continues with another or ends cleanly. The queue lands in the morning
  digest.
- **No gate waits without bound.** 2.0 built the bound (#1918, §24aj).

**Its scope is decided from the ledgers** (2.0 plan rev 9, decision 4). The ledgers say:
- **Plan reviews:** 36 of 36 approved in the re-read's window.
- **Increment rulings:** 6 of 22 returned.

**Two constraints from this line:**
- **#1995's precondition** (on #1708, 2026-10-05). A proposal's PRD delta can state more than its
  manifest delta, criteria and footprint carry, and only a reader catches that. An auto tier that
  approves proposals needs a typed link from each PRD-delta item to what carries it, or an equivalent
  check.
- **Memory's evidence.** A proposal the auto tier approves is never classified, so a class the
  supervisor would have returned goes unobserved (SIP-0110 §5b). §4, D3 sequences the two.

### 2.3 Hardening placed by the owner

| issue | the defect | the fix | size | deploy |
|---|---|---|---|---|
| #2079 | the realm's `squadops-admin` signs in with the password every realm file commits; #2006 left the realm's human users out | generate it per deploy, as #2006 does for service credentials, and rotate it with the same runbook (`docs/ops/credential_rotation.md`) | S | yes |
| #2082 | `test_cycle_command_handlers.py` stubs `auth_bff` in `sys.modules`, and `test_auth_bff.py` imports the real one, so the pair fails 5 tests in one order | one fixture that owns the module for both files | S | no |
| #2083 | the realm sync's `partialImport` leaves out `users`, so a service account added after a realm was created never gets its realm roles | apply each service account's roles from the export, without importing human users | S | yes |

**`docker-compose.yml`:** the owner's exception was for the 2.1 line (2.1 plan §5 ruling 13). A 2.2
item that needs a compose change asks first.

### 2.4 From the 2.1 cut (open)

Left open on purpose. The findings of the cut's set, its shakeout and its diagnostics are placed here
when they are found.

### 2.5 Not in 2.2 (ruled)

- **#557, #949 and #950** follow Outcome Evaluation's scenarios, in 2.4 or later (Q2).
- **The recurring design questions** (7 of 8 unresolved questions asked how the runs list is ordered or
  paged) are decision records, the Design Decision Register's payload, and they arrive with its home,
  #950 (SIP-0110 §5b, Q12).
- **Phase 1.5** (the correction lane) and **Phase 2** stay unplaced. Both are gated on Phase 1's
  measurement (SIP-0110 §8).
- **#316** is 2.3's (2.1 plan §5 ruling 14).

---

## 3. Sequencing

1. **Inherit the 2.1 cut's findings** (§2.4). They are live evidence.
2. **Rule before building:** the SIP-0109 amendment for #1708's tier and queue, and decisions D1 to D4
   (§4). Each becomes an amendment in the PR that implements it.
3. **Hardening:**
   - #2082 (tooling, no deploy);
   - then #2079 and #2083 together, since both are the realm's, with a rebuild.
4. **Memory's rails,** inert:
   - the typed pattern and the adapter, with the adapter's recall verified on its own corpus;
   - the five templates, reviewed;
   - encode at the ruling, recall into the proposal task, and feedback.

   A rebuild and the regression pair follow. Nothing injects, because nothing is promoted.
5. **The instrument** (D1), then **the measurement window's pre-registration:** N declared before
   rolling, the memory-off arm first, and then the owner promotes the pattern.
6. **#1708's auto tier and queue,** in the order D3 sets. Its auto-decided scope comes from the ledgers.
7. **The cut:**
   - a regression set on both stacks;
   - one campaign shakeout;
   - memory's measurement read and recorded as a SIP-0110 amendment, which decides whether Phase 2
     begins;
   - #1708's record.

---

## 4. Decisions for the owner

Each has a recommendation. None is built before it is ruled.

| # | decision | recommendation | why |
|---|---|---|---|
| D1 | **the instrument:** a proposal-run replay with and without a pattern, or live campaigns only | **build the replay, as Phase 1's first slice** | Six returns in one window is too few to measure live within one release. A replay runs the same stored inputs memory-on and memory-off. **Unverified:** the proposal task's inputs must be rebuilt from the campaign's state at the ruling, as #1959 rebuilds an increment's seeds, because a stored prompt is cut at 10,000 characters (#1756) |
| D2 | **a return must carry a class** | **yes: a return with no `ProposalClassification` is refused**, a SIP-0109 rail and amendment | 3 of the 6 returns carry their class only in prose, and Phase 1 encodes typed classes only. Without a rail, the corpus thins without anyone seeing it |
| D3 | **memory and the auto tier, in order** | **the auto tier takes plan reviews first.** Increment rulings stay with the supervisor until memory's measurement window closes | Plan reviews were 36 of 36 approved, and increment rulings are where the returns are. Auto-deciding them during the window would remove the evidence the window measures |
| D4 | **#1995's precondition** | **required before the auto tier decides any increment ruling,** and not needed for plan reviews | It is the check a supervisor's reading supplies today |
| D5 | **this plan** | adopt as drafted, or amend | — |
| D6 | **#2062** | **2.3,** with the structure batch | 606 import sites move for no behaviour. It is the odd line's kind of change, and #1992's move rewrites many of the same imports |

---

## 5. What this plan does not decide

- **The 2.1 cut's findings** (§2.4) and **#1964's cut readings** (SIP-0110 §5b).
- **The cut's criteria** (the regression set's size and the measurement window's N). They are written
  as pre-registrations when their batches are built.
- **The standing authority for 2.2.** The owner's grant of 2026-10-04 covers the 2.1 line. 2.2's
  authority is the owner's to give when this plan is adopted.
- **Any compose change** (§2.3).
