# Stack #2 bend register — Next.js + TypeScript

**Purpose.** S3's exit criterion is **zero *unexplained* bends**. This is the artifact that
criterion is evaluated against, and it feeds S3's falsification pass and S5's admission rule.

**Written during, not after.** A register reconstructed at the end is a rationalization — you
cannot recover the moment you chose to accept a constraint, only the story you tell about it
afterwards. Every entry below was recorded while the code that produced it was being written
(#822 Stage 1c), and the same rule applies to anything added later.

**Scope.** Stack #2 is `nextjs_ts` (`capabilities/stack_nextjs_ts.py`), selected by S2's
amended ruling (2026-08-09, PR #826). Stack #1 is `fullstack_fastapi_react`.

---

## The classification, and why it is not one bucket

S3's definition is precise: a bend is *"a convention the stack had to adopt that it would not
otherwise use, purely to satisfy the schema."* Applying it strictly splits what looked like six
bends into four different kinds, and the split is the useful part — **"the schema is wrong
here" and "the stack conceded here" demand opposite responses.**

| # | Finding | Kind | Direction |
|---|---|---|---|
| 1 | the API is many fill slots, not one | **schema defect** | the blueprint was wrong |
| 2 | path parameters translate `{x}` → `[x]` | **cleared** | neither side bent |
| 3 | `frontend.routes[].view` has no home | **field with no home** | the schema does not map |
| 4 | route handlers, not server actions | **bend** | the stack conceded |
| 5 | seven whole-tree builds per acceptance pass | disclosure | a cost, not a concession |
| 6 | no static check on route slots | disclosure | a coverage gap, already known |

**One true bend.** That is the number S3 has to argue, and #4 is argued below.

---

## 1 — The API is many fill slots, not one · *schema defect*

**What happened.** FastAPI holds every endpoint in a single `backend/routes.py`. Next derives
the URL from the directory, so the reference manifest's **five endpoints became four route
files** — `app/api/runs/route.ts` (holding `GET` and `POST /runs`), then one each for
`[run_id]`, `[run_id]/join`, `[run_id]/leave`.

**The field that forced it.** `_ROUTES_PATH = "backend/routes.py"` — singular, hardcoded, and
the sole basis of the emitter's slot partition until #818.

**Why this is not a bend.** The stack adopted nothing unnatural; one file per route segment is
Next's own convention. It is the *blueprint* that could not express the situation. Recording
it as a bend would have put the concession on the wrong side and left the schema unexamined.

**Argued as a genuine cross-stack convention:** an API is a set of addressable operations, and
how many files hold them is the stack's business, not the contract's.

**The supporting evidence is unusually good.** `VerificationContract.endpoint_owners()` already
returned a **dict** — endpoint → owning file — and **survives this stack unchanged**. The
relation was modelled correctly all along; only the partition that produced it was singular.
That is the difference between a schema that generalizes and one that happened to fit.

**What S3 owes:** the blueprint must express "which endpoints does *this* file own", not "is
this *the* routes file."

## 2 — Path parameters translate to bracket directories · *examined, cleared*

`{run_id}` (manifest) · `:run_id` (Express) · **`[run_id]`** (Next, as a directory name). Three
conventions, and #820's third named trigger fired here exactly as predicted.

**Not a bend.** The manifest's form stays canonical and the expander places files at derived
locations — declared-then-placed is what an expander is for. Both sides kept their idiom and
neither conceded.

Recorded anyway, because a register that lists only problems cannot show that anything was
*checked*. This one was, and the schema came out clean.

**Consequence for #820:** its deferral holds. The class it defers is *cross-endpoint naming
incoherence within one manifest*, which translation does not touch.

## 3 — `frontend.routes[].view` has no natural home · *field with no home*

**What happened.** The manifest declares `view: RunsListView` for a route. In Next the URL comes
from the directory and **the file is always `page.tsx`**, so a declared component name cannot be
a filename. It became the exported component's name instead.

**Why this is its own kind.** The stack did not concede — it has no opinion about what the
export is called. The schema simply has a field whose meaning is stack-#1-shaped: on stack #1
`view` is *the filename*, and that identity is unavailable here.

**Left as a strain, deliberately.** This is §5c.3's territory — *"authored mode binds to the
blueprint's declared design artifact(s)"* — routed to **1.7** by owner ruling. Reshaping the
manifest now would generalize its schema from one-and-a-half instances, which is the failure
the Blueprint SIP declines acceptance over.

## 4 — Route handlers, not server actions · **the bend**

**What happened.** Next offers two ways to run server code for a mutation: a **route handler**
(`app/api/runs/route.ts` exporting `POST`) and a **server action** (a function marked
`'use server'`, invoked from a component and addressed by an opaque generated id). An idiomatic
App Router app frequently uses server actions for form mutations. **Stack #2 is constrained to
route handlers.**

**The field that forced it.** `api.endpoints[].method` + `.path`, and everything downstream of
them: the derived contract's probes issue real HTTP against a declared method and path, and a
server action has no stable path to address.

**The argument, which S3 must accept or reject.** *A design is declared as a set of addressable
HTTP operations.* If that holds as a cross-stack convention, this is not a concession but the
schema doing its job — and the behavioral probe tier, the one thing that transferred between the
two stacks untouched, depends on it.

**The counter-argument, recorded so the decision is real.** It removes a genuinely idiomatic
option from the stack, and a future stack whose transport is not HTTP (the non-REST row in the
plan's unvalidated-assumptions table) would have no answer at all. So the convention holds for
*HTTP stacks* and is silent beyond them — which is narrower than "cross-stack" claims to be.

**Status: argued, not settled.** S3 decides.

## 5 — Seven whole-tree builds per acceptance pass · *disclosure*

`frontend_compiles` is anchored per fill slot, so stack #1 pays 3 builds and stack #2 pays 7 —
and a Next build is not the sub-second warm-cache npm install the check's docstring describes.

**Kept at parity anyway.** #641/#648 attach the check to the file under evaluation so a failure
repairs *where the defect lives*. Dropping to one build for the tree would trade repair
targeting for wall-clock, and repair targeting is what #650 and #688 were both written to fix.

**Watch at VS**, and revisit only with a measurement.

## 6 — No static check on the API route slots beyond the build · *disclosure*

The nine AST checks parse Python by construction (`ast.parse`). `tsc --noEmit` **is** on the
`command_exit_zero` safelist but is **not provisionable** — `tsc` lives in `node_modules/.bin`,
never on `PATH` — so emitting it would produce #707's *"passes the allowlist but cannot run"*
class: a check that is always `skipped`.

`next build` runs tsc itself and `next.config.mjs` declines to ignore type errors, so **the
bundler check is the type check.**

**What remains genuinely uncovered:** no criterion proves the declared endpoints *exist in the
source*. `endpoint_defined` is Python-only, so that claim rests on the behavioral probes alone —
late and functionally, rather than early and structurally. This is S4's territory and was
disclosed before the stack was built.

---

## Adding an entry

Append in the same PR as the code that caused it, with: what happened · the field or assumption
that forced it · which of the four kinds it is · the argument for or against. An entry without a
named field is not reviewable, and an entry added later is a story.

## What consumes this

- **S3's falsification pass** — remove or corrupt each blueprint field and confirm something
  breaks in at least one stack. Entries 1 and 3 name fields that are already known not to work
  as written.
- **S3's promotion** — "zero unexplained bends" is evaluated against entry 4, the only true
  bend, plus the two disclosures.
- **S5's admission rule** — a new blueprint field must be demonstrated on two stacks. Entry 1
  is the candidate this stack earns; entry 3 is the candidate it explicitly does *not*, since
  1.7 owns that question.
