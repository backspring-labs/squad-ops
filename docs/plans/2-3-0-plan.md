# 2.3.0 plan — a faster engine first, then the structure: TensorFold to a decision, and stabilization on the engine that ships

**Status: DRAFT (2026-10-11), for the owner's ruling (§5).** It was drafted while 2.2.1's diagnostic ran, at the
owner's request: "I want to prioritize the TensorFold adapter to get shorter cycle times". It assumes 2.2.1 cuts as its
plan says. Nothing here starts before that cut.

**What 2.3 is.** An odd minor: a stabilization release, feature-free by rule (CLAUDE.md, #281). One track rides it
under a waiver the owner already granted: **SIP-0111's TensorFold trial**, dark, under SIP-0106 §4.3 (the owner's Q1,
2026-10-09). This plan puts that track first, and carries it to a cutover decision rather than stopping at the
adapter.

**The question it answers:**

> **Can the squad run on a faster engine with no loss in what it emits, and does the framework's structure hold
> through its largest refactors, measured on the engine 2.3 ships with?**

**Why the engine goes first, beyond speed.** An engine change is a listed-input change for every measurement after it
(SIP-0111 §1, its SIP-0110 overlap). So anything measured before the engine decision would be measured again after it:
- regression baselines;
- Outcome Evaluation's baselines;
- the next build-side memory experiment.

Deciding the engine first means 2.3 measures once.

---

## 1. What a faster engine buys, from this box's own records

Squad work dispatches one task at a time, so a cycle's length is mostly single-stream decode (SIP-0111 §1). Read from
the 2.2 cut set's four counted rolls:

| roll | wall clock (min) | authoring model calls (min) | share |
|---|---:|---:|---:|
| React 1 `cyc_0009e2942a6c` | 50.5 | 31.0 (10 calls) | 61% |
| Next.js 1 `cyc_e2a1ad13af47` | 54.3 | 33.2 (9) | 61% |
| React 2 `cyc_5fb4b1537245` | 52.0 | 32.9 (10) | 63% |
| Next.js 2 `cyc_e7e0670e2681` | 62.1 | 41.2 (12) | 66% |

The model-call minutes are each envelope's `recorded_at − captured_at` (SIP-0110's capture). They are a floor: calls at
seams that aren't captured, such as correction analysis, add to them. The rest of the wall clock is test runs, builds,
the boot audit and dispatch. A faster engine doesn't touch any of that.

- **At G0's bar** (TensorFold at most 0.75× Ollama's wall-clock per call), a roll saves about 8–10 minutes: **about 16%**.
- **At the vendor's figures,** about 0.5×: about 16–20 minutes, **about 32%**. These are vendor numbers, unmeasured here,
  and the class has missed its vendor claims here twice (SIP-0111 §3).
- **A campaign** is mostly cycles, and gains about as much.

**The gain arrives only at cutover, G4.** Until then, SIP-0111 runs TensorFold dark. The owner's disposition says
adoption rests on end-to-end cycle quality, latency, stability and recoverability, never on vendor tokens per second.

---

## 2. The work

### 2.1 Track A, first: SIP-0111 from S to a G4 decision

| step | what | where | cost |
|---|---|---|---|
| S | engine switching and rollback, with #1177's exclusivity guard. Exercised: a switch each way, a failed start that restores Ollama, restoration from a busy TensorFold, long-context memory within the floors (90 / 16 GiB) | #2199 | code: one PR (`scripts/dev/ops/engine_switch.py`); box: about 1 h |
| pre-registration | the sample, the split, the seeds, the recipe matrix, the floors and the analysis, posted to #2199 before the first TensorFold load | #2199 | prose |
| harness | each held-out envelope replayed through each arm, scored by its task type's production validator. A task type with no validator fails the harness | #2199 | code: one or two PRs |
| G0 / G1 | tuning, the frozen recipe, the held-out run, and the drafted-against-serial check | #2199 | **box: 17–56 h, by D2** |
| G2 | the adapter, dark: the port's four amendments (seed, thinking budget, normalized termination, the overflow error), the registry entries, the `docker-compose.tensorfold.yml` overlay (Q3: OK in principle), the conformance suite across every adapter, and parity tests | #2200, merged only if G0 and G1 pass | code: two to four PRs; a rebuild |
| G3 | an uncounted cycle A/B on both stacks: regression pairs interleaved A, B, A, B, one engine resident at a time, judged on cycle wall-clock, with a short pre-registration | **unplaced today: D3** | box: about 7–8 h (8 rolls, and a switch between each) |
| G4 | cutover, by S's switching path, or the trial parked with its record | **the owner's decision: D4** | — |

**Conditional, all the way down.**
- G2 is built only if G0 and G1 pass.
- G3 runs only after G2.
- G4 is the owner's, on G3's evidence. **This plan authorizes no production switch.** It asks for D4.
- A negative at any gate parks the trial, records it in SIP-0111 as Atlas's and vLLM's were, and 2.3 goes on with the
  stabilization track on Ollama.

### 2.2 Track B: stabilization, measured on the engine Track A leaves

All of these are placed in 2.3 already, by earlier rulings. Each is a framework fix or an output-quality change, as the
owner's direction of 2026-10-09 asks plans to say.

| item | what | kind | size | note |
|---|---|---|---|---|
| #2204 (with #2203) | host and GPU exporters, `GET /health/host`, a Host panel, a Grafana dashboard, and agent inference metrics (decode rate, TTFT, tokens per increment) | framework (instrument) | M–L | **early:** it is how Track A's cycle-time gain and memory floors are seen. Its compose services are OK'd |
| #2201 | CI's integration job pulls Docker Hub images unauthenticated, and hit the rate limit twice | framework | S | the owner's choice: credentials or a mirror |
| #2202 | a manifest decision the build does not honour passes acceptance | **output quality** | M | the first of its class (2026-10-09 direction) |
| #2205 | a manifest delta's undefined key is dropped, so a footprint can omit the file every criterion needs | output quality | S–M | placed here at the 2.2 cut |
| #2206 | a cross-role repair's file is labelled as the failed task's | framework (evidence) | M | placed here at the 2.2 cut |
| #2210 | a revocation names finished units as still holding the lesson | framework (display) | S | placed here at the 2.2 cut |
| #2208 | the `criterion_already_satisfied` rubric: how a manifest's silence is read | prose | S | |
| the tier's timeout half, live | a diagnostic-only fault that makes an increment's plan ask a question, then the expiry, the parked cycle, `abandon_and_propose`, the no-progress stop and the late answer, read on one campaign | framework | S code, ~3 h box | placed here by 2.2.1's D2 |
| #2174, #2175, #2176 | SIP-0110's entry-point prerequisites: the legacy agent store dormant with its failures visible, chat's history with session ownership checked, and the context-assembly port, inert | framework | M each | Q25's 2.3 placement |
| #1976, #1977 | API contract residue; comms deduplication, a dead-letter queue and publisher confirms | framework | M, M–L | |
| #316 | the request-profile taxonomy | framework | L | **its SIP must be accepted first** (Q13: pinned definitions keep resolving old names) |
| Outcome Evaluation's reporting-only instruments | the yardstick that the output-quality work after 2.3 is measured against | instrument | M–L | **its SIP must be accepted first** (PR #1963, proposed) |
| #1992, #1993, #1994 | the structure batch: orchestration out of `adapters/cycles` (about 12,000 lines), a `stacks` package, the largest units split | framework (refactor) | L, M, L | **one refactor per rebuild, each with a regression pair.** D5 |

### 2.3 Not in 2.3

- **SIP-0111 G4's consequences,** if adopted: every later counted set and memory measurement restarts on TensorFold
  (SIP-0111 §4). No lesson is approved, so no replay check is owed.
- **The next build-side memory experiment** (SIP-0110 §5h): broad multi-increment campaigns with memory on. It costs many
  hours of box time and must run on the final engine. Recommended for 2.4, beside Outcome Evaluation's scenarios (D6).
- **#2177–#2183** (the entry points' feature half, 2.4) and **#2184** (2.5), as SIP-0110's ledger places them.

---

## 3. Sequencing: the box is the constraint

One box runs everything: measurements, rebuilds, regression pairs and campaigns. Code proceeds on branches while it's
held.

1. **2.2.1 cuts.** Then the owner rules this plan.
2. **#2204's exporters and metrics,** and **#2201,** so the trial and the cycles are observed and CI is reliable.
3. **S,** built and exercised.
4. **The pre-registration, then the harness.**
5. **G0 / G1 on the box** (D2's size). Meanwhile on branches: G2's adapter, Track B's small defects (#2202, #2205,
   #2206, #2210, #2208), #2174–#2176, #1976, #1977, and the two SIP design reviews (#316's, Outcome Evaluation's).
6. **If G0 and G1 pass:** G2 merged dark, a rebuild, then G3. **If not:** the negative recorded, and Track B goes on with
   Ollama.
7. **G4, the owner's decision** (D4). On adoption, cutover by S, and from here every measurement is on TensorFold.
8. **Track B's merges, on the chosen engine:** the small defects and #2174–#2176 together in one rebuild with a
   regression pair; #1976 and #1977 in another; then the structure batch, one refactor per rebuild (D5).
9. **The cut:** a pre-registered regression set on both stacks, on the chosen engine, plus a campaign shakeout. If G4
   adopted TensorFold, this set is the engine's first counted baseline. Then the release procedure.

**The cut's criteria:**
- **Track A:** G4 decided (adopted, or parked with its record), with each earlier gate's evidence in SIP-0111.
- **Track B:** each item merged with its evidence, or re-placed by the owner. Substance gates the cut, not the clock.
- **The regression set** passes under its own pre-registration.

---

## 4. G0 / G1's size, from the corpus as it stands

The corpus on 2026-10-11 is 409 captured authoring envelopes. Under §4's split (tuning up to 2 per task type and stack,
held-out up to 8), it gives:
- **129 held-out envelopes:** 87 React and 42 Next.js;
- **39 tuning envelopes.**

One Ollama generation of the held-out set takes about **7.3 h**, from each task type's median call time in the corpus
(0.4 min for `builder.assemble` to 5.7 min for `qa.propose_plan_tasks`).

| protocol | Ollama | TensorFold (at 0.75×, at 0.5×) | tuning | total box |
|---|---|---|---|---|
| **as accepted** (3 generations per arm, a drift block, a matrix of at least 6 configs) | 29 h | 16 h, 11 h | ~10 h | **~50–56 h** |
| **lean** (2 generations, interleaved O, T, O, T so the order itself detects drift; the 3 checkpoints with production's thinking settings) | 15 h | 11 h, 7 h | ~5 h | **~27–32 h** |
| **leanest** (1 generation per arm; the 3 checkpoints) | 7 h | 5.5 h, 3.7 h | ~5 h | **~17–19 h** |

The power that matters is G0's median paired ratio and G1's per-seam pass rates:
- G0 has 129 pairs even at one generation. A median over 129 or more pairs resolves a 0.75 bar clearly.
- G1 compares pass rates per seam (plan writing, build authoring, proposal, repair), with tens of samples each. At one
  generation a one-sample difference moves the repair seam's rate visibly, and two generations halve that sensitivity.

Changing the protocol is an amendment to SIP-0111 §4, which the owner ruled. Hence D2.

---

## 5. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | **the order** | **Track A first** (S, G0, G1, then G2 and G3), Track B on branches meanwhile, and Track B's merges after G4, so 2.3 measures on one engine |
| D2 | **G0 / G1's size** (a SIP-0111 §4 amendment) | **lean, about 27–32 h of box time:** 2 generations per arm, interleaved, with the 3 checkpoints at production's thinking settings. *As accepted:* about 50–56 h. *Leanest:* about 17–19 h, with noisier per-seam pass rates |
| D3 | **G3, placed** | **in 2.3,** with its short pre-registration. It runs only after G2 |
| D4 | **G4, the cutover decision** | **in 2.3, the owner's, on G3's evidence, before the cut set**, so the cut measures the engine 2.3 ships with. Cutover in an odd minor extends Q1's waiver from "dark" to "adopted", and that extension is the owner's to grant. If it isn't granted, G4 moves to 2.4's start, and 2.3's cut runs on Ollama |
| D5 | **the structure batch** (#1992, #1993, #1994) | **kept in 2.3, after G4,** one refactor per rebuild with a regression pair each. If Track A runs long, **#1992 and #1994 move to 2.5** (the next odd minor) rather than stretch 2.3, and **#1993 stays** |
| D6 | **the next build-side memory experiment** | **2.4,** beside Outcome Evaluation's scenarios, on the final engine |
| D7 | **#2201's fix** | registry credentials in CI (a repository secret), or a pull-through mirror. Recommended: **credentials**, the smaller change |
| D8 | **who runs the line** | **the supervisor, on the 2.2 line's terms:** build in §3's order, merge on green with main's run read, run rebuilds and uncounted runs. **The owner's:** compose changes beyond #2204's and the overlay; G4; any lesson approval; the tag and Release unless delegated at the cut |

---

## 6. What this plan does not decide

- **G4 itself.** D4 places the decision; it doesn't make it.
- **The cut's numbers:** the regression set's size and the shakeout's exit rule, written as a pre-registration when the
  last batch is built.
- **#316's and Outcome Evaluation's designs.** Each needs its SIP accepted, at its own design review.
- **Anything compose beyond #2204's services and SIP-0111's overlay.**
