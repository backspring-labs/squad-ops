# 🌐 SquadOps Multi‑Cloud Infra Playbook (AWS ↔ GCP ↔ Azure)

> Goal: Make the **same SquadOps repo** able to target AWS, GCP, or Azure with a single logical design, so Claude (or any IaC assistant) can generate cloud‑specific stacks without changing the SquadOps application code or protocols.

---

## 0) Design Principles

1. **Cloud‑Agnostic Contract**: Define a small set of *logical components* the squad needs (Orchestrator, Agents, Queue, DB, Object Store, Secrets, Scheduler, Logs). Each cloud maps those to native services.
2. **IaC Interface**: One Terraform interface module (variables + outputs) with **three providers** behind it (aws/gcp/azurerm). Select via `var.cloud`.  
3. **Naming & Tags**: `org=squadops, env=dev|stage|prod, app=<squad-name>, owner=max`. Enforce uniformly.
4. **Security First**: Least‑privilege IAM; private subnets + public ALB; KMS/Key Vault for all at‑rest secrets; no public DBs.
5. **WBA Everywhere**: Eventing + Lambda/Cloud Functions/Azure Functions to generate **SIP‑006/6.1** reports each run.
6. **Model Backends Portable**: Prefer managed (Bedrock, Vertex AI, Azure OpenAI) first; self‑host GPUs only when needed.

---

## 1) Logical Components → Cloud Mappings

| Logical Component | AWS | GCP | Azure |
|---|---|---|---|
| **Orchestrator (HTTP UI + API)** | ECS **Fargate** + ALB | **GKE Autopilot** + HTTP LB (or Cloud Run fully managed) | **AKS** + App GW (or Container Apps) |
| **Agents (containers)** | ECS Fargate services | GKE Autopilot (or Cloud Run jobs/services) | AKS (or Container Apps jobs) |
| **Queue / Messaging** | **SQS** (+ DLQ) | **Pub/Sub** (+ Dead‑Letter topics) | **Service Bus** queues (+ DLQ) |
| **Scheduler / Events** | **EventBridge** rules | **Cloud Scheduler** + **Eventarc** | **Timer triggers** in Functions + **Event Grid** |
| **Serverless (WBA jobs)** | **Lambda** | **Cloud Functions** | **Azure Functions** |
| **Database (Postgres)** | **RDS PostgreSQL** (Multi‑AZ) | **Cloud SQL for PostgreSQL** (HA) | **Azure Database for PostgreSQL** (Flexible Server, zone‑redundant) |
| **Object Storage (artifacts, reports)** | **S3** | **Cloud Storage** | **Blob Storage** |
| **Searchable Logs (optional)** | OpenSearch Service | Elastic on GKE / Cloud Logging + Log Analytics | Azure Monitor Logs + Log Analytics Workspace |
| **Metrics/Monitoring** | CloudWatch | Cloud Monitoring (Stackdriver) | Azure Monitor + Application Insights |
| **Secrets & Keys** | **Secrets Manager** + **KMS** | **Secret Manager** + **Cloud KMS** | **Key Vault** (secrets + keys) |
| **VPC / Networking** | VPC, subnets, NAT GW, SGs | VPC, subnets, Cloud NAT, firewall rules | VNets, subnets, NAT GW, NSGs |
| **WAF / Edge** | **AWS WAF** (+ Shield) | Cloud Armor | Azure WAF |
| **CI/CD** | CodeBuild/Deploy, or GitHub Actions | Cloud Build/Deploy, or GitHub Actions | DevOps Pipelines, or GitHub Actions |
| **Managed LLMs** | **Bedrock** (Claude, Llama, Mistral) | **Vertex AI** (Gemini, Llama) | **Azure OpenAI** (GPT‑4/4o/mini) |
| **GPU Inference (self‑host)** | g5/g6/p5 on EC2 + ECS | A2/L4/L4s on GCE + GKE | NCas/H100 on VMSS + AKS |

---

## 2) Data Model (common across clouds)

**Postgres schemas** (identical everywhere):  
- `runs`, `wba_reports` (SIP‑006/6.1)  
- `agent_dna` (SIP‑004)  
- `squad_config` (SIP‑005 layer 3)  
- `prd` (or playbooks for ops mode; SIP‑005 layer 1)  
- `metrics_agent`, `metrics_squad`, `metrics_app_or_ops`

**Object storage layout** (S3/GCS/Blob):  
```
artifacts/{run_id}/...
reports/{run_id}/WBA.md
dna/{agent}/vX.Y.Z.md
squad/{version}/changelog.md
```

---

## 3) Terraform Layout (single interface, 3 providers)

```
infra/
  modules/
    squadops_interface/            # <- cloud-agnostic interface
      variables.tf                 # cloud, env, names, sizes, feature toggles
      outputs.tf                   # endpoints, queue names, db_url, secrets
      main.tf                      # conditionally calls one of the cloud impls
    aws_impl/
    gcp_impl/
    azure_impl/
  stacks/
    dev/
      main.tf                      # calls squadops_interface with cloud=aws|gcp|azure
    stage/
    prod/
providers/
  aws/
  gcp/
  azure/
```

**Interface variables (excerpt):**
```hcl
variable "cloud" { type = string } # "aws" | "gcp" | "azure"
variable "name"  { type = string } # squad name, e.g., "paperclip"
variable "env"   { type = string } # "dev" | "stage" | "prod"

# sizing
variable "orchestrator_cpu" { type = number, default = 1 }
variable "orchestrator_mem" { type = number, default = 2048 }
variable "agent_sizes" { type = map(object({
  cpu = number, mem = number
})) }

# features
variable "use_managed_llm" { type = bool, default = true }
variable "gpu_enabled"     { type = bool, default = false }
```

**Interface main.tf (pseudo):**
```hcl
module "cloud_impl" {
  source = var.cloud == "aws"   ? "../aws_impl" :
           var.cloud == "gcp"   ? "../gcp_impl" :
           var.cloud == "azure" ? "../azure_impl" : ""

  name  = var.name
  env   = var.env
  # pass through all common variables
}
```

**Outputs (uniform names):**
```
orchestrator_endpoint
queue_url
db_url
artifact_bucket
secrets_ref_namespace
wba_trigger_arn_or_id
```

---

## 4) Cloud‑Specific Notes

### AWS
- **ECS Fargate** for orchestrator/agents keeps ops minimal; ALB public, tasks private.
- Use **VPC endpoints** for S3/SQS/Secrets to reduce NAT costs.
- **EventBridge** + **Lambda** to assemble WBA reports to S3; notify via SNS/SES/Slack.

### GCP
- Prefer **Cloud Run** for fast start (or GKE Autopilot if you need daemon‑like agents).
- **Pub/Sub** for queueing; **Cloud Scheduler** + **Eventarc** for WBA triggers.
- **Cloud SQL** private IP + **Serverless VPC Access** for Cloud Run if needed.

### Azure
- **Container Apps** is the fastest path; use **AKS** if you need k8s features.
- **Service Bus** queues; **Functions** (Timer/Event Grid) for WBA.
- **Flexible Server PostgreSQL** with VNet integration; **Key Vault** for secrets.

---

## 5) Security & Governance (all clouds)
- Least‑privilege identities **per agent**; one role per service.
- Encrypted everywhere (KMS/Cloud KMS/Key Vault); customer‑managed keys for DB + storage.
- Private networking for DB; public ingress only through WAF‑protected LB.
- **Budgets/Alerts** day one.
- **Audit**: CloudTrail / Cloud Logging / Azure Activity Log enabled.

---

## 6) WBA Automation (portable recipe)

**Trigger**: post‑run event → cloud events → serverless function.  
**Function**: query Postgres + logs, compute Good/Bad/Ugly (SIP‑006/6.1), write `WBA.md` to object storage, send notification.  
- AWS: EventBridge → Lambda → S3 → SNS/Slack
- GCP: Scheduler → Cloud Function → GCS → Chat/Webhook
- Azure: Timer Function → Blob → Teams/Webhook

---

## 7) Model Backends (choose one per environment)

| Need | AWS | GCP | Azure |
|---|---|---|---|
| Managed LLM | **Bedrock** | **Vertex AI** | **Azure OpenAI** |
| Self‑host | ECS + EC2 g5/g6/p5 | GKE + A2/L4 | AKS + NCas/H100 |

Tip: keep an internal **`model-gateway`** service (HTTP/gRPC) so agents call a single endpoint regardless of provider.

---

## 8) Starter Variables Example (dev)

```hcl
module "squadops" {
  source = "../../modules/squadops_interface"
  cloud  = "aws"
  name   = "paperclip"
  env    = "dev"

  agent_sizes = {
    pak     = { cpu = 0.5, mem = 1024 }
    lore    = { cpu = 0.5, mem = 1024 }
    trin    = { cpu = 1.0, mem = 2048 }
    rune    = { cpu = 0.5, mem = 1024 }
    rachael = { cpu = 0.5, mem = 1024 }
    yelena  = { cpu = 0.25, mem = 512 }
    rom     = { cpu = 0.25, mem = 512 }
  }

  use_managed_llm = true
  gpu_enabled     = false
}
```

---

## 9) What to Put in the Repo So Claude Can Run With It

- `infra/modules/squadops_interface/` with **variables.tf**, **outputs.tf**, and a **main.tf** that routes to cloud impls.  
- Stubs for `aws_impl`, `gcp_impl`, `azure_impl` that create the mapped resources.  
- `stacks/dev/main.tf` showing one example instantiation (flip `cloud` to switch).  
- `providers/*` with auth boilerplate (README explains how to set credentials).  
- A short **CONTRIBUTING.md** describing naming/tags, versioning, and WBA requirements.

With this structure, Claude can fill in the cloud‑specific modules while keeping the logic consistent across providers.
