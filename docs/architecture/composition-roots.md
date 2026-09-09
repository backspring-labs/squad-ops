# Composition roots — the standard for how the framework is wired at start-up

**Status:** the owning standard for what a composition root may construct and how (#301,
#286, #637; the 1.7.5 plan §3.1's first design artifact, 2026-09-09, rev 2 on the owner's
review the same day). `CLAUDE.md`'s "Hexagonal Structure" and "Key Patterns" summarise the
architecture; this document is the full statement of the start-up rule, the audit of the four
roots against it on main `5c686cbd`, and the decisions the audit forced. **Enforced** by a
composition-roots guard beside the existing architecture guards in `tests/unit/architecture/`
— specified in §6.5, landing in the same PR as the first root it constrains (1.7.5 plan
§3.10). **This document, not the plan, is the acceptance source for #286, #301 and #637**: the
plan owns placement and sequencing; this standard owns the architecture and what "done"
means.

This is one of two independent design decisions the 1.7.5 line reviews before its first
closure PR. The other, the recovery extraction map (`docs/plans/1-7-5-recovery-extraction-map.md`),
answers a different invariant and is not derived from anything here. The one connection
between them is that any collaborator the map introduces is constructed at a root-internal
composition seam this standard governs (§3); that applies the standard, it does not couple
the decisions.

## 1. The two principles

> **Importing code defines behaviour; starting the application performs configuration and
> wiring.**

and, at the moment of wiring:

> **Every adapter binding a composition root performs is delegated to the owning adapter
> package's approved factory. A factory takes typed configuration and a required selector.
> A root never instantiates a concrete vendor adapter.**

The first is #286's principle and it generalises past the FastAPI root that violates it: a
module that loads configuration and resolves secrets at import time cannot be imported by
tooling, by a test that wants the app object, or by a CI job that wants to prove the image's
dependencies import (#637) without standing up an environment first. The second is #301's:
the factory is where configuration selects the provider and flows into the adapter, which is
the whole point of ports and adapters. A root that constructs `RabbitMQAdapter(url=...)`
directly has re-implemented the factory's job in one place and will drift from it in the next
(#158/#299 externalised adapter timeouts to config and wired the factories; the roots that
bypass them never picked the setting up).

A reviewer's test for any future change to a root is the two questions these principles
give: *did this module merely define things at import?* and *did start-up select
infrastructure through a factory?*

## 2. Which modules are composition roots

The allowlist at `tests/unit/architecture/test_forbidden_imports.py:156` already names them
with the reason each wires infrastructure (#154):

| root | wires |
|---|---|
| `squadops.api.runtime` (`main`, `deps`, `scheduler_bootstrap`) | the runtime API: pool, queue, LLM, registries, vault, telemetry, tracker, events, executor, auth |
| `squadops.agents.entrypoint` | the agent container: queue, LLM, memory, prompts, telemetry, filesystem, messaging |
| `squadops.sandbox.main` | the sandbox service |
| `squadops.bootstrap` | system composition, the doctor's checks, the secrets provider |

**This standard adopts that list as the definition** rather than writing a second one. A new
root is a deliberate decision recorded in the allowlist with its reason, never a default; a
domain module reaching for an adapter fails the existing guard.

## 3. The kinds of binding a root performs — and what is not a binding

| kind | what it is | the rule |
|---|---|---|
| **provider-selected port binding** | a port with a factory under `adapters/<package>/factory.py` — fifteen exist: audit, auth, capabilities, comms, cycles, embeddings, events, llm, memory, prompts, sandbox, secrets, tasks, telemetry, tools | **delegated to the factory, with the selector read from typed config and required** (§4 R1, R2) |
| **substrate-bound persistence adapter** | a Postgres adapter constructed over the one pool — `PostgresAssignment`, `PostgresRuntimeActivity`, `PostgresFocusLease`, `PostgresRuntimeState`, `ChatRepository`, and the health checker's two | the substrate is selected once, at `adapters.persistence.pool.create_pool` (#577, guarded by `test_one_pool_factory.py`); the per-table adapters have no alternative substrate and are constructed **over that pool, in a root, under one lifecycle** (§4 R4) |
| **bootstrap reader** | a short-lived adapter a root constructs to *read* something it owns during composition — the YAML squad profile copied into Postgres at start-up (`main.py:295`), the doctor's read of the same file (`bootstrap/setup/checks.py:857`) | permitted **when all four hold**: it is short-lived; it is used only during composition or a bootstrap check; its result is copied into an authoritative store or reported, never handed to a domain or runtime consumer as the bound port; it binds no port a route or a handler later reads. A reader that outlives composition or is handed onward is a binding and R1 applies |
| **root-internal composer** | composition of ports that are already bound: `ReplyRouter` over the queue, `HealthChecker`, `create_runtime_coordinator`, `create_flow_executor` and the executor's own constructor (which builds `CorrectionRunner` at `dispatched_flow_executor.py:365` with an injectable override), the sandbox's `create_app(service, …)` | permitted in a root; it is what a root is for. **Two meanings of "factory", kept apart:** an *adapter factory* selects and binds an infrastructure provider and is governed by R1 and R2; an *application composer* such as `create_flow_executor` assembles collaborators from ports already bound and is governed by R4 only — no selector, because it selects nothing |

**Not a binding: a probe of a vendor.** The health checker's Redis client
(`main.py:472`) and the runtime's persistent broker connection (`main.py:569`, kept "like
agents do" so first use does not pay the connect) are the vendor itself, held for the purpose
of asking whether it is up. They bind no port and are outside R1. **A probe may inspect
vendor health; it may never be used by application behaviour as a substitute for the bound
port** — diagnostic use only, never a production message or query path. They are enumerated
in the guard's named exceptions (§6.5) so a new one is a decision.

## 4. The rules

- **R1 — factory-only construction.** Every adapter binding performed by a composition root
  is delegated to the owning adapter package's approved factory. A root never imports and
  instantiates a concrete vendor adapter. **This is the architecture invariant.** The guard
  proves it by AST today, and identifies "adapter" by whether the class implements a
  `squadops.ports` port — **that detection is a guard technique, not the definition of a
  binding**: an adapter that satisfies a port structurally, wraps another adapter, or
  inherits from no obvious interface is still a binding under this rule, and a guard that
  cannot see it is a guard defect, not a licence. The factory package's layout may evolve
  without amending this standard.
- **R2 — the selector is required, at every seam, even where one provider exists.** A
  selector at a composition seam is required configuration: no schema default, no factory
  default (the owner's ruling, 2026-08-28, #1157, SIP-0106 Ruling 3). The vocabulary lives in
  the config schema as a `Literal`; the mapping from name to class lives in the factory;
  neither lives in a root. **The SquadOps rule, stated rather than implied: every
  infrastructure port binding is explicit even when only one provider exists, because the
  selector records deployment intent, not merely a choice among alternatives.** A deployment
  that names its queue, its LLM and its messaging transport can be read, diffed and pinned;
  one that infers them from a default cannot. A port that exists for dependency direction
  alone and has one implementation still declares it. A factory that today defaults its
  selector (§7) is a masking fallback: a root passes the selector explicitly whether or not
  the factory would default it.
- **R3 — side-effect-free import.** A root module performs no configuration load, no secret
  resolution, no adapter construction and no network at import. Construction happens in an
  app or service factory called by the process entry point. **The sandbox root is the
  precedent** (`src/squadops/sandbox/main.py:29–52`): `sandbox_config_from_env()` reads the
  environment, `build_app()` calls it and `create_app(service, service_token=…)` composes —
  a bare `import squadops.sandbox.main` does nothing. The agent entrypoint already conforms
  (its only module-level statement is a logger). The runtime API does not (§5).
- **R4 — one authoritative binding lifecycle per port per process.** A root owns one
  lifecycle for each port it binds — construction, reconnection, lazy initialisation, pool
  recreation after failure all belong to that one binding — and consumers do not
  independently construct parallel bindings. The rule is about **ownership paths, not
  constructor counts**: a client that reconnects itself is one binding; a helper that builds
  a second `PostgresRuntimeState` "because it is stateless over the pool" has created a
  second ownership path the root cannot see (§7 names the one that exists).
- **R5 — tunables are not selectors.** Timeouts, prefetch counts and pool sizes are
  configuration a factory reads and may default in the schema (#158, #1147); the *provider*
  is the selector R2 governs. The two are not confused: a required selector with a defaulted
  timeout is correct.

## 5. Conformance on main `5c686cbd` (2026-09-09) — every binding, every root

| root | binding | today | rule | closed by |
|---|---|---|---|---|
| runtime API | LLM | `create_llm_provider(provider=config.llm.provider, …)` at `main.py:444–451` — selector required since #1157 | ✓ R1, R2 | — |
| runtime API | queue | **`RabbitMQAdapter(url=RABBITMQ_URL)` at `main.py:310`** — `get_queue_adapter` exists (`adapters/comms/factory.py:40`) and already requires a selector (`:29–31`); nothing calls it from a root | ✗ R1 | **#301** |
| runtime API | A2A client | **`A2AClientAdapter()` at `main.py:496`** — no factory exists; the timeouts are the constructor's defaults (`a2a_client.py:33–38`) | ✗ R1, R2 | **#301** |
| runtime API | project registry, cycle registry, squad profile, artifact vault, workflow tracker, event bus, LLM observability, flow executor | through `adapters.cycles.factory`, `workflow_tracker_factory`, `events.factory`, `telemetry.factory` (`main.py:284–411`) | ✓ R1 | — |
| runtime API | squad-profile YAML seed | `ConfigSquadProfile()` at `main.py:295` — a bootstrap reader by §3's four criteria: constructed to copy YAML into the Postgres profile once, never handed onward | ✓ bootstrap reader | — |
| runtime API | persistence over the pool | `create_pool` (#577) then the five Postgres adapters (`main.py:359–373`, `:472–477`, `:495`) | ✓ substrate-bound | — |
| runtime API | Redis client, broker connection | `main.py:472`, `:569` — vendor probes, diagnostic use | not a binding | — |
| runtime API | **import** | `configure_logging()`, `app = FastAPI(...)`, `register_domain_error_handlers(app)`, **`config = load_config(...)` at `main.py:57`**, the URL globals (`:60–61`), the fingerprint log, the auth and CORS middleware from `config.auth` (`:83–110`), the routers (`:113–156`) and the connection globals (`:159–163`) all execute at import; `tests/unit/cli/test_integration.py:57` works around it by setting env vars and popping `sys.modules` | ✗ R3 | **#286** |
| runtime API | the routes' dependency registry | `src/squadops/api/runtime/deps.py:30–60`: twenty module-global `_<port>` variables populated by `set_*` and read by `get_*` from ten route modules — **process-global by construction** | ✗ R4 (a second ownership path beside the app) | **named, §6.4 and §7 — not closed by #286** |
| agent entrypoint | LLM, memory, prompt repository, prompt asset source, telemetry, LLM observability | through their factories (`entrypoint.py:342–441`) | ✓ R1 | — |
| agent entrypoint | queue | **`RabbitMQAdapter(url=rabbitmq_url, prefetch_count=1)` at `entrypoint.py:453`** — `prefetch_count` is a tunable (#323), correctly a constructor argument; the binding is not | ✗ R1 | **#301** |
| agent entrypoint | filesystem | **`LocalFileSystemAdapter()` at `entrypoint.py:447`** while `adapters.tools.factory.create_filesystem_provider(provider, allowed_roots, production_mode)` exists — the same shape as the queue, found by this audit rather than by #301 | ✗ R1, R2 | **#301** |
| agent entrypoint | A2A server | **`A2AServerAdapter(...)` with `ChatAgentExecutor(...)` at `entrypoint.py:458–499`** behind `a2a_messaging_enabled` | ✗ R1 | **#301** |
| agent entrypoint | import | one module-level statement: `logger` | ✓ R3 | — |
| sandbox | service | `create_sandbox_service(config)`, `resolve_service_token(config)` (`sandbox/main.py:48–52`) | ✓ R1 | — |
| sandbox | import | `sandbox_config_from_env()` + `build_app()` — the precedent for R3 | ✓ R3 | — |
| bootstrap | secrets | `adapters.secrets.factory.create_provider` (`bootstrap/secrets.py:18–20`) — #154 moved it here from the config loader | ✓ R1 | — |
| bootstrap | the doctor's squad-profile read | `ConfigSquadProfile` at `bootstrap/setup/checks.py:857` — a bootstrap reader | ✓ bootstrap reader | — |

**Two of four roots conform today; the two that do not are the two with a container image.**

## 6. The decisions — what #286 and #301 build, and what the guard asserts

### 6.1 #301 closes on four bindings, not the two it names

**#301 is closed when, and only when, all four rows in §5 marked #301 conform:** the runtime
API's queue and A2A client, and the agent entrypoint's queue, filesystem adapter and A2A
server. The issue was filed naming the first two; this audit found the other two by reading
every binding in the root rather than the neighbourhood the issue described. A PR that
closes #301 against the original two examples has not closed it. The plan's row already
says "no vendor adapter class instantiated in either root"; this section makes the four
explicit so the acceptance cannot narrow to the examples.

### 6.2 The queue factory takes typed config, and the selector is named for the port it selects

`get_queue_adapter(profile: dict, secret_manager)` (`adapters/comms/factory.py:40`) reads a
**profile dictionary** — `profile["comms"]["provider"]`, `comms.url` — that predates the
typed config. The typed `CommsConfig` (`config/schema.py:164`) carries `rabbitmq: RabbitMQConfig`
and `redis: RedisConfig` and **no selector**; the loader resolves `secret://` before any
factory runs, so the `SecretManager` parameter is dead. Its only caller is
`tests/unit/adapters/test_queue_port.py`. Decision:

- **The selector is `comms.queue.provider`, not `comms.provider`.** `CommsConfig` holds three
  independent things — the queue, the A2A transport and Redis — and a selector named
  `comms.provider` would read as selecting all communications infrastructure when it selects
  only the queue. The legacy factory's name for it is an accident of the profile dictionary,
  and a standard normalises vocabulary rather than inheriting it. So `CommsConfig` gains
  `queue: QueueConfig(provider: Literal["rabbitmq"])` — **required, no default** (R2) — and
  the vendor sections stay where they are: `comms.rabbitmq.url` is the vendor's own settings,
  read by the factory when the selector names it, which keeps
  `SQUADOPS__COMMS__RABBITMQ__URL` untouched on every deployment. **The naming is a schema
  decision for the owner at this review**; the rule it follows — *selectors are named for
  the port, vendor settings for the vendor* — is the standard's.
- Rolled out the way #1157 rolled out `SQUADOPS__LLM__PROVIDER`: `SQUADOPS__COMMS__QUEUE__PROVIDER: rabbitmq`
  on every service in `docker-compose.yml` that sets the LLM selector today (eight; `:218`,
  `:277`, `:332`, `:406`, `:463`, `:516`, `:573`, `:632`), in `.env.example` beside `:62`, in
  every bootstrap profile and test environment that sets the LLM selector. **The
  `docker-compose.yml` edit is exactly the #1157 shape and is recorded on the PR for the
  owner's OK** (CLAUDE.md "Docker").
- The factory becomes `create_queue_adapter(comms: CommsConfig, *, prefetch_count: int | None = None) -> QueuePort`
  — the `create_*` name every other factory uses, one path, the profile-dict signature and
  its test ported rather than kept beside it (no dual paths). `prefetch_count` is a tunable
  (R5) passed by the agent root.
- Both roots call it: `main.py:310` and `entrypoint.py:453`.

### 6.3 The A2A factory, both halves, one selector

`adapters/comms/factory.py` gains `create_a2a_client(comms: CommsConfig) -> A2AClientPort` and
`create_a2a_server(comms: CommsConfig, *, executor, card) -> A2AServerPort` (the port names
follow whatever `squadops.ports` calls them today). Selector: `comms.a2a.provider: Literal["http"]`
— **required with one legal value, by R2's stated rule**: the selector records that this
deployment's agent messaging is the HTTP transport, and a second value (`disabled`, the NoOp
the always-inject pattern in `CLAUDE.md` names) is added when a root needs one, not
speculatively. The client's two timeouts (`a2a_client.py:33–38`) move to `comms.a2a` as
tunables with schema defaults (R5). The server half keeps `a2a_messaging_enabled` as the
agent-level switch it is today; the switch decides *whether* the root binds, the selector
decides *what*.

### 6.4 The filesystem adapter in the agent root goes through its factory

`create_filesystem_provider(provider, allowed_roots, production_mode)` exists
(`adapters/tools/factory.py:27`) and requires `allowed_roots` in production mode. The agent
root binds through it with `provider` read from a required `tools.filesystem.provider:
Literal["local"]` and `allowed_roots` from the agent's workspace configuration — the PR states
where that configuration lives today, since this audit did not find a `tools` section in
`config/schema.py`. If none exists, it is added with the selector required; the constructor
defaults the root relies on today are named in the PR.

### 6.5 The runtime app factory (#286), in the sandbox's shape — and what it does not fix

`src/squadops/api/runtime/main.py` becomes:

- `create_app(config: AppConfig) -> FastAPI` — pure composition: the `FastAPI` instance, the
  domain-error handlers, the middleware from `config.auth`, the routers, and the start-up and
  shutdown hooks that build the pool and the bindings §5 lists. Nothing reads the environment.
- `build_app() -> FastAPI` — the process entry point: `load_config(strict=..., secret_provider_factory=secret_provider_for)`
  then `create_app(config)`. The `strict` flag is read from the environment here and nowhere
  else.
- Module level: imports and `logger`. **A bare `import squadops.api.runtime.main` performs no
  configuration load, no secret resolution and no construction.**
- The connection and process objects (`pool`, `rabbitmq_connection`, `rabbitmq_channel`, the
  Redis client, the health checker instance, the reply router, the tracker, the coordinator)
  move from module globals onto `app.state`, FastAPI's own per-app holder, so an app's
  connections have the app's lifecycle and nothing else's.
- `src/squadops/api/runtime/Dockerfile:64` becomes
  `uvicorn squadops.api.runtime.main:build_app --factory --host 0.0.0.0 --port 8001`;
  `docker-compose.yml` is untouched (it names the image, not the module); the healthcheck
  (`:61`) is unchanged.
- `tests/unit/cli/test_integration.py`'s `_import_fastapi_app()` and its `_TEST_ENV` are
  **deleted**, and the test calls `create_app(test_config)` — the mirror rule: the workaround
  produced an app object under overridden env; `create_app` produces the same object from a
  config value, with no env and no `sys.modules` surgery.

**What #286 does not fix, stated so it is not claimed.** The routes do not read their ports
from `app.state`; they read them from `deps.py`'s module-global registry — twenty `_<port>`
variables, `set_*` at composition, `get_*` from ten route modules
(`src/squadops/api/runtime/deps.py:30–60`). After #286, `create_app` populates that registry,
which means **two apps in one process share one registry and the second `create_app`
overwrites the first's ports.** #286 therefore delivers import purity and app-owned
connections; **it does not deliver multi-app isolation, and this standard does not claim
it.** The registry is a second ownership path (R4) and is named in §7 with the follow-on
that closes it — the routes reading their ports through `Depends` from `request.app.state`,
which touches ten route modules and is its own change, not #286's.

### 6.6 What the guard asserts

One test module beside the existing architecture guards, in the shape of
`test_forbidden_imports.py` (AST over the roots' source, a named allowlist), with four
assertions — three prohibitions and **one positive presence check**, because "no direct
construction" also passes when a binding is deleted outright:

1. **Import purity (R3):** for each root in `COMPOSITION_ROOTS`, a subprocess
   `python -c "import <root>"` with an **empty environment** (no `SQUADOPS__*`, no
   `.env`) exits 0. The sandbox and agent roots pass today; the runtime root passes after
   #286; the bootstrap package is asserted too.
2. **Factory-only construction (R1):** within every module under a root, no call whose
   callee was imported from `adapters.<package>.<module>` with `<module> != factory`
   instantiates a class the guard identifies as an adapter (by port implementation today —
   the technique, not the rule). The named exceptions are a table in the test, each with its
   category from §3 and its reason: the substrate-bound Postgres adapters over the pool, the
   bootstrap readers, the root-internal composers, the two vendor probes. **A new exception
   is a deliberate decision recorded in the table**, the `COMPOSITION_ROOTS` precedent.
3. **Expected bindings are present and enter through their factory (R1, positive):** a table
   in the test declares, per root, the provider-selected bindings it is expected to perform —
   the runtime API: LLM, queue, A2A client, project registry, cycle registry, squad profile,
   artifact vault, workflow tracker, event bus, LLM observability, flow executor, auth; the
   agent entrypoint: LLM, queue, filesystem, memory, prompt repository, prompt asset source,
   telemetry, LLM observability, and the A2A server behind its switch; the sandbox: the
   service; bootstrap: secrets — and asserts **exactly one factory call per expected
   binding** in the root's source. A binding that vanishes fails CI as surely as one that
   bypasses its factory.
4. **The selector is required (R2):** for every factory a root calls, the config field the
   selector is read from has no default in `config/schema.py` — asserted from the Pydantic
   field definitions, so a schema default added later fails CI. Today that is
   `llm.provider`; after #301, `comms.queue.provider`, `comms.a2a.provider` and
   `tools.filesystem.provider`.

And the precedent kept: `test_the_two_named_leaks_are_closed` in `test_forbidden_imports.py`
names the sites #154 closed so the general allowlist cannot readmit them; the new guard adds
`main.py:310`, `:496`, `entrypoint.py:447`, `:453` and `:458` by name once #301 closes them.

**The invariant is the rule; the AST is today's proof.** If the factory package layout
changes — factories move into `adapters/<package>/__init__.py`, say — the guard's matcher
changes and this standard does not.

## 7. Known deviations, named — none closed by this line unless its row says so

- **The routes' dependency registry is process-global** (`deps.py:30–60`). After #286 it is
  populated by `create_app` and still shared by every app in the process (§6.5). The
  follow-on is the routes reading their ports through `Depends` from `request.app.state` —
  **#1448**, filed at this standard's review and placed by the 1.8 plan. Until it lands,
  **"one process, one runtime app" is a stated constraint, not an accident.**
- **Factory selector defaults.** **Eighteen selector parameters across eleven factory
  modules** default their provider (the exact table is in **#1449**; this document's first
  draft counted nine, which is the point — a default is invisible until it is looked for):
  audit (`"logging"`), project registry (`"config"`), cycle registry (`"memory"`), the flow
  executor and the event bus (`"in_process"`), capability repository, embeddings, memory,
  prompt repository and asset source, tasks (`"sql"`), four telemetry seams (`"otel"`,
  `"langfuse"`), filesystem (`"local"`), container (`"docker"`), vcs (`"git"`). R2 says the
  root passes the selector explicitly regardless; §5 confirms every root does. Removing the
  defaults themselves is #1449, placed by the 1.8 plan, not #301's scope.
- **A second ownership path for the runtime-state adapters.** `create_runtime_coordinator`
  (`scheduler_bootstrap`) builds `PostgresFocusLease` and `PostgresRuntimeState` again; the
  root's comment at `main.py:367–373` calls the instances interchangeable because they are
  stateless over the pool. That is true and it is still an R4 deviation — two paths own one
  binding. Named; not this line's.

## 8. What this standard does not decide

- Whether the runtime API's Prefect, Keycloak or LangFuse clients should gain NoOp
  implementations beyond the ones they have — that is each port's own question.
- The 1.8 question of which ports the Cross-Cycle Memory rails add; they will follow R1–R5
  when they do.
- The recovery extraction (`docs/plans/1-7-5-recovery-extraction-map.md`) — a different
  invariant, reviewed on its own.
