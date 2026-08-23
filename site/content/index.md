# Squad Ops

Squad Ops builds working applications from a written requirement. A cycle reads
the requirement, designs the interface, implements it, verifies it by execution,
and produces a runnable project directory.

It runs on locally hosted open-weight models. The reference deployment is a Qwen
27B model on an NVIDIA DGX Spark.

```bash
squadops cycles create play_game --squad-profile full --request-profile validated-fullstack
squadops runs assemble play_game <cycle-id> <run-id> --out ./output
```

## How a cycle works

| Stage | What happens |
|---|---|
| **Framing** | The squad authors an interface manifest — entities, endpoints, error contracts, screens — from the requirement. Two gates check it: structural completeness, and winnability (the design expands into a skeleton, the derived contract is satisfiable, fill slots enumerate). |
| **Review** | The cycle pauses for an operator when the design records an unresolved question. Otherwise it proceeds. |
| **Implementation** | The design expands into a skeleton of frozen files and fill slots. Agents write into the slots. |
| **Verification** | Tests execute. The application installs, builds, boots, and answers probes over HTTP against the contract derived from the design. |
| **Correction** | Failures are classified by locus — application, test suite, or harness — and repaired for a bounded number of rounds. |

## Verification results

Three verdicts, recorded per cycle:

| Verdict | Meaning |
|---|---|
| `accepted` | Every required check executed and passed |
| `rejected` | A check executed and failed |
| `blocked_unverified` | A required check never executed |

Each cycle publishes the full roll-up: checks verified, checks failed, checks
that never executed with a machine-readable reason for each, checks an operator
waived and why, and checks that have been inert across recent runs.

## Work assignment

A **capability** declares the work — `development.develop`, `qa.test` — with its
inputs, outputs, acceptance checks, and the roles permitted to fulfil it.

A **squad profile** binds each role to an agent instance and a model:

```yaml
profile_id: full
agents:
  - { agent_id: neo, role: dev, model: "qwen3.6:27b", enabled: true }
  - { agent_id: eve, role: qa,  model: "qwen3.6:27b", enabled: true }
```

Task plans are generated per run from the workload type and the roles the
profile fills.

## Measured results

The most recent measurement window closed 20 August 2026: a squad-authored
design produced a working application with no human intervention in 4 of 6
registered runs. Across the arc, 9 of 9 delivered applications install, build,
boot, and answer their probes.

[Method, full results, and their limits](evidence.md){ .md-button }

## Where to go

<div class="grid cards" markdown>

-   **[Getting started](getting-started.md)** — install, bootstrap, first cycle
-   **[Key concepts](key-concepts.md)** — cycles, runs, tasks, gates, artifacts
-   **[Architecture](architecture.md)** — ports, adapters, execution
-   **[CLI](cli.md)** — command reference
-   **[Roadmap](roadmap.md)** — 1.7, 1.8, 2.0
-   **[Improvement proposals](design/sips/index.md)** — 125 design records

</div>

---

Squad Ops is a research project under active development, built at
[backspring-labs/squad-ops](https://github.com/backspring-labs/squad-ops).
