# Key concepts

Squad Ops has four levels. Most confusion about the system comes from collapsing
them, so it is worth being precise before anything else.

```mermaid
%%{init: {'look':'neo','flowchart':{'nodeSpacing':36,'rankSpacing':52,'curve':'basis','padding':8}}}%%
flowchart LR
    P([Project]) --> C[Cycle]
    C --> R1[Run<br/>framing]
    R1 -->|gate| R2[Run<br/>implementation]
    R2 --> R3[Run<br/>wrap-up]
    R2 --> T1[task] & T2[task] & T3[task]
    T1 --> A([agent])
    T2 --> A
    T3 --> A
```

| Level | What it is |
|---|---|
| **Project** | The thing being built, and the namespace everything else hangs off |
| **Cycle** | One governed pass from a requirement to an application |
| **Run** | One **workload** within that cycle — framing, implementation, wrap-up |
| **Task** | One unit of work dispatched to one agent |

## Cycles

A cycle is created against a project with a requirement document, a **squad
profile** (which agents, on which models) and a **cycle request profile** (what
kind of pass this is). It is the unit you start, watch, and judge.

```bash
squadops cycles create play_game --squad-profile full --request-profile validated-fullstack
```

The request profile is where the shape of the cycle is declared — including its
**workload sequence**:

```yaml
workload_sequence:
  - type: framing
    gate: progress_plan_review
  - type: implementation
    gate: null
```

A cycle's status is derived from its runs: `created`, `active`, `paused`,
`completed`, `failed`, `cancelled`. **`paused` is the interesting one** — it
means the cycle is waiting for a human at a gate between workloads, not that
anything went wrong.

## Runs

**A run is one workload's execution — not a retry of the whole cycle.** This is
the distinction most worth internalising. A cycle that framed a design and then
implemented it has *two* runs, and they are separate rows with separate
identities, artifacts, and gate decisions.

Every run records the hash of the configuration it resolved. That is what makes
two runs comparable, and it is why a measurement window can claim a frozen
deployment: the run itself carries proof of what it ran under.

Runs are the resumability boundary too. Because each workload is its own run
with its own promoted artifacts, a cycle interrupted after framing can resume
into implementation without re-authoring the design.

Workload types are `framing`, `implementation`, `evaluation`, `refinement` and
`wrapup` — a documented vocabulary rather than a closed enum, since a request
profile may compose its own.

## Tasks

A run is planned into a list of **task envelopes**, one per unit of work, each
addressed to a specific agent. The envelope is the contract between the runtime
and an agent container: identity (`task_id`, `agent_id`, `cycle_id`,
`task_type`), the inputs the task needs, and lineage fields —
`correlation_id`, `causation_id`, `trace_id`, `span_id` — that are always
present so a task can be traced back through the run that planned it.

Task types read as `role.verb`: `strategy.frame_objective`,
`development.author_manifest`, `development.develop`, `qa.test`,
`governance.merge_plan`, `data.analyze_failure`.

The plan is not a fixed script. It is generated per run from the workload type,
the squad profile, and — once framing has produced them — the implementation
plan and verification contract. A build workload's task list is therefore
derived from the design the squad just authored.

## Flows and dispatch

The executor runs a plan under a declared **flow mode**:

| Mode | Behaviour |
|---|---|
| `sequential` | One task at a time, fail-fast |
| `fan_out_fan_in` | Parallel dispatch, barrier before the next stage |
| `fan_out_soft_gates` | Parallel dispatch with non-blocking checkpoints |

Dispatch is a request/reply over RabbitMQ: the executor publishes a task
message, an agent container consumes it, executes the handler for that task
type, and replies with a result. Agents are separate processes — a task
crossing to an agent is a real network hop, not a function call, which is why
the envelope carries everything the agent needs rather than a reference to
shared memory.

**Prefect provides the view, not the control.** Each run opens a flow run and
every dispatched task nests inside it, so `http://localhost:4200` shows the run
as a graph with per-task logs. The orchestration decisions are the executor's;
Prefect is where you watch them.

## Gates

Two different things are called gates, and they behave differently.

**In-run gates** are declared in the task flow policy and fire after a named
task type completes — `progress_plan_review` after `governance.review`, for
example. They interrupt the task sequence within a run.

**Inter-workload gates** sit between runs. These are the ones that move the
whole cycle to `paused` until someone decides. A gate decision is recorded on
the run with who decided it and when — and, when an operator accepts with a
waiver, exactly which checks were waived and why. The waiver sits *above* the
evidence and never edits it.

```bash
squadops runs gate play_game <cycle-id> <run-id> progress_plan_review --approve
```

## Artifacts

Everything a task produces goes to the artifact vault, content-hashed and
immutable. Artifacts start `working`; promotion to `promoted` is one-way.

Promotion is what carries work between workloads: when a framing run completes,
its *promoted* artifacts — the interface design, the implementation plan, the
derived contract — are forwarded into the implementation run. Working artifacts
are not forwarded, so a rejected draft cannot leak into the next workload.

---

## The pass itself

With the machinery established, the actual work of a cycle:

```mermaid
%%{init: {'look':'neo','flowchart':{'nodeSpacing':38,'rankSpacing':48,'curve':'basis','padding':8}}}%%
flowchart LR
    R([Requirement]) --> F[Framing<br/>author + gate the design]
    F --> I[Implementation<br/>fill the skeleton]
    I --> V[Verification<br/>execute the checks]
    V --> O{Outcome}
    O -->|passed| A([accepted])
    O -->|never executed| B([blocked_unverified])
    O -->|failed| C[Correction]
    C -->|repaired| V
    C -->|rounds exhausted| X([rejected])
```

### 1. Framing — the squad authors the design

The squad reads the requirement and produces an **interface manifest**: the
entities, endpoints, error contracts, and screens the application will have.

This is the step that separates Squad Ops from a code generator. The design is
not supplied; it is written by the agents and then checked before anything is
built — a **schema gate** (does it parse, is it structurally complete) and a
**winnability gate** (can the thing it describes actually be built and
verified: does the skeleton expand, is the derived contract satisfiable, do the
fill slots enumerate, do the test anchors cover the screens it promises).

A design that cannot be won is rejected in seconds, rather than an hour into a
build.

### 2. Review — only when it is needed

The cycle stops for a human when the authored design records a genuinely
**unresolved question** — the squad saying the requirement does not determine
something, and declining to guess. With no open questions it proceeds.

This is deliberate. An earlier version reviewed every design, and the reviews
became rubber stamps discussing facts the automated gates had already proven,
while a real unresolved question sat unsurfaced. A gate that is always approved
teaches nobody anything, and makes a later reader unable to tell a considered
approval from a reflex.

### 3. Implementation — fill the slots

The accepted design expands into a skeleton: some files frozen, others slots to
be filled. Agents write into the slots; an attempt to write outside them is
caught rather than merged.

### 4. Verification — execute, don't assume

Tests are **executed**. The application is installed, built, booted, and probed
over real HTTP against the contract derived from the design.

```mermaid
%%{init: {'look':'neo','flowchart':{'nodeSpacing':38,'rankSpacing':48,'curve':'basis','padding':8}}}%%
flowchart LR
    C([A check]) --> E{Did it<br/>execute?}
    E -->|no| B[blocked_unverified]
    E -->|yes| P{Did it<br/>pass?}
    P -->|yes| V[verified]
    P -->|no| F[failed]
```

Three outcomes, not two. Most systems collapse the left branch into one of the
others — a check that could not run is reported green because nothing failed,
or red because nothing passed. Both are lies, and each is wrong in the direction
that hurts most: the first hides broken verification, the second sends a
correction round after an application that was never actually tested.

The same distinction carries to the cycle verdict. `rejected` means the product
failed a criterion and the product is what to repair; `blocked_unverified` means
the framework *cannot honestly claim* it verified anything, and the harness,
environment or configuration is what to repair.

### 5. Correction — bounded, and aimed

When something fails, the failure evidence is classified before anything is
repaired: is the defect in the application, in the test suite, or in the
machinery doing the measuring? Those route to different fixes, and confusing
them burns attempts.

Repairs run for a bounded number of rounds, carrying the failure evidence
forward so a later attempt knows what the earlier one was told. A chain that
stops making progress — the same failure signature twice — is terminated rather
than left to spend the budget rediscovering it.

---

## Capabilities, roles and squad profiles

These three are the concepts worth holding. Everything else about "the agents"
follows from them.

```mermaid
%%{init: {'look':'neo','flowchart':{'nodeSpacing':36,'rankSpacing':60,'curve':'basis','padding':8}}}%%
flowchart LR
    C[Capability<br/>development.develop] -->|owner_roles| R[Role<br/>dev]
    R -->|squad profile| A[Agent instance<br/>id + model]
    A -->|dispatch address| Q([queue])
```

### Capability — the unit of work

A **capability** is a contract: an id like `development.develop` or `qa.test`,
the inputs it accepts, the outputs and artifacts it produces, the acceptance
checks that decide whether it delivered, and a timeout. It also declares
`owner_roles` — which roles are permitted to fulfil it.

A task's `task_type` *is* a capability id. When a run plans
`development.author_manifest`, it is naming a capability, and the contract for
that capability determines what the task must be given and what it must
produce.

Roughly 35 capabilities exist today, grouped by the role that owns them:

| Prefix | Examples |
|---|---|
| `strategy.` | `frame_objective` · `analyze_prd` · `propose_plan_guidance` |
| `development.` | `design_plan` · `author_manifest` · `develop` · `repair` |
| `builder.` | `assemble` · `assemble_repair` |
| `qa.` | `define_test_strategy` · `test` · `validate` · `assess_outcomes` |
| `data.` | `research_context` · `analyze_failure` · `gather_evidence` |
| `governance.` | `define_done` · `review_plan` · `merge_plan` · `correction_decision` |

### Role — who may fulfil it

A **role** is the abstraction the framework actually resolves against:
`strat`, `dev`, `builder`, `qa`, `data`, `lead`. Capabilities are owned by
roles; task plans are built from roles; correction routing decides which *role*
repairs a failure.

Nothing in the framework depends on a particular agent existing. It depends on
a role being **filled**.

### Squad profile — which instance fills the role

A **squad profile** is the configuration that answers "for this cycle, which
agent instance and which model fills each role?"

```yaml
profile_id: full
agents:
  - { agent_id: neo, role: dev,     model: "qwen3.6:27b", enabled: true }
  - { agent_id: eve, role: qa,      model: "qwen3.6:27b", enabled: true }
  - { agent_id: bob, role: builder, model: "qwen3.6:27b", enabled: true }
```

Each entry may also carry `config_overrides` (temperature, completion budget,
timeout), so a role can be tuned without touching code.

| Profile | Model | Purpose |
|---|---|---|
| `smoke` | 3B | Liveness and plumbing only. Not a quality signal. |
| `lite` | 7B | The whole pipeline, cheaply. Framework validation. |
| `full` | 27B | The quality squad. What measurements are run on. |
| `full-38` | 27B (newer) | Comparison arm — identical to `full` but for the model |

The profile is resolved at plan time and its hash is recorded on the run, which
is what makes two runs comparable.

### Identity is a convenience

`neo`, `eve`, `bob` are **agent instance ids** — addresses on the queue and
labels in a log. They are not a framework concept, they carry no behaviour, and
the display names attached to them are for humans reading a trace.

Swap the id, and provided the role is still filled the cycle is unchanged. Two
instances can fill the same role in different profiles; the same id can run a
different model in a different profile. **Read a task's role, not its name** —
the name tells you which row of a config file was selected, and nothing more.
