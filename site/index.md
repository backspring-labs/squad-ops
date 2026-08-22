---
layout: default
title: Home
nav_order: 1
permalink: /
---

# Squad Ops

A team of AI agents that builds working software from a written requirement.
{: .fs-6 .fw-300 }

Squad Ops takes a product requirement document and produces an application that installs,
builds, boots, and passes its own tests — with the design authored by the agents, not
supplied to them. It runs entirely on local, open-weight models.

[View on GitHub](https://github.com/backspring-labs/squad-ops){: .btn .btn-primary }

---

## What has actually been measured

Most agent frameworks are demonstrated. This one is measured, on windows whose size, inputs,
and scoring rules are written down and frozen *before* the first run — so the result cannot be
improved by re-rolling until it looks good.

The most recent window closed on 20 August 2026:

> A squad-authored design produces a working application with no human intervention, at a rate
> of **4 of 6** on a pre-registered window against a frozen deployment.

Three things about that number are worth more than the number itself:

**Nothing was re-run to improve it.** Six slots were registered; six slots ran. A tempting
lower reading was declined rather than retried.

**The scoring instrument's own error is disclosed.** The deciding run initially scored as a
failure. The cause turned out to be a defect in the auditing tool, not the application. The
correction was ruled *before* the corrected measurement was taken, so the decision could not be
influenced by its outcome — and both numbers stay on the record: 3 of 6 under the original
instrument, 4 of 6 under the corrected one.

**Every delivered application worked.** Across the whole arc, **9 of 9** applications that were
delivered install, build, boot, and answer every check their contract specifies. Every failed
run failed in the test suite or the measuring apparatus — none failed because the application
was broken.

### What is not proven

The applications are small-to-moderate web applications built from a single requirement
document against one technology stack. A second stack is in progress. Nothing here demonstrates
performance on large existing codebases, and the 4-of-6 rate is a starting point, not a
plateau — the known limitations that cost the two failed runs are queued as fixes.

---

## How it works

A **cycle** is one governed pass from requirement to application. It runs as a sequence of
workloads, each with its own agents, artifacts, and approval gates.

1. **Framing** — the squad reads the requirement and *authors an interface design*: the
   entities, endpoints, error contracts, and screens the application will have. This is the
   step that distinguishes Squad Ops from a code generator. The design is checked before
   anything is built: does it parse, is it structurally complete, and is it *winnable* — can the
   thing it describes actually be built and verified?
2. **Human review, only when it is needed** — the cycle stops for a person when the design
   records a genuinely unresolved question. When the agents have no open questions, it proceeds.
   A gate that is always rubber-stamped teaches nobody anything.
3. **Implementation** — the design expands into a skeleton with defined slots. Agents fill the
   slots; the frozen parts stay frozen.
4. **Verification** — tests are executed, not merely written. The application is installed,
   built, booted, and probed over real HTTP.
5. **Correction** — failures are diagnosed and repaired within a bounded number of rounds, with
   the failure evidence carried into the repair.

### The verification rule

Only checks that **executed and passed** count as verified. A check that did not run is
recorded as `blocked_unverified` — never as a pass. Every completed cycle publishes an outcome
that discloses what was verified, what was waived, and what never ran.

This sounds obvious and is the single most load-bearing decision in the system. A framework
that lets an unrun check read as green cannot tell you anything true about its own output.

---

## The squad

Six agents, each with a role and a reasoning style, coordinated over a message queue.

| Agent | Role | Responsibility |
|:------|:-----|:---------------|
| Max | Lead | Orchestration, correction decisions, gate closeout |
| Nat | Strategy | Requirement framing, objective definition |
| Neo | Development | Interface design, implementation |
| Bob | Builder | Assembly of build artifacts into a runnable project |
| Eve | Quality | Test authoring, execution, verification |
| Data | Analytics | Failure analysis, evidence gathering, cycle assessment |

Squad composition is a profile, not a hardcoded roster. Profiles range from a small
plumbing-check squad to the full six-agent squad on a 27-billion-parameter model.

---

## Local models, by design

Squad Ops runs against locally hosted open-weight models — no hosted API, no per-token cost,
no data leaving the machine. The reference deployment runs a Qwen 27B model on an NVIDIA DGX
Spark.

This is a constraint the project chose, and it shapes everything: the work goes into
scaffolding, verification, and correction rather than into a larger model. The open question
the project exists to answer is whether structure can substitute for scale.

---

## Architecture

**Hexagonal — ports and adapters.** The domain defines interfaces; infrastructure implements
them. Swapping the inference engine, the message broker, or the observability backend is a
configuration change, not a migration.

- **Ports** — LLM provider, queue, cycle registry, artifact vault, authentication, audit, observability
- **Adapters** — Ollama and vLLM inference, RabbitMQ, PostgreSQL, Keycloak, LangFuse, OpenTelemetry
- **Distributed execution** — tasks dispatched to agent containers over RabbitMQ, orchestrated with Prefect
- **Durable state** — cycles, runs, gates, and artifacts persisted in PostgreSQL with content-hashed artifact storage

Architectural decisions are recorded as **Squad Ops Improvement Proposals**, which move through
proposed → accepted → implemented. There are 125 of them; 65 are implemented.

---

## Try it

**Requirements:** Python 3.11+, Docker and Docker Compose, and [Ollama](https://ollama.com) for
local inference.

```bash
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops

python -m venv .venv && source .venv/bin/activate
pip install -e .

./scripts/bootstrap/bootstrap.sh dev-mac    # or dev-pc / local-spark
docker-compose up -d
```

Then run a cycle:

```bash
squadops login
squadops cycles create play_game --squad-profile lite --request-profile selftest
squadops cycles show play_game <cycle-id>
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

`squadops doctor dev-mac` validates the environment against the profile contract before you
start.

**Squad profiles:** `smoke` (3B, liveness only) · `lite` (7B, full pipeline cheaply) ·
`full` (27B, the quality squad).

**Worked examples**, each with a requirement document and a request profile:
`hello_squad` · `play_game` · `group_run` · `run_crysis` · `agent_chess`

---

## Project status

**Version 1.6.1.** Roughly 89,000 lines of Python across the framework and its adapters, with
8,000+ unit tests. Releases follow an even/odd convention: even minors carry features, odd
minors are feature-free stabilisation releases.

Squad Ops is a research project under active development, not a product. It is developed in the
open at [backspring-labs/squad-ops](https://github.com/backspring-labs/squad-ops).
