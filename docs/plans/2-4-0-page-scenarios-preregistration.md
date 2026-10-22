# 2.4.0: the page scenarios' reading, pre-registered (SIP-0113 §10k B1 to B3, §10p rulings 12 to 14; #2564)

**Written** 2026-10-22 by the Spark lane, before revision 5 is drafted and before any tree below is read for it. It
fixes what #2564's step 8 reads and how, and the diagnostic ruling 13 places before it: what each tree has or lacks.

None of it is a suite value. The outcomes are ruling 12's, as §10p states them, and revision 5's values are written
apart and held out.

## 1. The trees

Each tree is the cycle's whole app by the evaluation service's own selection (`evaluated_tree_refs`), exported
read-only from the vault on 2026-10-22. The seven window trees' identities match their campaigns' records. The
reference pair predates the window and has none.

| pair (ruling 13, §10k B1) | stack | base | next |
|---|---|---|---|
| capacity | FastAPI + React | `cyc_413e75801797` (`c6cc245541ac…`) | `cyc_840e72247f38` (`99eb7f123ab5…`) |
| capacity | Next.js | `cyc_23232c9e72da` (`d9cbd66dde75…`) | `cyc_e5370cec344f` (`ab6c4f36b375…`) |
| sorting | FastAPI + React | `cyc_f9930df7c925` (`0f9a95fb98cd…`) | `cyc_b7432a9633a5` (`2618fa01fdfb…`) |
| sorting | Next.js | `cyc_e5370cec344f` (`ab6c4f36b375…`) | `cyc_679608d64edc` (`08269c43327a…`) |
| §10c's reference | FastAPI + React | `cyc_7a4b7a6fbf0e` (`dcff44b833ce…`) | `cyc_20246018f2b8` (`4692c159b8b3…`) |

## 2. The ground-truth diagnostic, read before B1

**The outcomes** are ruling 12's four:
- **O1, capacity's indicator:** a run's page shows how many have joined of how many it holds (k of N, in either
  written form).
- **O2, capacity on the page:** at capacity, the page's join is unavailable, or a join from the page leaves the count
  unchanged when read back over HTTP.
- **O3, the list's order on the page:** the runs list shows runs in date order, whatever order they were created in.
- **O4, joining from the page:** a join made on the page is recorded, read back over HTTP and on a fresh visit.

**The reader** is an agent that has seen none of the drafting. It reads each tree's delivered source and this
document. It never opens the suite, and it writes no repository text.

**What it records, per tree and outcome:**
- *has*, *lacks* or *can't tell*;
- the files and lines that decide it: the page code that renders the outcome and, for O2 and O4, the API handler
  the page calls.

**And ruling 3's inventory:** for each control O2 and O4 act on, and each region O1 and O3 read, its role and its
accessible name as the source renders them. That is the drafter's list of candidate names.

**Where it goes:** `var/window/2-4-0/page-scenarios/ground-truth.md`, kept with the window's records. A tree read
*can't tell* for an outcome is not used for B1 on that outcome.

## 3. The fault-injected tree

O4 has no tree that lacks it (ruling 13), so one is made.
- **Which:** the FastAPI capacity calibration, `cyc_413e75801797`, if the diagnostic reads it as having O4.
  Otherwise, the first base in §1's order that it reads as having O4.
- **The fault:** its page's join submission is removed. The join control still renders and is enabled; what it
  submits to the API is taken out, and nothing else changes. So the page offers a join that records nothing.
- **Why not the control itself:** a control that's not found reads `blocked_unverified`, `control_absent` (ruling 4).
  B1 reads a blocked result as no discrimination, so a missing control could never show one.
- **How:** `scripts/dev/read_scenarios.py --fault`, with the spec kept beside the ground truth. The output records the
  faulted identity and the tree it was made from, and names the reading a diagnostic (#1251's rule).
- **Prediction F1:** O4's page scenario fails on the faulted tree and passes on the tree it was made from.
  - **Falsified by** any other pair of results.
  - **If it reads `control_absent`,** the fault removed more than it names, and the diagnostic is remade.

## 4. The readings

**All of them:**
- run by `scripts/dev/read_scenarios.py`, after revision 5 is approved;
- on a deploy that carries #2564's step 6, named in the record with its evaluator tag;
- written with no campaign.

**B1, discrimination (§10k, as ruling 13 widens it):**
- **What runs:** one evaluation of each tree in §1, and of the faulted tree.
- **What's read:** each page scenario, on each pair whose trees the diagnostic reads as lacking and having its
  outcome, in either direction.
- **Falsified by:**
  - a page scenario that passes on a tree that lacks its outcome;
  - one that fails on a tree that has it;
  - one that passes both trees of every pair it's read on.

  Each such scenario is withdrawn as evidence.
- **A blocked result on either tree** is not discrimination. B1 is unread for that scenario on that pair, and the
  record says so.

**B2, no flake:**
- **What runs:** three evaluations of one unchanged tree per stack, `cyc_840e72247f38` and `cyc_e5370cec344f`. B1's
  reading of each is the first of its three.
- **"The same result"** is an equal result, blocked reason and first failing step, read per stack.
- **Falsified by** any difference. That scenario is withdrawn, and the driver's waits are read first.
- **Ruling 5's bounds** come from these runs: max(5 s, three times the longest wait observed), recorded with the tag
  that carries them.

**B3, held out:**
- **When:** after the readings.
- **What runs:** prediction 2's sweep, with the page markers (§10q item 5), over everything it reads. The evidence
  table is excluded from its dump, as the suite's own store is.
- **Falsified by** any marker found.

## 5. Reading rules

- **A reading is read from the tool's output and the records,** and never re-run to a pass.
- **A failure the ground truth contradicts is read by its evidence first,** with the owner's reader, outside every
  Git tree, before it is called a scenario's defect or a tree's.
- **An evaluation lost to the infrastructure** (`no_runner`, or `start_failed` on a tree that started in the window)
  is void, and is re-run. The record says so.
- **Nothing deploys during the readings.**
- **Revision 5's review and approval** are ruling 14's. The window log records that the drafter and the approver
  are the same actor, by the owner's delegation of 2026-10-21.

## 6. What this doesn't cover

- **Other stacks, and trees outside the window and the reference pair.**
- **The waits a scenario outside revision 5 needs.** Ruling 5's bounds hold for what B2 observes.
- **Whether an outcome matters to the app's users.** That is the scenario author's judgement, and D4 is the owner's.
- **A tree whose outcome the diagnostic reads *can't tell*.** It's named, and not read for that outcome.
