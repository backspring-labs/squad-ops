# ✅ Nexa Squad Tool-Shed Protocol (v1.1)

------------------------------------------------------------------------

## 📌 Purpose

Define a standardized protocol for **arming agents with tools** so they
can execute tasks effectively. This covers how tools are **registered,
accessed (API, CLI, MCP, etc.), governed, and audited** within SquadOps,
ensuring consistency, security, and traceability across the squad.

------------------------------------------------------------------------

## ✅ Protocol Objectives

-   Centralize tool definitions in a **Tool-Shed Registry**.
-   Support multiple **access patterns**: direct API, CLI bridge,
    message bus, data-plane connector, MCP, or adapter microservices.
-   Enforce **auth, secrets, and permissions** per agent.
-   Guarantee **traceability**: every tool invocation logs to the
    PID/task ledger.
-   Enable **governance checks** (via Max) for usage, cost, and
    compliance.
-   Ensure **observability**: success/failure, latency, cost, and audit
    trails.
-   Bake in **failure-mode mitigations** as explicit requirements.

------------------------------------------------------------------------

## ✅ Access Patterns

  -------------------------------------------------------------------------
  Access Type       When to Use       Example Tools        Guardrails
  ----------------- ----------------- -------------------- ----------------
  **Direct API**    Full-featured     GitHub, Flagsmith,   OAuth2, PATs,
                    vendor APIs       PostHog              rate-limits

  **CLI Bridge      CLI-first tools   Git, Docker, k6,     Run in
  (Sidecar)**                         nmap                 container, wrap
                                                           with RPC shim

  **Message-Bus     Batchy or async   Long tests, report   Correlation IDs,
  Tooling**         jobs              generation           retries, DLQs

  **Data-Plane      Databases /       Postgres,            Service
  Connectors**      storage           TimescaleDB, MinIO   accounts, schema
                                                           RBAC

  **MCP (Model      Strict schemas +  `open_pr`,           Input
  Context           discoverability   `create_flag`,       validation,
  Protocol)**                         `emit.event`         quotas

  **Adapter         Multi-step        Feature flag         Versioned
  Microservice**    orchestration     seeding,             endpoints,
                    hidden from       provisioning flows   synthetic tests
                    agents                                 
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## ✅ Tool-Shed Registry (Canonical Record)

Every tool must be registered with the following fields:

  -----------------------------------------------------------------------
  Field                    Description
  ------------------------ ----------------------------------------------
  **Tool ID & Version**    `flagsmith@2.3.1`, `github@v1.0`

  **Category**             Security, Testing, Analytics, VCS, Deployment,
                           Creative

  **Access Pattern**       api / cli-bridge / bus / dataplane / mcp /
                           adapter

  **Endpoint / Address**   URL, queue/topic, or local socket

  **Auth Method**          oauth2_client / api_key / service_account /
                           none

  **Input/Output Schemas** Summary or JSON schema (MCP if applicable)

  **Latency Class**        sync (\<5s), near-sync (≤60s), async (\>60s)

  **Cost Class**           free / metered / premium

  **SLAs & Timeouts**      Defaults, retries, circuit breakers

  **Owner Agent**          Governance responsibility

  **Permissions**          Agents allowed to call it
  -----------------------------------------------------------------------

> **Format:** Store as `tool_shed.yaml` under `/infra/tools/` and
> version in Git.

------------------------------------------------------------------------

## ✅ Security & Permissions (Requirements)

-   Each agent must have its own scoped service account (no shared
    credentials).
-   Secrets must be mounted via Vault/Keycloak, never checked into Git.
-   All tokens must be short-lived (OAuth2, JWT) and auto-rotated.
-   Logs must redact any sensitive values.

------------------------------------------------------------------------

## ✅ Concurrency & Blocking (Requirements)

-   CLI tools must be wrapped in checkpoint-safe async adapters.
-   Long-running tools must implement checkpoints at least every 5
    minutes.
-   Tool sidecars must enforce timeouts and exponential backoff retries.
-   Urgent governance signals (`suspend`, `redirect`) must preempt
    blocking tasks.

------------------------------------------------------------------------

## ✅ Observability & Traceability (Requirements)

-   Every tool call must log: `pid`, `task_id`, `tool_id@version`,
    timestamp, success/failure, and latency.
-   Output artifacts must be registered in Postgres/MinIO and tied to
    the PID registry.
-   Data lineage must be updated when new tools produce or transform
    KDEs.
-   SOC UI must display per-tool invocation stats.

------------------------------------------------------------------------

## ✅ Cost & Resource Control (Requirements)

-   Each tool must declare a `cost_class` (`free|metered|premium`).
-   Quark enforces daily/weekly ceilings for premium tools.
-   GPU-heavy tools must declare `resource_profile`, and SOC must
    enforce scheduling fairness.
-   Premium tool calls must support a "dry-run" estimate for budget
    checks before execution.

------------------------------------------------------------------------

## ✅ Versioning & Compatibility (Requirements)

-   All tools pinned by semantic version (`tool@1.2.3`).
-   Breaking changes must increment `tool_id` or schema version.
-   WarmBoot runs must validate tool versions before merging to `main`.
-   Registry changes must flow through Git workflow branches:
    `feature/tool-upgrade-*`.

------------------------------------------------------------------------

## ✅ Invocation Lifecycle

1.  **Discover** tool from registry.\
2.  **Authorize** (fetch token/secret).\
3.  **Contract-check** (schema validation).\
4.  **Invoke** with `correlation_id` + `idempotency_key`.\
5.  **Record** success/failure, latency, cost, tied to PID/task log.\
6.  **Recover** with retries/backoff; escalate to Max if repeated
    failures.

------------------------------------------------------------------------

## ✅ Agent Loadouts (Examples)

  ----------------------------------------------------------------------------------
  Agent            Tooling        Access Pattern        MCP Exposed Actions
  ---------------- -------------- --------------------- ----------------------------
  **Max            Prefect API,   Direct API + Bus      `status.query`,
  (Governance)**   RMQ admin,                           `task.redirect`,
                   Keycloak                             `suspend.agent`

  **Neo (Dev)**    GitHub API,    API + CLI bridge      `open_pr`, `toggle_flag`
                   Flagsmith,                           
                   Docker CLI                           

  **EVE (QA/Sec)** OWASP ZAP, k6, CLI bridge + API      `run_regression`,
                   Burp Suite                           `run_pentest`

  **Data           PostHog,       API + DB connector    `kpi.snapshot`, `emit.event`
  (Analytics)**    TimescaleDB,                         
                   MinIO                                

  **Quark          Billing        API + DB connector    `budget.check`,
  (Finance)**      meters,                              `budget.lock`
                   Postgres                             
                   ledger                               

  **Glyph          SDXL API,      Direct API            `generate.asset(spec)`
  (Creative)**     MinIO store                          

  **Nat / Joi /    Knowledge      API + microservices   `search.knowledge`,
  Og**             indices,                             `summarize.context`
                   search                               
                   adapters                             
  ----------------------------------------------------------------------------------

------------------------------------------------------------------------

## ✅ Governance & Observability

-   Quark enforces ceilings and tracks premium costs.\
-   Max validates registry completeness before WarmBoot runs.\
-   Data ensures KDEs and lineage are updated with new tools.\
-   Every invocation is stored in the task ledger (Postgres +
    Prometheus).\
-   Alerts trigger on SLA breach, cost overrun, repeated tool errors.

------------------------------------------------------------------------

## ✅ Failure Modes & Safeguards

-   **Agent offline** → requests queued, retried with DLQ handling.\
-   **Tool storm** → SOC rate-limits and prioritizes governance
    signals.\
-   **Governance conflicts** → last-write-wins with audit trail and
    reason code.\
-   **Breaking changes** → new tool_id/version, enforced by Max before
    merge.

------------------------------------------------------------------------

## ✅ Future Enhancements

-   Auto-discovery of MCP tools at squad boot.\
-   Dynamic cost optimization (route to cheapest provider).\
-   Simulation mode for tool invocation replay.\
-   Auto-scaling CLI bridges for heavy workloads.

------------------------------------------------------------------------

> This protocol ensures agents are **armed with the right tools,
> securely and consistently**, with mitigations encoded as requirements
> for governance, traceability, cost control, and safety.
