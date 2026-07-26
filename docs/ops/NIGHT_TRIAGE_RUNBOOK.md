# Night triage runbook — root cause, not narrative

How to take a failed measurement roll from terminal verdict to a fix on a branch, unattended,
without guessing. Written after the night of 2026-07-25/26, which produced two correct
diagnoses, two wrong ones I had to retract, and three idle hours.

The wrong ones are the reason this exists. Both came from the same move: **explaining a
symptom instead of tracing it.**

---

## The standard

A diagnosis is finished when you can name the line that caused the failure and show the
evidence. Not "the agent hallucinated names." Not "the repair loop didn't converge." A file,
a line, and the artifact or log entry that proves it.

If you cannot get there, say so and stop — an honest "unresolved, here is what I ruled out"
is worth more than a plausible story. A plausible story gets acted on and wastes the next
roll.

---

## Step 1 — verdict, then immediately past it

```sql
SELECT verdict, jsonb_pretty(summary::jsonb)
FROM run_verification_summaries WHERE run_id='<run>';
```

Read the four outcome states as genuinely different things. Conflating them is how you get a
wrong answer fast:

| State | Means | Does **not** mean |
|---|---|---|
| `failed` | ran, and the answer was wrong | — |
| `unverified` | never ran (usually the app didn't boot) | passed |
| `skipped` | declined to run (unsupported file type) | passed |
| `error` | the checker itself broke | failed |

`unverified` is the trap. pf-40's probe came back unverified because the app never started —
which masked whether the API was correct at all. Reading that as "the probe was fine" would
have hidden the real defect.

Then check `criteria_verified` against `criteria_total`, and remember the roll-up
under-reports: successful development work isn't recorded, so a fully verified run can show
three of six (#597). Do not diagnose that as partial coverage.

## Step 2 — rule out silent non-execution

```bash
python3 -c "
import json,glob,collections
c=collections.Counter()
for p in glob.glob('*/typed_check_evaluation_*.json'):
    for e in json.load(open(p)).get('evaluations',[]): c[e.get('status')]+=1
print(dict(c))"
```

Any `skipped` or `error` at `severity: error` is a check that contributed nothing. Find which
one and why before going further — a run can look thoroughly checked while a third of its
checks never executed.

## Step 3 — trace the file, do not sample it

**This is the step that finds the answer.** Every other step supports it.

Take the file the failure points at and read *every* stored version, oldest to newest:

```bash
for d in $(ls -tr); do
  [ -f "$d/backend/routes.py" ] && { printf "%s  " "$(stat -c %y $d|cut -c12-19)"; \
    grep -m1 -oE '<the line you care about>' "$d/backend/routes.py"; }
done
```

Both real findings this week came from exactly this and nothing else:

- imports going `RunEventCreate, ParticipantName` (correct) → `Run, CreateRun` →
  `RunCreate` → a five-name invention, showing the **developer was right and the repairs
  degraded it**
- the router going `APIRouter()` → `APIRouter(prefix="/api")` → `prefix="/runs"` →
  `APIRouter()` → `APIRouter()`, showing the loop **held the correct fix twice and discarded
  it**

Neither is visible in a single artifact. Both are obvious in the sequence.

## Step 4 — separate what was stored from what actually ran

The artifact vault keeps **every** emission, including repairs that were rejected and never
applied. The newest artifact is frequently *not* what executed.

Before attributing a failure to a file's contents, establish which version the failing check
actually saw. Two reliable cross-checks:

- **Did the app boot?** An unimportable file cannot boot. If the probe returned a status
  code rather than a boot failure, whatever ran was importable — so a stored file with
  broken imports was not it.
- **Which task ran the check?** Probes execute inside the QA task against the artifacts
  threaded onto that envelope at dispatch, not against a final assembly.

I skipped this step and reported that broken repairs "landed". They had not: the executor
assembles patched artifacts in memory and applies them only on a pass. One `grep` of the
verification call site would have prevented a wrong report.

## Step 5 — read the code path before naming a mechanism

If the claim is "X happens because the system does Y", open Y. Every time.

Claims that turned out wrong because I asserted rather than read:
- "the unverified patch lands" — the executor returns `"continue"` and re-dispatches
- "the frozen-emission evidence proves the author was never told" — those tasks were
  explicitly assigned those files

Claims that held because I read first: the missing `success_status` field, the absent
extension guard on four of five checks, the manifest declaring persistence with nothing
emitting it.

## Step 6 — treat the analyzer's diagnosis as a hypothesis

The failure analysis is LLM output. It is often right and sometimes confidently wrong, and it
can be right in a way that gets ignored. pf-41's five attempts produced five different
diagnoses; the third one correctly identified the path prefix, and the loop spent its
remaining attempts elsewhere.

Read all of them, note which repeat, and verify the claim independently before acting.

## Step 7 — root cause, phrased structurally

Push past "the model did something wrong" to what let it. The recurring shape:

> **The system holds the authoritative answer and never puts it in front of the thing that
> needs it, so the model improvises.**

Five instances in one week: the required success status (contract knew, decorator omitted);
the real class names (`models.py` held them, repairs never saw them); the persistence file
(manifest declared it, scaffold emitted nothing); the route prefix (the proxy rewrite is
frozen and unread); the packaging.

When a diagnosis fits this shape, the fix is usually **materialise or inject the fact**, not
add a detector. A detector rejects the guess; it never supplies the answer, so the next
attempt guesses again.

## Step 8 — fix, and prove it against the real artifacts

Branch, implement, then replay the fix against the **stored artifacts of the roll that
failed** — never a synthetic fixture:

```python
seed    = open('<run>/<seed_artifact>/backend/routes.py').read()
emitted = open('<run>/<failing_artifact>/backend/routes.py').read()
corrected, notes = fix_under_test(seed, emitted)
# assert the defect is gone AND the surrounding work survived, and that it parses
```

That is what turns "this should help" into "this would have fixed that roll." It costs
seconds and needs no cycle.

Prefer **enforcement over instruction** where the target is body-independent — a status code
and a router prefix can be restored safely because no function body depends on them; a
signature or a response model cannot, because the code around it does. Where enforcement is
unsafe, report the divergence rather than rewriting it.

---

## Unattended authority

Standing unless a specific instruction says otherwise:

**Do without asking** — read anything; query the database; replay stored artifacts; write
code on a branch; open a PR; file an issue; run the full regression and the contract gates.

**Never without an explicit rule** — deploy, rebuild, restart a service, merge, or change
frozen seeds mid-baseline.

**A deploy freeze is not a work freeze.** After a roll failed I wrote *"do not implement
anything"* into my own watchdog and then sat idle for three hours while the diagnosis was
already complete. The constraint was only ever "nothing deploys". Building and PRing was
always allowed, and had been done mid-campaign the night before.

If the campaign is stopped and the box is idle, the correct default is: finish the
investigation, build the fix, open the PR, and have it waiting.

## Stack the fixes

Multiple fixes toward one green go in a **stack**, each branch based on the last, so
deploying the tip gets all of them and each stays individually reviewable:

```
main → #604 model names → #606 store → #607 check guards → #608 router prefix
```

Note in the PR whether a change moves the **frozen surface** — if it does, the contract must
be re-emitted, re-ingested, and the launcher refs updated before the next roll.

## The morning report

Plain English, deltas and anomalies only, no optimism. Lead with what happened and what it
means; the identifier goes second, for traceability. Never use an issue number as a noun.
Translate internal vocabulary on first use. If a claim was later retracted, say so plainly —
a correction costs a paragraph, a wrong diagnosis acted on costs a roll.
