# Evidence

**This page is about how the project evaluates itself — not about what the
framework does for you.** The two are easy to confuse and worth separating
before anything else.

| | Verification | Measurement |
|---|---|---|
| **What** | Checks derived from the design, executed inside every cycle | Windows that score whole cycles, run by the maintainers |
| **Who gets it** | Anyone running a cycle. It is a framework feature | Nobody. It is how *this project* tests whether the framework works |
| **Produces** | A cycle verdict and an evidence roll-up | The numbers quoted on this site |
| **Where** | [Key concepts](key-concepts.md#4-verification-execute-dont-assume) | This page |

Measurement *consumes* verification — a window's scoring rule reads the cycle
verdict as one of its inputs — which is exactly why they blur. But
pre-registered windows are research methodology **about** the product, not a
capability **of** it. Nothing below is something you receive when you run a
cycle.

What it is instead: the reason to believe the claims made elsewhere on this
site.

## How the project measures itself

A measurement window is **pre-registered**: the number of runs, the requirement
document, the deployment hash, and the scoring rule are written down and frozen
*before the first run*. Once open, nothing is fixed mid-window.

That discipline removes the two ways a result normally flatters itself:

- **You cannot re-roll.** Every registered slot runs and is scored. A run cannot be
  quietly discarded because it went badly.
- **You cannot move the bar.** The scoring rule is committed in advance, so a
  disappointing number cannot be reinterpreted into a better one.

A run scores functional only if the cycle verdict is `accepted`, an independent
audit confirms the delivered application installs, builds, boots and answers
every probe its contract specifies, **and** no human intervened. The first
condition is the framework's own verdict; the second and third are the
maintainers checking it independently, because a framework grading its own
homework is not evidence.

## Results

### Authored-mode window — closed 20 August 2026

The squad authored its own interface design, then built against it.

| Measurement | Result |
|---|---|
| Under the pre-registered instrument | 3 functional / 6 |
| Under the corrected instrument | **4 functional / 6 — bar met** |

Both numbers are the record. The deciding run first scored as a failure; the
cause was a defect in the auditing tool, not the application. The correction was
ruled **before** the corrected measurement was taken, so the decision could not
be conditioned on its outcome.

Across the whole arc, **9 of 9 delivered applications** install, build, boot and
answer their probes. Every failed run failed in the test suite or the measuring
apparatus — none because the application was broken. Zero manual interventions
across the window, and no run was re-run to improve the figure.

### Seeded-mode window — closed 31 July 2026

The squad was *given* a fully specified interface design and built against it.

**6 of 6 functional.** This is the weaker claim of the two, and it is the one to
read carefully: it establishes that given a requirement *and a specified
interface*, the squad delivers a working application. Whether it could author
that interface was, deliberately, not measured — which is what the August window
went on to test.

## What this does not show

The honest boundary of both numbers:

- **One technology stack.** A second is in progress. Nothing here speaks to
  portability across stacks.
- **Small-to-moderate greenfield web applications**, built from a single
  requirement document. No evidence at all about large existing codebases,
  migrations, or work against unfamiliar code.
- **4 of 6 is a starting point, not a plateau.** The limitations that cost the two
  failed runs are known and queued.
- **Local models only.** Nothing here says how the framework behaves against a
  frontier hosted model, because that is not the configuration it is built for.

## Why the instrument story is on this page

It would be easy to publish only the corrected number. Recording both, and the
order the decisions were taken in, is the point: a measurement programme that
hides its own instrument failures cannot be trusted about anything else.

The two layers happen to share that principle — the framework never reports an
unexecuted check as a pass, and the measurement programme never quietly drops a
run that went badly — but they are separate mechanisms, built at different
times, for different audiences.
