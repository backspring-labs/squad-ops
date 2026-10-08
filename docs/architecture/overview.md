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
- **Capability handlers and the CLI do not import runtime persistence**
  (`adapters.persistence.runtime`).
- **Decisions do no I/O** (`test_pure_decisions_do_no_io.py`), and task types are strings at the
  boundary and `TaskType` members at the core (`test_task_type_literals_live_at_the_boundary.py`,
  CLAUDE.md "Task-type identifiers").
- **Where code goes:** a domain model, decision or port goes in `src/squadops/`; anything that
  speaks to a database, queue, model server, filesystem or vendor SDK goes in `adapters/`, behind a
  port. **One known exception:** the cycle orchestration in `adapters/cycles` (about 12,000 lines)
  holds domain logic with no infrastructure import; its move into `squadops.cycles.execution` is
  placed in 2.3 (#1992).

## Core packages (`src/squadops/`)

### `squadops.agents`
`BaseAgent`, which receives its ports (LLM, memory, prompts, queue, metrics and events, filesystem,
LLM observability) by constructor injection, the immutable `PortsBundle`, and the agent container's
entrypoint, which consumes task envelopes from the queue and is the agent's composition root.

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
Task contracts and their handlers: the per-task-type handlers the agents run, the scaffold and its
stacks (`scaffold`, `stack_fastapi_react`, `stack_nextjs_ts`), typed acceptance, the context-assembly
contracts that decide what each task is handed, and the workload runner. "Capability" here means a
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
verification evidence rules (SIP-0096) and the delivered-tree rules. Its executor lives in
`adapters.cycles` today (#1992).

### `squadops.embeddings`
The embeddings domain: the request and result models an `EmbeddingsPort` adapter serves.

### `squadops.events`
The cycle lifecycle event system: event types, payload models and the public emission API. The bus
implementations are adapters (`adapters.events`).

### `squadops.llm`
The LLM domain: request, response and chat-message models, its exceptions, and the model context
registry (SIP-0073), which maps each model name to its context window and defaults.

### `squadops.memory`
The memory domain: entries, queries and scored results for semantic memory (SIP-042), and Cross-Cycle
Memory's (SIP-0110): the recall query and recalled pattern, and the authoring replay envelope with its four seams.

### `squadops.orchestration`
Coordination between agents and handlers: `AgentOrchestrator`, the handler registry and the
`HandlerExecutor`.

### `squadops.ports`
The port interfaces, the contracts between the domain and external systems: secrets, queue, cycle
registry, auth, audit, LLM observability, sandbox and the rest.

### `squadops.prompts`
Deterministic, versioned prompt assembly: fragments and request templates through `PromptService`
and the request renderer. Prompt content lives here as managed assets, never as handler literals
(#448; `docs/PROMPT_AUTHORING_STANDARD.md`).

### `squadops.runtime`
Agent runtime state (SIP-0089): runtime modes, activity, focus leases, assignments and duty windows.
A pure coordination layer that depends on ports only, never on adapters.

### `squadops.sandbox`
The execution sandbox domain (SIP-0102): the service that builds and runs a delivered app in
isolation, and its entrypoint (`squadops.sandbox.main`, a composition root).

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
Cycle execution (SIP-0064, SIP-0066): `DispatchedFlowExecutor`, the correction runner and repair
loop, run provisioning and completion, the memory and Postgres cycle registries and their factory.
Most of it is orchestration with no infrastructure import, moving to `squadops.cycles.execution` in
2.3 (#1992).

### `adapters.embeddings`
Implementations of `EmbeddingsPort`.

### `adapters.events`
Cycle event buses: in-process and NoOp, the runtime event publisher, and their factory.

### `adapters.llm`
Model servers: Ollama, vLLM's OpenAI-compatible API, and Atlas (SIP-0106).

### `adapters.memory`
Semantic memory on LanceDB.

### `adapters.noop`
NoOp port stubs for bootstrapping a `PortsBundle` (SIP-0066).

### `adapters.observability`
Health-check reporting over HTTP, for the operations dashboard.

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
