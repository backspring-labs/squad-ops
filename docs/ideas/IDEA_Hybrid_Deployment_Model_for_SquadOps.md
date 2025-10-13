# IDEA: Hybrid Deployment Model for SquadOps

---

## Purpose

This IDEA defines an **industry-aligned deployment architecture** for SquadOps that separates **infrastructure provisioning** from **runtime deployment**.  
The approach eliminates the earlier use of Terraform's `null_resource` for local or edge setups, aligning with modern DevOps and MLOps practices.  

Terraform remains responsible for **provisioning reproducible cloud infrastructure**, while a lightweight **`squadctl` CLI** manages local, edge, and hybrid runtime deployments.

---

## 1. Background

Earlier SquadOps concepts explored using Terraform for both cloud and local deployments (Mac, PC, Jetson).  
While technically feasible through `local-exec` and `remote-exec` provisioners, that approach stretches Terraform beyond its design intent.  
Industry consensus is clear: Terraform should **provision infrastructure**, not **manage or deploy applications**.

This IDEA redefines the deployment flow into two complementary layers that preserve portability and parity without overloading Terraform.

---

## 2. The Hybrid Model Overview

| **Layer** | **Responsibility** | **Recommended Tooling** |
|------------|--------------------|--------------------------|
| **Infrastructure Provisioning** | Provision servers, networking, and storage (cloud or on-prem). | **Terraform** |
| **Container Orchestration** | Deploy & manage SquadOps runtime containers. | **Docker Compose**, **Kubernetes**, or **ECS/Cloud Run** |
| **Application Runtime** | Serve the SquadOps API, manage agents, collect telemetry. | **SquadOps Runtime (FastAPI + adapters)** |
| **Edge / Local Bootstrap** | Run setup on personal or embedded devices. | **`squadctl` CLI** or installer script |

---

## 3. Terraform’s Role

Terraform continues to serve as the **source of truth** for reproducible infrastructure and deployment variables.

Terraform provisions:
- Networking (VPCs, gateways, load balancers)
- Compute resources (EC2, GCE, Azure VM, or container clusters)
- Storage and telemetry (S3, DynamoDB, Firestore, or CosmosDB)
- Container registries and secrets
- Outputs used by the SquadOps runtime layer

**Example:**

```bash
terraform apply -var="provider=aws"
```

Outputs:
```
api_url       = "https://api.squadops.cloud"
telemetry_db  = "telemetry_table"
auth_token    = "XXXXXX"
```

Terraform stops at infrastructure creation; it does not deploy containers or agents directly.

---

## 4. The `squadctl` CLI Layer

To deploy and manage SquadOps runtimes consistently across environments, a command-line tool — **`squadctl`** — will be introduced.  
It provides a uniform interface to launch, manage, and connect runtimes regardless of host type.

**Example Commands:**

```bash
# Deploy locally
squadctl deploy --adapter local

# Deploy to Jetson
squadctl deploy --adapter jetson --host 192.168.1.25

# Connect local runtime to cloud registry
squadctl connect --registry https://registry.squadops.cloud
```

**Key Responsibilities:**
- Detect OS and environment (Mac, Windows, Linux, Jetson).  
- Pull and configure SquadOps container images.  
- Register runtime with central registry and telemetry service.  
- Manage local environment variables and secrets.  
- Report back to Terraform outputs if running in hybrid mode.

---

## 5. Architecture Summary

```
+-----------------------------------------------+
| Terraform Infrastructure Layer                |
|  - Provisions cloud environment (AWS/GCP/Azure) |
|  - Exposes runtime variables & network configs |
+----------------------------┬------------------+
                             │
                             ▼
+-----------------------------------------------+
| SquadOps Runtime Layer (Docker/Kubernetes)    |
|  - FastAPI runtime exposing /api/* routes      |
|  - Agent orchestration and telemetry           |
+----------------------------┬------------------+
                             │
                             ▼
+-----------------------------------------------+
| Local & Edge Layer (squadctl CLI)             |
|  - Deploys runtimes to Mac/PC/Jetson          |
|  - Connects local nodes to cloud registry     |
|  - Maintains API and telemetry parity         |
+-----------------------------------------------+
```

---

## 6. Benefits of the Hybrid Model

| **Advantage** | **Description** |
|----------------|-----------------|
| **Industry Alignment** | Matches best practices of AWS, GCP, and Azure DevOps workflows. |
| **Separation of Concerns** | Terraform handles infra; SquadOps CLI handles runtime. |
| **Cross-Platform Parity** | Local, edge, and cloud all use the same API runtime contract. |
| **Scalable & Modular** | Allows future orchestration through Kubernetes, ECS, or Fleet Management. |
| **Simplified Developer UX** | `terraform apply` + `squadctl deploy` replaces complex provisioning logic. |

---

## 7. Next Steps

| **Phase** | **Deliverable** |
|------------|----------------|
| **1. CLI Prototype** | Build `squadctl` with Typer or Click to wrap Docker Compose and local configs. |
| **2. Docker Manifests** | Create Docker Compose + Helm charts for local/cloud deployments. |
| **3. Terraform Refactor** | Simplify Terraform modules to focus purely on provisioning. |
| **4. Registry Integration** | Link deployed runtimes to central SquadOps registry for telemetry. |
| **5. Documentation Update** | Update Appendix A to reflect hybrid workflow (`terraform apply` + `squadctl deploy`). |

---

## 8. Alignment with the SquadOps System Interface Blueprint (SIB)

This hybrid deployment model directly supports the **SquadOps System Interface Blueprint (SIB)** by maintaining consistent runtime APIs and telemetry contracts across all environments while staying aligned with industry-standard infrastructure practices.

---

## Status

🧩 **IDEA Stage** — Candidate for Squad Improvement Proposal (SIP) after CLI prototype validation.
