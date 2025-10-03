# ✅ Quark Cost Monitoring Protocol (v1.0)

------------------------------------------------------------------------

## 📌 Purpose

Define the protocol for **Quark's role as Cost Accountant** within
SquadOps. Quark must monitor every WarmBoot run, attribute costs to
agents/PIDs, and attach cost summaries to the final WarmBoot report.
This includes **cloud infra (AWS/GCP/Azure)**, **API vendors (Claude,
GPT-5, etc.)**, and explicitly records **zero cost for local LLM
usage**.

------------------------------------------------------------------------

## ✅ Protocol Objectives

-   Centralize **cost data ingestion** across providers.\
-   Attribute costs to **run_id, agent, PID** for every WarmBoot run.\
-   Differentiate **cloud infra spend**, **API vendor spend**, and
    **local-zero-cost usage**.\
-   Guarantee **traceability** by enforcing tagging/labeling across all
    deployments.\
-   Enable **real-time governance signals** when ceilings are breached.\
-   Produce a unified **WarmBoot Cost Report** (summary + detail).

------------------------------------------------------------------------

## ✅ Access Requirements

  -----------------------------------------------------------------------------------------------
  Provider        Access Method      Permissions                        Delivery Mechanism
  --------------- ------------------ ---------------------------------- -------------------------
  **AWS**         IAM Role           `cur:DescribeReportDefinitions`,   IRSA (EKS), ECS Task
                                     `s3:GetObject`,                    Role, or Vault/STS broker
                                     `athena:StartQueryExecution`,      
                                     `athena:GetQueryResults`,          
                                     `ce:GetCostAndUsage`,              
                                     `tag:GetResources`                 

  **GCP**         Service Account    `roles/billing.viewer`,            Workload Identity or JSON
                                     `roles/bigquery.dataViewer`        key delivered via Vault

  **Azure**       Service Principal  `Cost Management Reader`,          Managed Identity (AKS) or
                  / Managed Identity `Storage Blob Data Reader`         Vault-injected
                                                                        credentials

  **Claude        Billing API/CSV    Read-only usage & billing          API key or CSV ingestion
  (Anthropic)**   export                                                into `vendor_costs`

  **OpenAI        Billing API/CSV    Read-only usage & billing          API key or CSV ingestion
  GPT-5**         export                                                into `vendor_costs`

  **Other Vendors Vendor billing     Read-only usage & billing          Ingest into
  (PostHog,       API/CSV                                               `vendor_costs` table
  Flagsmith,                                                            
  etc.)**                                                               

  **Local LLMs    N/A                N/A                                **Always zero cost**;
  (DGX Spark,                                                           recorded in ledger
  Jetson Nano,                                                          explicitly
  etc.)**                                                               
  -----------------------------------------------------------------------------------------------

------------------------------------------------------------------------

## ✅ Tagging & Attribution Requirements

-   **Cloud Infra**: All resources must carry `WarmBootRun`, `Agent`,
    `PID` tags (AWS/GCP) or labels (Azure).\
-   **API Calls**: Each premium API call must include `run_id`, `agent`,
    `pid`, `tokens_in/out`, `cost_estimate`. Logged into Quark's
    internal ledger at runtime.\
-   **Local LLMs**: Logged with `run_id`, `agent`, `pid`, and
    `cost_usd=0.00`.

------------------------------------------------------------------------

## ✅ Cost Planes

### 1. Cloud Infra

-   Costs collected via CUR (AWS), BigQuery Export (GCP), or Billing
    Export/API (Azure).\
-   Quark queries exports and attributes costs by run_id/agent/pid using
    tags/labels.\
-   Shared infra (NAT, ALB, DBs, bandwidth) must be allocated by policy
    (time, utilization, traffic).

### 2. API Vendors

-   Quark logs every API call at runtime with estimated cost.\
-   Reconciles nightly/weekly against vendor billing exports (Claude,
    OpenAI, PostHog, etc.).\
-   Discrepancies flagged to Max for governance review.

### 3. Local LLMs

-   No vendor billing.\
-   Logged explicitly with `cost_usd=0.00`.\
-   Included in reports for completeness.

------------------------------------------------------------------------

## ✅ Invocation Lifecycle

1.  **Start of Run**: Quark enforces tag/label policies; validates
    access to billing data sources.\
2.  **During Run**:
    -   Logs premium API usage in real time.\
    -   Monitors cost ceilings; raises governance signals if exceeded.\
3.  **End of Run**:
    -   Pulls infra costs from cloud provider exports (CUR, BigQuery,
        Blob/API).\
    -   Merges with API vendor costs and local-zero-cost entries.\
    -   Produces WarmBoot Cost Report.

------------------------------------------------------------------------

## ✅ Governance & Observability

-   **Quark** attaches cost breakdown to every WarmBoot summary.\
-   **Max** validates run ceilings and ensures compliance.\
-   **Data** integrates cost KDEs into SquadOps analytics dashboards.\
-   **SOC** displays real-time API spend and lagging infra spend side by
    side.

------------------------------------------------------------------------

## ✅ Failure Modes & Safeguards

-   **Missing tags/labels** → cost marked as "orphaned"; allocation
    rules apply.\
-   **Vendor API outage** → fallback to internal runtime logs;
    reconciliation deferred.\
-   **Cloud export lag** → reports marked PRELIMINARY until billing data
    stabilizes.\
-   **Budget breach** → Quark raises governance signal to pause or
    throttle agents.

------------------------------------------------------------------------

## ✅ Deliverables per WarmBoot Run

-   `warmboot_run_cost_summary.md`\
-   `warmboot_run_cost_detail.csv` (line items per service/agent/pid)\
-   `warmboot_run_vendor_costs.csv` (external APIs)\
-   `warmboot_run_allocation_explained.json` (shared infra math)

------------------------------------------------------------------------

> With this protocol, Quark becomes the **single source of truth for
> WarmBoot run costing** across infra, APIs, and local models ---
> ensuring complete, auditable, and actionable financial telemetry for
> every run.
