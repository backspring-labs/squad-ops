# 2.3.1 plan — what the 2.3 cut found, fixed small

**Status: ADOPTED (2026-10-16).** The owner ruled §5 at ~15:26 ET: "approve D1-D3 for 2.3.1". The scope was ruled
earlier the same day. After the 2.3.0 cut the owner placed five items here: "place the 2.3.1 candidates you listed
after the cut", and "yes" to adding #2381 the same way. D2 adds a sixth, #2384. This plan says how each is built, how
the line is verified, and what it leaves out.

**What 2.3.1 is.** A patch on the 2.3 line (CLAUDE.md, #281: urgent or small fixes, either lane). Every item was found
on the 2.3 line, most of them by its cut. None is urgent: each is a defect that is small, understood, and cheaper to fix
now than to carry into 2.4, whose first campaigns start measuring outcomes. The headline line for 2.4 is its own plan's.

**The claim it makes:**

> **What a campaign's records and checks say is what happened:**
> - a late answer reaches the stored digest, and says who gave it;
> - a correct handler for a declared query parameter is not refused;
> - a check that ran and passed is not recorded as skipped;
> - a cycle that failed does not read `accepted`.

---

## 1. The six items

### #2322: the runtime API's unused RabbitMQ connection and channel are removed

- **The defect:** the runtime API opens an AMQP connection and channel at startup and keeps them on `app.state`
  (`src/squadops/api/runtime/main.py:682-683`, slots at `:126-128`). Nothing reads either, except to close the
  connection at shutdown (`:819-820`). Every publish goes through the queue port, which opens its own connection.
- **The fix:** remove both slots and their startup and shutdown code. First confirm that no route or startup sweep
  reads them through `request.app.state` dynamically. A static search finds none.
- **The test:** one that fails when either slot is set at startup. It runs the composition root's startup with the
  queue port faked.

### #2305: a late answer on a closed campaign updates the stored digest, and can be recorded as an agent's

- **The defect, in three parts:**
  - the answer route applies the transition without re-materializing the stored package (`campaigns.py:395`), while
    the close and the abort do (`_materialize_after_close`). So `campaigns digest` keeps asking for an answer that was
    given;
  - `squadops campaigns answer` has no `--as-agent`, where `runs gate` does (#812). A delegate's answer is recorded
    under the owner's user id;
  - the digest line doubles the question's period.
- **The fix:**
  - re-materialize after a late answer, as the close does, when the campaign is closed;
  - add `--as-agent`, recorded as `runs gate` records it;
  - join the answer without the doubled period.
- **The wiring test** enters at the answer route on a closed campaign. It asserts that the **stored** package, not
  only a digest built from the log, shows the answer and no longer asks for it. That gap is why the existing test
  missed the defect.
- **The ledger:** SIP-0109's row for #2305 moves from "unplaced, deliberately" to placed in 2.3.1, in this plan's PR.

### #2378, the smaller fix: the signature check accepts a declared query parameter

- **The defect:** `fill_slot_signature` pins a route's parameters to the scaffold's, which are the path's
  (`src/squadops/cycles/fill_slot_integrity.py:621`). It refuses any difference (`:682-686`).
  - In the cut's first counted roll, the manifest chose a query parameter for the leave endpoint. The developer's
    correct FastAPI handler was refused.
  - The accepted repair read the parameter through a context variable to get around the check.
- **The fix in 2.3.1:** an added parameter that is neither a path nor a body parameter is accepted. A removed or
  renamed scaffold-owned parameter is still refused, so the check keeps what it is for.
- **Not in 2.3.1:** the proper fix, an endpoint that declares its query parameters as a field the scaffold, QA's prompt
  and the probes read. That is 2.4's output-quality work.
- **The test:** three cases.
  - Today's refused handler, `name: str = Query("")` added beside `run_id`, now passes.
  - A renamed path parameter is still refused.
  - A dropped scaffold parameter is still refused.

  It must also hold on the Next.js stack's route handlers, or say why they don't carry the check.

### #2384: a failed cycle does not roll up as `accepted` (D2, ruled in)

- **The defect:** `aggregate_cycle_outcome` (`src/squadops/cycles/verification_integrity.py:875`) keeps a run's
  adverse verdict at cycle scope only when the run left no reconcilable rows (`:946`).
  - The 2.3 cut's set 1 fourth roll (`cyc_ce31b502b82c`) failed on a framework integrity error. Its implementation
    run's own verdict was `blocked_unverified`, from two optional rows that had executed and passed elsewhere.
  - Reconciliation superseded both rows, so the cycle detail read `accepted` beside the cycle's `failed` status.
  - The roll-up has no notion of a run that failed, only of the rows it left.
- **The fix:** a run that failed carries its adverse verdict to cycle scope, unless a later run re-executes its work.
  The "opaque" rule (#388) extends to a failed run, whatever rows it left. First read every caller of
  `resolve_cycle_outcome` (the cycle-detail API, the release package, wrap-up and gates). The rule is right only if
  none of them relies on today's reading of a failed run.
- **The test:** the issue's shape: a failed implementation run whose summary is `blocked_unverified` with only
  optional, elsewhere-executed unverified rows. Its cycle reads `blocked_unverified`. The edge: a failed run whose
  work a later run re-executed and passed still reads `accepted`. The wiring test enters at the cycle-detail route.
- **The release package keeps its warning** (#2385) as the guard against the next disagreement.

### #2297, a read first: does QA's test author see the leave endpoint's method and path?

- **The defect:** QA's backend test for leaving a run guessed the endpoint's method or path and got 405. That was 2 of
  the 3 TensorFold React cycles after the seed fix, and two Ollama cycles before.
- **The read:**
  - Is the endpoint's method and path in the `qa.test` prompt? The model sees what it edits
    (`docs/PROMPT_AUTHORING_STANDARD.md`).
  - What did each failing test call, against what the manifest declared?
  - Is it the input stated only in prose, as in #2378?
- **The fix ships in 2.3.1 where the read points:**
  - a prompt fragment (`src/squadops/prompts/fragments/`) when the endpoints are missing from what QA is shown;
  - nothing, with the read recorded on the issue, when they are there and the model ignores them. That is a 2.4
    output-quality question.

### #2381, a read first: a skip at patch verification must not replace a pass

- **The defect:** in a backend-only campaign increment, the view-compile checks were bound to QA's task. A developer
  repair's patch verification re-ran them where Node is missing. Their `missing_tooling` skips replaced QA's executed
  passes, and the record read 17 of 20 (`cyc_024e350cc844`; round 2's seed increment shows the same).
- **The read must answer one question first:** can a **required** row, such as `frontend_build`, be superseded the same
  way? If it can, a correct increment would end `blocked_unverified`. That is the outcome that failed the cut's first
  set, by a different path.
- **It ships in 2.3.1 if the fix stays inside patch verification:**
  - either a row the repaired files don't own keeps the task's executed result;
  - or the row is decided where the toolchain exists.

  Either way, with a wiring test at the live repair's entry. **If it needs the ledger's supersession rule changed, it
  moves to 2.4** with the read.

---

## 2. Not in 2.3.1

| item | why not | where |
|---|---|---|
| #2306, a converging repair ended as a plan defect | changes when correction gives up. The issue itself says to read the 12 recent terminations first | 2.4's plan |
| #2153, slot assertions routed by location | the owner ruled it waits for SIP-0110's measurement window (SIP-0104 §13d) | after the window |
| #2253, QA's output budget | raising it changes what a regression roll measures, so it belongs in a line's plan | 2.4's plan |
| #1469, `frontend_build`'s aggregate signature | still blocked on its corpus | re-read at each cut |
| #1756, stored prompts cut at 10,000 characters | an instrument, not a patch | 2.4's plan |
| #2286, TensorFold operator keys | credentials: the owner's to place | the owner |

---

## 3. Verification

Two of the items change the build's own path: the signature check every developer task runs (#2378), and possibly
QA's prompt (#2297). So unlike 2.2.1, a campaign alone can't show the build unchanged.

| step | what it shows | cost |
|---|---|---|
| each PR's unit and wiring tests, in CI | each fix at the entry point a live cycle uses | in the PR |
| `rebuild_and_deploy.sh all`, then `verify_loaded.py` from the main checkout | the deploy answers with the fixed code: one new loaded check per fix, plus every tracked row | ~15 min |
| **one regression pair, one roll per stack, uncounted** | the build unchanged on both stacks, with the new checks answering in each roll | **~1 h** |
| **one shakeout campaign**: 2.3's cut shakeout, carried | the campaign path unattended on the fixed deploy, and the reads' shapes where an increment reaches them | **~1.25 h** |
| the cut (CLAUDE.md steps 1–8) | the release, its package and its records | ~1 h |

**The exit rule:** the pair and the shakeout on one deploy, with no new seam finding.
- A finding in a changed seam is fixed, rebuilt and re-run.
- A finding elsewhere is filed and placed. It does not hold the patch unless the fixes caused it.

**What this does not cover:**
- **#2305, live:** a late answer needs a closed campaign with a pending escalation, and the shakeout asks nothing. It is
  read in its wiring test only.
- **#2378, live:** the refusal needs a manifest that chooses a query parameter, which one of the 2.3 cut's eight counted
  rolls did (set 1's first). The pair may not reach it.
- **#2384, live:** the defect needs a run that fails on a framework error, which a passing pair does not produce. It is
  read in its wiring test, and in the roll-up of any cycle in the pair or the shakeout that does fail.

---

## 4. Sequencing

1. #2322, then #2305, then #2378, then #2384. Each is its own PR, merged on green with main's run read.
2. The two reads, #2297 and #2381, recorded on their issues. Then a fix PR for each read that points to one inside
   2.3.1, or a re-placement to 2.4 with the read.
3. The rebuild, the loaded checks, the pair and the shakeout. Then the cut.

---

## 5. Decisions (ruled 2026-10-16)

| # | decision | recommendation | ruling |
|---|---|---|---|
| D1 | **the verification** | **§3 as written:** tests, a full rebuild with loaded checks, one uncounted pair and one shakeout campaign, about 2.5 hours of box time. *Heavier:* a counted set, two rolls per stack pre-registered as 2.3's was, about 2 more hours. *Leaner:* the shakeout alone, which leaves #2378's change to the build path read only in tests | **approved** |
| D2 | **#2384, a failed cycle rolling up `accepted`** | **in 2.3.1.** It is a correctness defect in the cycle roll-up that every consumer reads: the API, the console and the release package, which had to work around it at the 2.3 cut. The fix is to let a failed run's adverse verdict stand at cycle scope unless a later run re-executes its work. Read the resolver's callers first | **approved** |
| D3 | **who runs the line** | **the supervisor, on the 2.3 line's terms:** build in §4's order, merge on green with main's run read, rebuilds and uncounted runs. Through the cut, including the tag and the records upload once §3's exit rule holds and the release PR merges with main green. If a reading fails, it stops for the owner. Accepting SIPs and anything security-related stay the owner's. The grant ends at the 2.3.1 cut | **approved** |
