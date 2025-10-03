# SquadOps Cloud Deployment Guide — Base Infra + AWS + GCP + Azure

This guide describes a portable **base infrastructure** for SquadOps and three cloud reference paths (**AWS, GCP, Azure**) that preserve **SquadNet** semantics, PID/WB/CHK traceability, and your incremental build strategy (HelloSquad → full squad).

---

## 0) Core Concepts (applies everywhere)

- **SquadNet (AMQP)**: Agents communicate over RabbitMQ-style exchanges/queues. Keep JSON envelopes (`TASK_ASSIGNMENT`, `STATUS`, `VERDICT`) identical across environments.
- **Traceability**: Every run carries `pid`, `pid_version`, `warmboot_id (WB-xxx)`, and `checkpoint_id (CHK-xxx)` into logs and artifacts.
- **Routable rules**: `status==online && llm_mode==real && accept_tasks!=false` (Lead computes). Health UI shows **status**, **MOCK** pill, **PAUSED** pill, derived **ROUTABLE**.
- **Composition**: One **base compose** + small **overrides** per environment. Build locally; publish multi-arch images for cloud.

---

## 1) Base Infra (portable / local-first)

### Services
- **Lead** (Max) — orchestrates tasks, verifies
- **Dev** (Neo) — implements HelloSquad app
- **HelloSquad App** — `/api/hello` (JSON), `/hello` (HTML fetches API)
- **RabbitMQ** — SquadNet broker (local only)
- **Postgres** — task & message logs (local only)

### Files & structure
```
/docker/
  compose.yml            # portable base
  compose.local.yml      # local-only: build, volumes, local RMQ/PG
  compose.aws.yml        # AWS override
  compose.gcp.yml        # GCP override
  compose.azure.yml      # Azure override
.env                     # shared defaults
.env.local               # local-only
.env.aws                 # AWS env (non-secrets)
.env.gcp                 # GCP env (non-secrets)
.env.azure               # Azure env (non-secrets)
```

### Base compose (sketch)
- All services declared with **env placeholders**; **RabbitMQ** and **Postgres** enabled by default for local.
- Health checks on `/health` for agents and app.
- App publishes a single port locally (`8080`), removed in cloud (LB handles).

---

## 2) AWS Reference Path (HelloSquad → full squad)

### Managed building blocks
- **Compute**: ECS on Fargate (one service per agent + app)
- **Messaging**: **Amazon MQ (RabbitMQ engine)** (keeps AMQP semantics intact)
- **Database**: Amazon **RDS for PostgreSQL**
- **Models**: **Amazon Bedrock** (Claude, Llama, Mistral, etc.)
- **Secrets/Config**: Secrets Manager + SSM Parameter Store
- **Networking**: VPC (private subnets for services; ALB public for app)
- **Logs/Metrics**: CloudWatch Logs/Metrics

### Model picks (dev-friendly)
- Lead: **Claude 3 Haiku** or **Claude 3.5 Sonnet** (governance/planning)
- Dev: **Llama 3 8B Instruct** or **Mistral Small**

### Env hints
```
MODEL_PROVIDER=bedrock
MODEL_PRIMARY_LEAD=bedrock:claude-3-haiku
MODEL_PRIMARY_DEV=bedrock:llama3-8b-instruct
RMQ_URL=amqps://<user>:<pass>@<amazon-mq-endpoint>:5671/<vhost>
PG_URL=postgres://<user>:<pass>@<rds-endpoint>:5432/squadops
LLM_MODE=real
```

### Notes
- Use **task roles** (no API keys in env) for Bedrock + Secrets Manager.
- Keep **DLQ/retry topology** identical to local.
- Record **WB-00N** + **CHK-00N** per phase.

---

## 3) GCP Reference Path (HelloSquad → full squad)

### Managed building blocks
- **Compute**: **Cloud Run** (fastest path) or **GKE Autopilot** (single cluster, more control)
- **Messaging**: **Managed RabbitMQ on GCP** (AMQP parity)
- **Database**: **Cloud SQL for PostgreSQL** (private IP)
- **Models**: **Vertex AI** (Gemini, Claude, Llama, Mistral, etc.)
- **Secrets/Config**: **Secret Manager** (+ Workload Identity)
- **Networking**: VPC + Serverless VPC Connector (Cloud Run) or native GKE
- **Logs/Metrics**: Cloud Logging/Monitoring

### Model picks (dev-friendly)
- Lead: **Gemini 1.5 Flash** or **Claude 3 Haiku**
- Dev: **Llama 3 8B Instruct** or **Mistral Small**

### Env hints
```
MODEL_PROVIDER=vertex
MODEL_PRIMARY_LEAD=vertex:gemini-1.5-flash
MODEL_PRIMARY_DEV=vertex:llama-3-8b-instruct
RMQ_URL=amqps://<user>:<pass>@<gcp-rabbitmq-endpoint>:5671/<vhost>
PG_URL=postgresql://<user>:<pass>@<cloudsql-ip>:5432/squadops
LLM_MODE=real
```

### Notes
- Prefer **Cloud Run** to start; graduate to **GKE** for sidecars/advanced net.
- Export logs to **BigQuery** optionally for analytics.

---

## 4) Azure Reference Path (HelloSquad → full squad)

### Managed building blocks
- **Compute**: **Azure Container Apps (ACA)** (simple) or **AKS** (more control)
- **Messaging**: **RabbitMQ** via **Azure Marketplace managed offering** *or* run RabbitMQ as a container on ACA/AKS for full AMQP parity
  - (Avoid switching to Service Bus if you want to keep AMQP envelopes/acks/routing keys unchanged.)
- **Database**: **Azure Database for PostgreSQL – Flexible Server**
- **Models**: **Azure OpenAI** (GPT‑4o/4.1, etc.) and **Models on Azure AI** (serverless hosted Llama/Mistral/Phi via Azure AI Foundry)
- **Secrets/Config**: **Azure Key Vault** + **Managed Identity**
- **Networking**: VNets + **ACA Environment** or AKS VNet; **Azure Front Door** or **Application Gateway** for public app
- **Logs/Metrics**: **Azure Monitor / Log Analytics**

### Model picks (dev-friendly)
- Lead: **gpt‑4o‑mini** (fast) or **gpt‑4.1** via Azure OpenAI
- Dev: **Llama 3 8B Instruct** or **Phi‑3** via Azure AI Models-as-a-Service

### Env hints
```
MODEL_PROVIDER=azureai
MODEL_PRIMARY_LEAD=azureopenai:gpt-4o-mini
MODEL_PRIMARY_DEV=azureai:llama-3-8b-instruct
RMQ_URL=amqps://<user>:<pass>@<azure-rabbitmq-endpoint>:5671/<vhost>
PG_URL=postgres://<user>:<pass>@<flexible-server-host>:5432/squadops
LLM_MODE=real
```

### Notes
- Use **Managed Identity** to fetch secrets from Key Vault; avoid raw keys.
- If using **RabbitMQ on ACA/AKS**, expose internally; agents reach it via VNet.
- Keep DLQ/retry bindings identical to local.

---

## 5) Portable Compose Strategy

- **Base** (`compose.yml`): service names, health checks, env placeholders.
- **Local override** (`compose.local.yml`): `build:`, bind mounts, local RMQ/PG endpoints.
- **AWS/GCP/Azure overrides**: switch to **prebuilt images** (ECR/Artifact Registry/ACR), remove host ports, wire managed endpoints, set cloud logging drivers.

**Local run**
```
docker compose -f docker/compose.yml -f docker/compose.local.yml --env-file .env.local up --build
```

**Cloud CI**
1) Build & push multi-arch images (arm64) to **ECR / Artifact Registry / ACR**.
2) Freeze image tags & digests in **checkpoint manifest** (PID versioned).
3) Deploy via IaC (Terraform/CFN; Cloud Deploy/TF; Bicep/ARM/Terraform).
4) Smoke tests → record **WB-xx / CHK-xx**.

---

## 6) Env Var Matrix (shared vs cloud-specific)

**Shared (all envs)**
```
PID=PID-001
PID_VERSION=v0.1.0
WARMBOOT_ID=WB-00N
CHECKPOINT_ID=CHK-00N

ROLE=lead|dev|qa|...
AGENT_ID=max|neo|...
LLM_MODE=real|mock
MODEL_PROVIDER=bedrock|vertex|azureai
MODEL_PRIMARY=<provider:model-id>
ACCEPT_TASKS=true|false
CAPACITY=1
```

**Local**
```
RMQ_URL=amqp://guest:guest@rabbitmq:5672/
PG_URL=postgres://postgres:postgres@postgres:5432/squadops
```

**AWS**
```
RMQ_URL=amqps://<user>:<pass>@<amazon-mq-endpoint>:5671/<vhost>
PG_URL=postgres://<user>:<pass>@<rds-endpoint>:5432/squadops
MODEL_PROVIDER=bedrock
BEDROCK_REGION=us-east-1
```

**GCP**
```
RMQ_URL=amqps://<user>:<pass>@<gcp-rabbitmq-endpoint>:5671/<vhost>
PG_URL=postgresql://<user>:<pass>@<cloudsql-ip>:5432/squadops
MODEL_PROVIDER=vertex
VERTEX_REGION=us-central1
```

**Azure**
```
RMQ_URL=amqps://<user>:<pass>@<azure-rabbitmq-endpoint>:5671/<vhost>
PG_URL=postgres://<user>:<pass>@<flexible-server-host>:5432/squadops
MODEL_PROVIDER=azureai
AZURE_REGION=eastus
```

*Use cloud-native identity (task role, Workload Identity, Managed Identity) to access model endpoints and secrets; avoid embedding long‑lived keys.*

---

## 7) Incremental Rollout (all clouds)

- **Phase 1**: Base infra + mock agents → `WB-001 Infra Baseline` → `CHK-001`
- **Phase 2**: HelloSquad (Lead+Dev, real LLMs) → `WB-00N` → `CHK-00N`
- **Phase 3**: Add agents one-by-one (QA, Data, Finance, Comms, Curator, Creative, Audit)
  - Bump **PID version** each step
  - Re-run **warm-boot** for squad tuning
  - Capture a **checkpoint** per increment
- **Phase 4**: Full squad reference app
- **Phase 5**: Next PID (e.g., Personal Fitness) using the proven squad profile

---

## 8) SquadNet Parity Checklist (applies to AWS/GCP/Azure)

- Broker provides **RabbitMQ AMQP 0‑9‑1** (managed or self-hosted).
- Same **exchanges/queues/bindings** (retry, DLQ) and **routing keys**.
- **TLS (5671)**; heartbeat 30–60s; reasonable connection timeout.
- Health endpoints unchanged; message schema unchanged.
- Large artifacts go to object storage; messages carry storage pointers.

---

## 9) Cost‑Control Defaults (dev/staging)

- Prefer smallest managed DB tiers (RDS/Cloud SQL/Azure PG Flexible). Serverless where available.
- Smallest managed RabbitMQ tier; alert on queue depth/conn count.
- Use **fast/cheap models** by default (Gemini Flash / Claude Haiku / Llama 3 8B / Phi‑3).
- Enable **scale-to-zero** on serverless compute (Cloud Run/Container Apps) for non-critical agents.

---

## 10) What changes when growing to a full squad?

Very little at the protocol level:
- Each new agent is **just another service** with the same env shape and SquadNet bindings.
- Lead’s routing policy stays the same; HAL’s audit gates stay the same.
- You primarily add **queues**, **env secrets**, and **model policies** per agent.

---

**That’s it.** This guide is designed to be dropped into `/docs/` and used as the cloud playbook for SquadOps while keeping local development simple and faithful.
