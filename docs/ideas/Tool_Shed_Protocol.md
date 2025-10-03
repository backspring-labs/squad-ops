# ✅ Nexa Squad Tool-Shed Protocol (v1.0)

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

## ✅ Auth & Secrets

-   Per-agent **service accounts**, never shared.
-   **Short-lived tokens** (OAuth2, JWT).
-   Secrets mounted via Vault/Keycloak, never in env files in Git.
-   Policy-driven RBAC: "who can call what" centralized, enforced at
    runtime.

------------------------------------------------------------------------

## ✅ Invocation Lifecycle

1.  **Discover** tool from registry.\
2.  **Authorize** (fetch token/secret).\
3.  **Contract-check** (schema validation).\
4.  **Invoke** with `correlation_id` + `idempotency_key`.\
5.  **Record** success/failure, latency, cost, tied to PID/task log.\
6.  **Recover**: retries/backoff, escalate to Max if repeated failures.

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

-   **Quark**: enforces daily cost ceilings.\
-   **Max**: validates tool registry completeness before WarmBoot runs.\
-   **Data**: logs tool outputs into metrics dashboards.\
-   **Task Ledger**: every invocation logged to Postgres + Prometheus.\
-   **Alerts**: SLA breach, cost overrun, repeated errors → governance
    signal.

------------------------------------------------------------------------

## ✅ Failure Modes & Safeguards

-   **Agent offline** → queue tool request, retry.\
-   **Tool storm** → rate-limit at SOC.\
-   **Governance conflict** → last-write-wins but audit trail required.\
-   **Breaking changes** → new tool_id/version, no silent upgrades.

------------------------------------------------------------------------

## ✅ Versioning & Change Management

-   Tools pinned by version in registry.\
-   Breaking changes → new schema version.\
-   Dry-run mode for mutative tools during WarmBoot runs.\
-   Registry updated via Git workflow (`feature/tool-upgrade-*`).

------------------------------------------------------------------------

## ✅ Future Enhancements

-   Auto-discovery of available MCP tools at boot.\
-   Dynamic cost optimization (route to cheapest provider).\
-   Simulation mode to replay tool usage for performance tuning.\
-   Auto-scaling CLI bridges for heavy workloads.

------------------------------------------------------------------------

> This protocol ensures agents are **armed with the right tools,
> securely and consistently**, with full traceability, governance, and
> observability --- making the Tool-Shed the backbone of effective,
> autonomous task execution.
