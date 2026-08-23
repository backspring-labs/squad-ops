# Squad Ops

**A team of AI agents that builds working software from a written requirement.**

Squad Ops takes a product requirement document and produces an application that
installs, builds, boots, and passes its own tests — with the interface design
*authored by the agents*, not supplied to them. It runs entirely on local,
open-weight models.

[Get started](getting-started.md){ .md-button .md-button--primary }
[How it works](how-it-works.md){ .md-button }

---

## What has actually been measured

Most agent frameworks are demonstrated. This one is measured, on windows whose
size, inputs, and scoring rules are written down and frozen *before* the first
run — so a result cannot be improved by re-rolling until it looks good.

The most recent window closed on 20 August 2026:

<div class="measured" markdown>
A squad-authored design produces a working application with no human
intervention, at a rate of **4 of 6** on a pre-registered window against a
frozen deployment.
</div>

Three things about that are worth more than the number.

**Nothing was re-run to improve it.** Six slots were registered; six slots ran.
A tempting lower reading was declined rather than retried.

**The scoring instrument's own error is disclosed.** The deciding run first
scored as a failure. The cause was a defect in the auditing tool, not the
application. The correction was ruled *before* the corrected measurement was
taken, so the decision could not be influenced by its outcome — and both numbers
stay on the record: 3 of 6 under the original instrument, 4 of 6 under the
corrected one.

**Every delivered application worked.** Across the arc, **9 of 9** delivered
applications install, build, boot, and answer every check their contract
specifies. Every failed run failed in the test suite or the measuring apparatus.
None failed because the application was broken.

!!! warning "What is not proven"

    The applications are small-to-moderate web applications built from a single
    requirement document against one technology stack. A second stack is in
    progress. Nothing here demonstrates performance on large existing codebases,
    and 4 of 6 is a starting point rather than a plateau — the known limitations
    that cost the two failed runs are queued as fixes.

---

## The idea

Give a small model more structure instead of giving it more parameters.

Squad Ops runs against locally hosted open-weight models — no hosted API, no
per-token cost, nothing leaving the machine. The reference deployment runs a
Qwen 27B model on an NVIDIA DGX Spark. That constraint shapes everything: effort
goes into scaffolding, verification, and correction rather than into a larger
model.

Whether structure can substitute for scale is the open question the project
exists to answer, and the measurement above is how it gets answered.

---

## Where to go next

<div class="grid cards" markdown>

-   **[How it works](how-it-works.md)**

    The cycle — framing, review, implementation, verification, correction — and
    the rule that only executed checks count.

-   **[Architecture](architecture.md)**

    Ports and adapters, the agent squad, and the services underneath.

-   **[Getting started](getting-started.md)**

    Install, bootstrap, and run your first cycle.

-   **[Improvement proposals](design/sips/index.md)**

    Every architectural decision, recorded and searchable.

</div>
