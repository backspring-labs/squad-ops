---
title: Edge Deployment Profile for Lightweight SquadOps Nodes
status: proposed
author: jladd
created_at: '2026-03-16T00:00:00Z'
---
# SIP: Edge Deployment Profile for Lightweight SquadOps Nodes

## Status
Proposed

## Summary

Introduce an `edge-nano` deployment profile for SquadOps that allows hardware-constrained nodes (initially a Jetson Nano) to participate as managed capability nodes. An edge node bootstraps from the main repo, deploys only targeted agents, connects to the Spark-hosted RabbitMQ broker as a remote AMQP client, and registers with the primary control plane for discovery and routing.

The first reference agent is an OpenClaw wrapper that translates SquadOps task envelopes into local OpenClaw HTTP API calls and returns structured results.

## SIP Relationships
- **Extends SIP-0081** (Profile-Driven Bootstrap): Adds `edge-nano` as a new bootstrap profile with reduced dependencies.
- **Extends SIP-0077** (Cycle Event System): Edge nodes emit registration/heartbeat events via the existing event bus.
- **Uses SIP-0062** (Auth Boundary): Edge nodes authenticate via Keycloak service account (client credentials grant).

## Problem

SquadOps assumes a rich runtime (Docker Compose with 17+ services, local Postgres, Redis, etc.). A Jetson Nano cannot run the full platform but should be able to host a specialized local runtime (OpenClaw) and expose it as a governed, discoverable SquadOps capability. No deployment profile exists for this use case.

## Goals

1. Add `edge-nano` as a bootstrap profile with minimal dependencies (Python, Docker, AMQP client — no local Postgres/Redis/Keycloak).
2. Implement an `EdgeNodeRegistryPort` so the primary control plane tracks edge node identity, capabilities, and health.
3. Deploy an OpenClaw wrapper agent on the Nano that consumes tasks via RabbitMQ and returns structured results.
4. Authenticate edge nodes via Keycloak service account — no interactive login.
5. Keep the edge runtime to a single agent container plus the local OpenClaw process.

## Non-Goals

1. Running any control-plane services (Postgres, Redis, runtime-api, Keycloak) on the edge node.
2. Multi-agent group chat or A2A messaging on edge nodes.
3. Agent-to-agent messaging without human intermediary.
4. Dynamic migration of arbitrary agents to edge — only explicitly configured agents deploy.
5. Local LLM inference on the Nano — the wrapper agent calls OpenClaw's local API, not an LLM.

---

## Design

### 1. Architecture

```text
[Primary Spark]
  Orchestration, RabbitMQ, Postgres, Redis,
  Keycloak, runtime-api, all squad agents
        |
        | TLS AMQP (5671) + HTTPS (Keycloak token endpoint)
        v
[Edge Nano]
  openclaw-wrapper agent container
  OpenClaw runtime (local process or container)
  edge-node-client (registration + heartbeat)
```

The edge node connects to the Spark-hosted RabbitMQ as a remote native AMQP client. It does not run its own broker. Registration and heartbeat go through the runtime-api over HTTPS.

### 2. EdgeNodeRegistryPort

A new port on the primary side tracks edge nodes. This is a primary-side port — edge nodes call it via runtime-api HTTP endpoints, not directly.

```python
class EdgeNodeRegistryPort(ABC):
    """Registry for edge node identity, capabilities, and health."""

    @abstractmethod
    async def register_node(self, registration: EdgeNodeRegistration) -> None:
        """Register or re-register an edge node. Idempotent by node_id."""

    @abstractmethod
    async def heartbeat(self, node_id: str, status: EdgeNodeStatus) -> None:
        """Update node health. Sets last_heartbeat_at and current status."""

    @abstractmethod
    async def deregister_node(self, node_id: str) -> None:
        """Mark node unavailable. Does not delete — preserves audit trail."""

    @abstractmethod
    async def get_node(self, node_id: str) -> EdgeNodeRegistration | None:
        """Return node registration or None if unknown."""

    @abstractmethod
    async def list_available_nodes(self) -> list[EdgeNodeRegistration]:
        """Return nodes with status READY and heartbeat within TTL."""
```

```python
@dataclass(frozen=True)
class EdgeNodeRegistration:
    node_id: str                          # e.g. "nano-01"
    hostname: str                         # e.g. "jetson-nano-01.local"
    deployment_profile: str               # "edge-nano"
    hardware_class: str                   # "jetson-nano", "jetson-orin", etc.
    agent_ids: list[str]                  # ["openclaw-wrapper"]
    capabilities: list[str]              # ["edge.openclaw.command", "edge.openclaw.chat"]
    concurrency_limit: int                # max simultaneous tasks
    status: str                           # STARTING | READY | DEGRADED | OFFLINE
    registered_at: datetime
    last_heartbeat_at: datetime | None
    metadata: dict[str, str]              # free-form (firmware version, IP, etc.)
```

### 3. OpenClaw Wrapper Agent

The wrapper is a standard `BaseAgent` subclass with a reduced `PortsBundle` (no memory, no prompt_service, no llm). It translates TaskEnvelopes into OpenClaw HTTP API calls:

```python
class OpenClawWrapperAgent(BaseAgent):
    """Edge agent wrapping a local OpenClaw runtime via HTTP."""

    def __init__(self, *, queue: QueuePort, metrics: MetricsPort,
                 events: EventPort, openclaw_url: str, **kwargs):
        super().__init__(
            llm=None, memory=None, prompt_service=None,
            queue=queue, metrics=metrics, events=events,
            filesystem=None, **kwargs,
        )
        self._openclaw_url = openclaw_url  # e.g. "http://localhost:8000"

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Route task to OpenClaw and normalize response."""
        # Map task_type to OpenClaw endpoint
        endpoint = _TASK_TYPE_TO_ENDPOINT[envelope.task_type]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._openclaw_url}{endpoint}",
                json={"input": envelope.payload},
                timeout=envelope.resolved_config.get("timeout_seconds", 120),
            )
            resp.raise_for_status()
        return TaskResult(
            task_id=envelope.task_id,
            status="completed",
            output=resp.json(),
        )
```

OpenClaw exposes an HTTP API (assumed at `http://localhost:8000`). The wrapper does not call an LLM — it translates between SquadOps task format and OpenClaw's REST interface. If OpenClaw's API shape differs, only `_TASK_TYPE_TO_ENDPOINT` and the request/response mapping change.

### 4. Bootstrap Profile

```yaml
# config/profiles/bootstrap/edge-nano.yaml
schema_version: 1
name: edge-nano
description: "Jetson Nano edge node — OpenClaw wrapper agent"

platform:
  os: linux
  distro: ubuntu
  distro_min_version: "20.04"

python:
  version: "3.11"
  manager: system        # Nano ships with system Python; no pyenv
  extras: []
  test_deps: null        # No test runner on edge

system_deps:
  - name: docker
    check: "docker --version"
    install: apt
    package: docker.io
    required: true
    confirm: false

docker_services: []      # No local services — connects to Spark's

ollama_models: []        # No local LLM

deployment_profile: edge
squad_profile: null      # No squad — single agent only
```

The bootstrap shell script for `edge-nano` installs Python 3.11, Docker, and pip dependencies from `requirements/edge.txt` (a minimal subset: `pika`, `httpx`, `pydantic`). It does NOT start Postgres, Redis, Keycloak, or any squad agents.

### 5. RabbitMQ Connectivity and Credentials

Edge nodes connect to the Spark-hosted RabbitMQ over TLS (port 5671). Credential provisioning:

1. **Primary-side setup** (one-time, maintainer): Create a scoped RabbitMQ user and vhost for edge nodes via `rabbitmqctl` or management API. The user has `configure` + `read` + `write` permissions scoped to `edge.*` queue/exchange patterns only.
2. **Edge-side config**: The bootstrap writes a `.env` file with `SQUADOPS__COMMS__RABBITMQ__URL=amqps://edge-nano-01:secret@spark.local:5671/edge`. The password is provisioned out-of-band (copied manually or via `scp` during bootstrap — no credential service on the Nano).
3. **TLS**: RabbitMQ on Spark exposes port 5671 with TLS. The edge node's `.env` includes `SQUADOPS__COMMS__RABBITMQ__CA_CERT=/etc/squadops/ca.pem`. Self-signed CA is acceptable for local network.

Queue declarations follow the existing idempotent pattern — the wrapper agent declares its queue (`edge.openclaw.tasks`) and binding on every startup.

### 6. Authentication

Edge nodes authenticate to the runtime-api (for registration/heartbeat) using a Keycloak **service account** (client credentials grant). No interactive login.

1. Maintainer creates a Keycloak client `edge-nano-01` with `Service Account Roles` enabled in the `squadops-dev` realm.
2. Client ID and secret are written to the edge node's `.env` during bootstrap.
3. The edge-node-client fetches a token from `https://spark.local:8180/realms/squadops-dev/protocol/openid-connect/token` on startup and refreshes it on expiry.
4. Registration and heartbeat calls include the bearer token. The runtime-api validates it via the existing auth middleware (SIP-0062).

### 7. Registration and Heartbeat

The `edge-node-client` is a lightweight Python process (or thread within the wrapper agent) that:

1. On startup: `POST /api/edge/nodes` with `EdgeNodeRegistration` payload. Idempotent by `node_id`.
2. Every 30s: `PUT /api/edge/nodes/{node_id}/heartbeat` with current status and task counts.
3. On shutdown (SIGTERM): `DELETE /api/edge/nodes/{node_id}` to mark offline.

The primary-side registry marks a node `OFFLINE` if no heartbeat is received within 90s (3x interval). The orchestrator skips offline nodes when routing tasks.

### 8. Readiness Model

Two-tier readiness, both required before routing:

| Layer | Condition | Checked by |
|-------|-----------|------------|
| **Messaging** | AMQP connected, queue declared, consumer active | Wrapper agent (local) |
| **Platform** | Registered, heartbeat current, status READY | Primary registry (TTL-based) |

The wrapper agent does not set status to READY until both its RabbitMQ consumer is active AND the local OpenClaw health endpoint (`GET /health`) responds 200.

### 9. Chat Persistence (DDL)

```sql
-- infra/migrations/007_edge_node_registry.sql
-- SIP-EDGE-NANO: Edge node registration and health tracking

CREATE TABLE edge_nodes (
    node_id         TEXT PRIMARY KEY,
    hostname        TEXT NOT NULL,
    deployment_profile TEXT NOT NULL DEFAULT 'edge-nano',
    hardware_class  TEXT NOT NULL,
    agent_ids       JSONB NOT NULL DEFAULT '[]',
    capabilities    JSONB NOT NULL DEFAULT '[]',
    concurrency_limit INT NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'STARTING'
                    CHECK (status IN ('STARTING', 'READY', 'DEGRADED', 'OFFLINE')),
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_heartbeat_at TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_edge_nodes_status ON edge_nodes(status);
```

### 10. Docker Compose (Edge-Side)

The edge node uses a separate `docker-compose.edge.yaml` (not the primary `docker-compose.yml`):

```yaml
# docker-compose.edge.yaml — runs on the Jetson Nano
services:
  openclaw-wrapper:
    build:
      context: .
      dockerfile: agents/edge/Dockerfile
      args:
        AGENT_ROLE: openclaw_wrapper
    container_name: squadops-openclaw-wrapper
    restart: unless-stopped
    environment:
      SQUADOPS__AGENT__ID: openclaw-wrapper
      SQUADOPS_AGENT_ROLE: openclaw_wrapper
      SQUADOPS__COMMS__RABBITMQ__URL: "${SQUADOPS__COMMS__RABBITMQ__URL}"
      SQUADOPS__EDGE__OPENCLAW_URL: "http://host.docker.internal:8000"
      SQUADOPS__EDGE__NODE_ID: "${SQUADOPS__EDGE__NODE_ID}"
      SQUADOPS__EDGE__RUNTIME_API_URL: "${SQUADOPS__EDGE__RUNTIME_API_URL}"
      SQUADOPS__AUTH__CLIENT_ID: "${SQUADOPS__AUTH__CLIENT_ID}"
      SQUADOPS__AUTH__CLIENT_SECRET: "${SQUADOPS__AUTH__CLIENT_SECRET}"
      SQUADOPS__AUTH__TOKEN_URL: "${SQUADOPS__AUTH__TOKEN_URL}"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    network_mode: host  # Simplifies Nano networking — no docker network needed
```

OpenClaw itself runs as a host process (not in Docker) since it may need direct hardware access. The wrapper container reaches it via `host.docker.internal` or `localhost` (with `network_mode: host`).

---

## Key Design Decisions

### D1: Edge as Managed Capability Node, Not Peer
Edge nodes are not reduced control planes. They do not run Postgres, Redis, Keycloak, or runtime-api. They connect to existing infrastructure on the Spark. This keeps the edge footprint minimal and avoids split-brain scenarios.

### D2: Native Remote AMQP, Not Bridge
Edge agents connect directly to the Spark's RabbitMQ over TLS as remote AMQP clients. No message bridge, no local broker. This reuses the existing RabbitMQ adapter (`adapters/comms/rabbitmq.py`) with only a connection URL change.

### D3: Keycloak Service Account for Auth
Edge nodes use OAuth2 client credentials (not interactive login). The maintainer provisions a Keycloak client per edge node. Credentials are injected via `.env` during bootstrap — no credential service runs on the Nano.

### D4: Scoped RabbitMQ Permissions
Edge users have permissions scoped to `edge.*` patterns. An edge node cannot declare or consume queues belonging to primary agents. This is enforced at the broker level, not application level.

### D5: Primary-Side Registry in Postgres
Edge node registration lives in the primary Postgres (table `edge_nodes`). The runtime-api exposes CRUD + heartbeat endpoints. No new service — these are routes on the existing API.

### D6: Heartbeat-Based Liveness
30s heartbeat interval, 90s TTL. Missed heartbeats mark the node OFFLINE. The orchestrator filters out offline nodes before routing. No complex consensus — simple TTL expiry.

### D7: Wrapper Agent Uses BaseAgent, Not LLM
The OpenClaw wrapper extends `BaseAgent` but passes `llm=None`. It is a protocol translator (TaskEnvelope → HTTP → TaskResult), not a generative agent. This keeps the edge dependency set minimal.

### D8: Separate docker-compose.edge.yaml
Edge nodes do not use the primary `docker-compose.yml`. A dedicated `docker-compose.edge.yaml` defines only the wrapper container. This avoids accidental startup of primary services on constrained hardware.

### D9: One Wrapper Agent per Edge Profile (v1)
v1 supports one agent per edge node. Multi-agent edge nodes are future work — the `agent_ids` list in the registry supports it, but the bootstrap and compose file wire exactly one agent.

### D10: OpenClaw HTTP API Assumption
The wrapper assumes OpenClaw exposes a local HTTP API. If OpenClaw is CLI-only, the wrapper shells out via `subprocess` instead. The adapter boundary is in the wrapper agent, not in a port — OpenClaw is a local detail, not a SquadOps abstraction.

---

## File-Level Design

### New Files

| File | Purpose |
|------|---------|
| `src/squadops/ports/edge/node_registry.py` | `EdgeNodeRegistryPort` abstract interface |
| `src/squadops/edge/models.py` | `EdgeNodeRegistration`, `EdgeNodeStatus` frozen dataclasses |
| `adapters/edge/postgres_node_registry.py` | Postgres adapter for `EdgeNodeRegistryPort` |
| `src/squadops/agents/edge/openclaw_wrapper.py` | `OpenClawWrapperAgent(BaseAgent)` — task-to-HTTP translator |
| `src/squadops/agents/edge/node_client.py` | Registration + heartbeat client (calls runtime-api) |
| `src/squadops/api/routes/edge/routes.py` | Edge node API routes (register, heartbeat, list, deregister) |
| `src/squadops/api/routes/edge/dtos.py` | Edge DTOs: `EdgeNodeRegistrationRequest`, `EdgeNodeDTO` |
| `infra/migrations/007_edge_node_registry.sql` | DDL for `edge_nodes` table |
| `config/profiles/bootstrap/edge-nano.yaml` | Bootstrap profile for Jetson Nano |
| `scripts/bootstrap/profiles/edge-nano.sh` | Bootstrap shell script for edge profile |
| `agents/edge/Dockerfile` | Minimal Dockerfile for edge wrapper agent |
| `docker-compose.edge.yaml` | Edge-side compose file (wrapper container only) |
| `requirements/edge.txt` | Minimal pip deps: pika, httpx, pydantic |

### Modified Files

| File | Change |
|------|--------|
| `src/squadops/api/main.py` | Mount edge routes (`/api/edge/`) |
| `agents/instances/instances.yaml` | Add `openclaw-wrapper` instance (role: `edge_wrapper`, enabled: false by default) |
| `src/squadops/agents/base.py` | Allow `llm=None` in BaseAgent constructor (guard existing property) |
| `src/squadops/bootstrap/setup/profile.py` | No changes needed — schema already supports the edge-nano.yaml shape |
| `scripts/bootstrap/bootstrap.sh` | Add `edge-nano` to recognized profile list |

### Files NOT Modified

| File | Reason |
|------|--------|
| `docker-compose.yml` | Edge nodes use separate `docker-compose.edge.yaml` (D8) |
| `adapters/comms/rabbitmq.py` | Reused as-is — only the connection URL differs |
| `src/squadops/cycles/` | No cycle model changes — edge tasks use existing TaskEnvelope |
| `src/squadops/capabilities/handlers/` | No handler changes — wrapper agent handles its own task routing |

---

## Implementation Phases

### Phase 1: Foundation — Profile, Port, DDL
- Add `edge-nano.yaml` bootstrap profile and shell script
- Implement `EdgeNodeRegistryPort` and `EdgeNodeRegistration` model
- Implement Postgres adapter (`edge_nodes` table, DDL migration 007)
- Add `requirements/edge.txt`
- Tests: profile validation, port contract, registry adapter CRUD, heartbeat TTL

### Phase 2: Wrapper Agent and Edge Entrypoint
- Implement `OpenClawWrapperAgent(BaseAgent)` with HTTP-based task handling
- Implement `edge-node-client` (registration + heartbeat against runtime-api)
- Create `agents/edge/Dockerfile` and `docker-compose.edge.yaml`
- Wire Keycloak service account token fetch
- Tests: wrapper unit tests with mock OpenClaw HTTP, node client registration/heartbeat, auth token refresh

### Phase 3: Runtime-API Routes and Routing
- Add edge node API routes (register, heartbeat, list available, deregister)
- Add DTOs and mapping
- Wire orchestrator to filter out offline edge nodes when routing tasks
- Tests: route tests, availability filtering, heartbeat expiry

### Phase 4: E2E Validation
- Bootstrap a Jetson Nano with `edge-nano` profile
- Deploy OpenClaw wrapper, connect to Spark RabbitMQ
- Send a task from primary, verify round-trip through OpenClaw
- Validate registration, heartbeat, and offline detection
- Version bump, SIP promotion

---

## Acceptance Criteria

1. `squadops bootstrap edge-nano` installs minimal deps and does NOT start Postgres/Redis/Keycloak.
2. `squadops doctor edge-nano` validates Python, Docker, AMQP connectivity, and OpenClaw health.
3. Edge wrapper agent starts, declares `edge.openclaw.tasks` queue on Spark's RabbitMQ, and consumes tasks.
4. `POST /api/edge/nodes` registers the edge node; `GET /api/edge/nodes` returns it with status READY.
5. Missed heartbeats (>90s) cause the node status to transition to OFFLINE.
6. A task routed to the edge agent returns a structured `TaskResult` with OpenClaw output.
7. Edge RabbitMQ user cannot access non-`edge.*` queues (broker-level enforcement).
8. Keycloak service account token authenticates edge API calls through existing auth middleware.

---

## Risks

### A1: OpenClaw API Instability
OpenClaw's HTTP API may change. **Mitigation**: The wrapper's `_TASK_TYPE_TO_ENDPOINT` mapping isolates SquadOps from OpenClaw's API shape. Changes are confined to the wrapper agent.

### A2: Network Reliability (Nano ↔ Spark)
WiFi or LAN flakiness may cause AMQP disconnects. **Mitigation**: `pika`'s built-in connection recovery handles reconnects. Heartbeat TTL (90s) tolerates brief outages without marking the node offline.

### A3: Nano Resource Constraints
Docker + Python + OpenClaw on a 4GB Nano is tight. **Mitigation**: The wrapper agent is minimal (no LLM, no memory, no prompt service). `docker-compose.edge.yaml` runs a single container. Monitor memory during Phase 4 E2E and adjust concurrency_limit accordingly.

### A4: Credential Provisioning is Manual
v1 requires manually copying RabbitMQ and Keycloak credentials to the Nano. **Mitigation**: Acceptable for a single-device lab setup. A future SIP can add a credential enrollment flow if edge nodes scale beyond 2-3 devices.
