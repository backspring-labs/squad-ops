# Architecture overview — every package, and which way the imports point

**Status:** the architecture map (#1989). `CLAUDE.md`'s "Hexagonal Structure" points here. Each
top-level package under `src/squadops/` and `adapters/` has an entry, and every entry names a
package that exists: `tests/unit/architecture/test_architecture_overview.py` holds both directions,
so a package added or removed without updating this map fails the suite (the shape of the SIP ledger
guard, #1969).

## The layering, as the guards enforce it

SquadOps is hexagonal: the domain under `src/squadops/` defines ports (`squadops.ports`) and the
models and decisions around them, and `adapters/` implements the ports against real infrastructure.

- **Only the composition roots import `adapters.*`** (#154, `test_forbidden_imports.py`): the runtime
  API's wiring (`squadops.api.runtime`), the agent container's (`squadops.agents.entrypoint`), the
  sandbox service's (`squadops.sandbox.main`) and the bootstrap package (`squadops.bootstrap`). Every
  other domain module receives its ports by injection. `docs/architecture/composition-roots.md` is
  the full standard: a root delegates each binding to the adapter package's factory, with typed
  configuration and a required selector.
- **The runtime-state layer stays pure:** `squadops.runtime` imports neither `adapters` nor
  `squadops.cli`, and its coordinator does not import the event bridges directly
  (`test_forbidden_imports.py`).
- **The stacks depend on neither side** (#1993, `test_package_import_direction.py`):
  `squadops.stacks` imports neither `squadops.capabilities` nor `squadops.cycles`, deferred or not,
  and loading it loads neither. Both sides read it.
- **Capability handlers and the CLI do not import runtime persistence**
  (`adapters.persistence.runtime`).
- **Decisions do no I/O** (`test_pure_decisions_do_no_io.py`), and task types are strings at the
  boundary and `TaskType` members at the core (`test_task_type_literals_live_at_the_boundary.py`,
  CLAUDE.md "Task-type identifiers").
- **Where code goes:** a domain model, decision or port goes in `src/squadops/`; anything that
  speaks to a database, queue, model server, filesystem or vendor SDK goes in `adapters/`, behind a
  port. The cycle orchestration (about 12,500 lines with no infrastructure import) was the one
  exception, filed under `adapters/cycles` beside the executor's port; it moved to `squadops.execution`
  in 2.3 (#1992).
- **The orchestration sits above what it orchestrates** (#1992, `test_package_import_direction.py`):
  `squadops.execution` imports `cycles`, `campaigns`, `capabilities` and `stacks`, and none of them
  imports it, so it forms no mutual pair.

## Core packages (`src/squadops/`)

### `squadops.agents`
`BaseAgent`, which receives its ports (LLM, prompts, queue, metrics and events, filesystem, LLM
observability) by constructor injection, the immutable `PortsBundle`, and the agent container's
entrypoint, which consumes task envelopes from the queue and is the agent's composition root. An
agent holds no memory store: SIP-042's per-agent store was retired in 2.5 (SIP-0110 §A.4.3, #2184).

### `squadops.api`
The runtime API: the FastAPI service (`squadops.api.runtime`, a composition root), its routes on the
lanes `docs/architecture/api-route-lanes.md` sets, the request and response schemas, the mapping
between API types and domain models, and the error handlers.

### `squadops.auth`
Auth domain models (SIP-0062): identity, token claims, the auth context, roles and scopes, and the
auth exceptions. The Keycloak validation itself is an adapter (`adapters.auth`).

### `squadops.bootstrap`
System initialization (a composition root): handler registries with every handler registered,
orchestrators ready to execute, the doctor's environment checks and the secrets provider wiring.

### `squadops.campaigns`
Campaign orchestration (SIP-0109): the campaign object, its lifecycle and control log, the
continuation decision, the proposal rails and change requests, increment acceptance, the box lease,
and the evidence package. State lives behind `CampaignRegistryPort`; every control operation is a
logged transition.

### `squadops.capabilities`
Task contracts and their handlers: the per-task-type handlers the agents run, typed acceptance, the
qa suite's fill merge (`verification_scaffold_fill`, which opens SIP-0107's revision transaction and
so stays beside the handlers rather than in `squadops.stacks`), the context-assembly
contracts that decide what each task is handed (with the supply of Cross-Cycle Memory's approved
lessons to the four authoring seams they declare, `lesson_supply`), and the workload runner. "Capability" here means a
task contract, keyed by `task_type` (#922); the package keeps the name (PORTFOLIO Q23).

### `squadops.cli`
The `squadops` command (Typer): login, cycles, runs, gates, artifacts and campaigns against the
runtime API, its client, config and output formatting.

### `squadops.comms`
Queue message models and the messaging rules on top of them: task replay detection and run
cancellation signalling.

### `squadops.config`
Configuration loading and validation: `SQUADOPS__*` environment variables, with double underscores
for nesting, into typed settings.

### `squadops.contracts`
Cycle request profiles (CRPs, SIP-0065): the named profile packs a cycle is created from, and their
loader (`load_profile`), whose `defaults` flow into a cycle's applied defaults.

### `squadops.core`
Small core utilities: the `SecretManager` that resolves `secret://` references through a provider,
and lineage helpers.

### `squadops.cycles`
The cycle execution domain (SIP-0064): projects, cycles, runs, gates and squad profiles as frozen
dataclasses, the lifecycle state machine, task planning (`task_plan`), the implementation plan, the
verification evidence rules (SIP-0096) and the delivered-tree rules. Its executor is
`squadops.execution` (#1992).

### `squadops.embeddings`
The embeddings domain: the request and result models an `EmbeddingsPort` adapter serves. Nothing
consumes it since the LanceDB store's retirement (#2184); a semantic index, if one is ever added, is
derived from Postgres (SIP-0110 §A.3.10).

### `squadops.execution`
The cycle's orchestration (#1992): `DispatchedFlowExecutor`, which implements `FlowExecutionPort`, and
its collaborators: run admission, provisioning and completion, task dispatch and the reply router, the
correction runner and repair, patch acceptance, the pulse-boundary runner, the framing and workload
gates, cycle evidence and benchmark regrading. It reaches infrastructure only through ports, and sits
above `cycles`, `campaigns`, `capabilities` and `stacks`: it imports them, and they don't import it.

### `squadops.events`
The cycle lifecycle event system: event types, payload models and the public emission API. The bus
implementations are adapters (`adapters.events`).

### `squadops.llm`
The LLM domain: request, response and chat-message models, its exceptions, and the model context
registry (SIP-0073), which maps each model name to its context window and defaults.

### `squadops.memory`
The memory domain, Cross-Cycle Memory's (SIP-0110): the observations projected from three sources and the repeat
report; the lessons, their approvals and each unit's pinned snapshot; the recall query and its deterministic policy;
the exposures recording what each consuming task was supplied; the authoring replay envelope with its four seams; and
the entry points' typed records and instructions, and what a chat turn may hold and capture. SIP-042's per-agent
store and its models were retired in 2.5 (SIP-0110 §A.4.3, #2184).

### `squadops.orchestration`
Coordination between agents and handlers: `AgentOrchestrator`, the handler registry and the
`HandlerExecutor`.

### `squadops.outcomes`
Outcome Evaluation's readings beside its scenarios (SIP-0113 §4.2–§4.6), starting with the intervention
ledger (§4.3): each person's or supervisor's action on a campaign, projected from SIP-0109's control log
and classified by its reason and severity, plus declared entries for actions outside the interface.
Also what a campaign's proposal run is shown of its accepted tree (§4.5): the goals with their results,
the quality moves and the accepted PRD, read through `ProposalEvidencePort` and composed onto that one
task's inputs by `squadops.execution.proposal_evidence`. `StoredProposalEvidence` reads them from the
campaign's evaluations, promotions and approved requests; the executor never imports it.

### `squadops.ports`
The port interfaces, the contracts between the domain and external systems: secrets, queue, cycle
registry, auth, audit, LLM observability, sandbox and the rest.

### `squadops.projects`
Project Lifecycle Management (SIP-0112): the Project Record's parts (its lifecycle status, source
binding and ownership) and the registry cutover's refusals. The read model stays
`squadops.cycles.models.Project`, which carries these parts; this package imports nothing from
the cycle domain. The writable registry behind `ProjectRegistryPort` is
`adapters.cycles.postgres_project_registry`.

### `squadops.prompts`
Deterministic, versioned prompt assembly: fragments and request templates through `PromptService`
and the request renderer. Prompt content lives here as managed assets, never as handler literals
(#448; `docs/PROMPT_AUTHORING_STANDARD.md`).

### `squadops.runtime`
Agent runtime state (SIP-0089): runtime modes, activity, focus leases, assignments and duty windows.
A pure coordination layer that depends on ports only, never on adapters.

### `squadops.scenarios`
Outcome Evaluation's held-out scenarios (SIP-0113 §4.1, §4.7): a scenario's goal, held-out steps,
checks and surfaces, content-addressed, and a suite of them that the supervisor drafts and the owner
approves before a campaign pins it. No squad-side package imports it (IR-4). An evaluation run's
record, and apart from it in `squadops.scenarios.reference`, the reference SIP-0112's Project history
stores (contract 5), which imports only the standard library. A suite's markers
(`squadops.scenarios.markers`), the step values the P2 sweep searches for and a proposal's goals are
held back by.

### `squadops.sandbox`
The execution sandbox domain (SIP-0102): the service that builds and runs a delivered app in
isolation, and its entrypoint (`squadops.sandbox.main`, a composition root).

### `squadops.stacks`
The stack registry and its stacks (#1993): the registry and scaffold expander (`scaffold`), each
stack's module (`stack_fastapi_react`, `stack_nextjs_ts`), the scaffold contract, the verification
scaffold and its gate, and the leaves they share (type tokens, success status, route paths, the
rendered packaging). The cycle domain and the capability handlers both read it, so it imports
neither, and a stack change is a change to this package.

### `squadops.tasks`
Task envelopes and results (the A2A message format, with lineage per SIP-031) and the `TaskType`
enum that single-sources every dispatched task type.

### `squadops.telemetry`
Telemetry models: metric types, spans, structured events, the `CorrelationContext`, and the NoOp LLM
observability adapter that `BaseAgent` and `AgentOrchestrator` inject when none is configured.

### `squadops.tools`
Tool domain models and policy: container specs and results, version-control status, and the path
security policy filesystem access is held to.

## Adapter packages (`adapters/`)

### `adapters.audit`
The audit log adapter (SIP-0062): a logging implementation of `AuditPort` and its factory.

### `adapters.auth`
Keycloak OIDC: token validation and the JWT middleware (SIP-0062).

### `adapters.capabilities`
The filesystem repository for task contracts and reference workloads.

### `adapters.comms`
Queue transport: RabbitMQ, and the A2A server and client modules, imported lazily because only
agents with A2A install their dependencies.

### `adapters.cycles`
Cycle infrastructure (SIP-0064, SIP-0066): the memory and Postgres cycle, campaign, deploy and squad
profile registries, the filesystem artifact vault, the Prefect workflow tracker and log forwarder, the
config-backed project registry, and the factory that composes the executor from `squadops.execution`
with the ports a root has bound.

### `adapters.embeddings`
Implementations of `EmbeddingsPort`, which nothing builds since the LanceDB store's retirement (#2184).

### `adapters.events`
Cycle event buses: in-process and NoOp, the runtime event publisher, and their factory.

### `adapters.llm`
Model servers: Ollama, vLLM's OpenAI-compatible API, and Atlas (SIP-0106).

### `adapters.memory`
Cross-Cycle Memory's store (Postgres beside the cycle registry, and in memory for tests) with the
recall that answers from a unit's pinned snapshot, the typed records' store, and the reference
resolvers. SIP-042's LanceDB store was retired in 2.5 (SIP-0110 §A.4.3, #2184).


### `adapters.scenarios`
The held-out scenario store (SIP-0113 §4.1): Postgres beside the campaigns that pin its suites, and
in memory for tests. Never the artifact vault, which is where squad tasks' inputs come from.
### `adapters.noop`
NoOp port stubs for bootstrapping a `PortsBundle` (SIP-0066).

### `adapters.observability`
Health-check reporting over HTTP, for the operations dashboard.

### `adapters.outcomes`
The intervention ledger's store (SIP-0113 §4.3): Postgres beside the campaigns whose control logs it
classifies, and in memory for tests.

### `adapters.persistence`
Postgres through asyncpg: the runtime connection pool and the runtime ports, and the chat repository
and cache.

### `adapters.prompts`
Prompt repositories and asset sources: the filesystem fragments and request templates the prompt
service reads.

### `adapters.sandbox`
The sandbox's container adapters (SIP-0102).

### `adapters.secrets`
Secret providers: environment variables, files and Docker secrets, chosen by the factory.

### `adapters.telemetry`
Telemetry exporters: OpenTelemetry, a development console adapter, a null adapter, and the LangFuse
LLM observability adapter, buffered and redacting (SIP-0061).

### `adapters.tools`
Filesystem (with the path-security wrapper), Docker and Git adapters for the tool ports.
