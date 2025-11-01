# 🧩 Squad Improvement Proposal (SIP-028)
## Title: Hybrid Deployment Model — Industry-Aligned Architecture for Multi-Environment Deployments
**Author:** System Architecture  
**Contributors:** Infrastructure, DevOps, Book Editorial  
**Date:** 2025-10-13  
**Status:** Proposed  
**Version:** 1.0  
**Priority:** HIGH  

---

## 🎯 Objective

Define a **production-grade deployment architecture** for SquadOps that separates **infrastructure provisioning** from **runtime deployment**, aligning with modern DevOps and MLOps practices while enabling seamless deployments across local, edge, and cloud environments.

This proposal introduces:
1. **`squadctl` CLI** — Unified deployment interface for all environments
2. **Environment Profiles** — Configuration templates for local, edge, and cloud deployments
3. **Terraform Integration** — Infrastructure-as-code for cloud provisioning
4. **LLM Provider Abstraction** — Flexible model loading across deployment targets

---

## 🔍 Background

### Current State

SquadOps currently uses manual Docker Compose commands for deployment:
- Infrastructure is hardcoded in `docker-compose.yml`
- Environment variables are manually configured
- No formal separation between infrastructure and runtime layers
- No CLI tool for cross-platform deployment
- No environment profiles (local, edge, cloud)

### Pain Points

1. **Manual Deployment Process**: Users run `docker-compose up` or `./deploy-squad.sh` manually
2. **No Environment Profiles**: Same `docker-compose.yml` for all environments (Mac, Jetson, AWS)
3. **Infrastructure Mixing**: Terraform concepts explored but abandoned due to misalignment with tool intent
4. **LLM Provider Lock-in**: Ollama-specific configuration hardcoded in compose files
5. **Poor Reader Experience**: Book readers need `squadctl deploy --adapter local` not shell scripts

### Industry Best Practices

Modern DevOps separates concerns:
- **Terraform** provisions infrastructure (VPCs, compute, storage) — stops at infrastructure creation
- **Container orchestration** (Docker Compose, Kubernetes, ECS) deploys applications
- **CLI tools** provide unified interfaces (e.g., `kubectl`, `aws`, `gcloud`)

---

## 🧩 Proposal Summary

Implement a **three-layer hybrid deployment model** that maintains backward compatibility while enabling enterprise-grade deployments:

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Terraform (Infrastructure)            │
│  - Provisions cloud resources (AWS/GCP/Azure)  │
│  - Outputs: API URLs, DB endpoints, secrets    │
│  - Scope: Cloud deployments only               │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ Layer 2: squadctl CLI (Runtime Orchestration)  │
│  - Detects environment (Mac/Linux/Jetson)      │
│  - Loads environment profiles                  │
│  - Manages Docker Compose / K8s deployments    │
│  - Connects to registries & telemetry          │
│  - Scope: All environments                     │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ Layer 3: SquadOps Runtime (Agents + Services)  │
│  - FastAPI task-api & health-check services    │
│  - Agent containers (Max, Neo, EVE, etc.)      │
│  - Infrastructure services (RabbitMQ, Postgres)│
│  - Scope: Identical across all environments    │
└─────────────────────────────────────────────────┘
```

---

## 🏗 Architecture Design

### Layer 1: Terraform (Infrastructure Provisioning)

**Responsibility**: Provision reproducible cloud infrastructure only.

**Terraform Provisions:**
- Networking (VPCs, subnets, gateways, load balancers)
- Compute resources (EC2, ECS clusters, GKE nodes, Azure Container Instances)
- Storage (S3, Cloud Storage, Blob Storage, RDS, Cloud SQL)
- Container registries and secrets management
- Outputs used by SquadOps runtime

**Example Workflow:**
```bash
cd terraform/environments/aws
terraform apply -var-file="dev.tfvars"

# Outputs:
# api_url       = "https://api.squadops.cloud"
# telemetry_db  = "squadops-telemetry"
# registry_url  = "123456789.dkr.ecr.us-west-2.amazonaws.com/squadops"
```

**Terraform stops here** — it does NOT deploy containers or start agents.

**Directory Structure:**
```
terraform/
  modules/
    aws/
      main.tf           # ECS cluster, VPC, ALB, RDS
      variables.tf      # Input variables
      outputs.tf        # Exported values (api_url, db_endpoint)
    gcp/
      main.tf           # Cloud Run, VPC, Cloud SQL
      variables.tf
      outputs.tf
    azure/
      main.tf           # Container Instances, VNet, Cosmos DB
      variables.tf
      outputs.tf
  environments/
    dev.tfvars          # Development configuration
    staging.tfvars      # Staging configuration
    prod.tfvars         # Production configuration
```

---

### Layer 2: squadctl CLI (Runtime Orchestration)

**Responsibility**: Deploy and manage SquadOps runtimes consistently across all environments.

**Core Commands:**

```bash
# Deploy locally (Mac/PC)
squadctl deploy --adapter local

# Deploy to Jetson edge device
squadctl deploy --adapter jetson --host 192.168.1.25

# Deploy to AWS (uses Terraform outputs)
squadctl deploy --adapter aws --region us-west-2

# Deploy to GCP
squadctl deploy --adapter gcp --project squadops-prod

# Connect local runtime to cloud registry
squadctl connect --registry https://registry.squadops.cloud

# Check runtime status
squadctl status
# Output:
# Environment: local
# Services: ✓ rabbitmq, ✓ postgres, ✓ redis, ✓ prefect
# Agents: ✓ max (llama3.1:8b), ✓ neo (qwen2.5:7b)
# Registry: Connected to https://registry.squadops.cloud

# View logs
squadctl logs max
squadctl logs postgres

# Tear down environment
squadctl teardown
```

**Key Responsibilities:**
- **Environment Detection**: Automatically detect OS (Mac, Linux, Windows) and architecture (x86_64, ARM64)
- **Profile Loading**: Read from `config/environments/{environment}.yaml`
- **Container Orchestration**: Generate Docker Compose overrides or Kubernetes manifests
- **Secret Management**: Load environment variables from profiles or Terraform outputs
- **Registry Connection**: Register runtime with central SquadOps registry
- **Health Checks**: Validate all services are healthy before reporting success
- **Telemetry Reporting**: Send deployment events to telemetry service

**Implementation Stack:**
- **Language**: Python (matches SquadOps core)
- **CLI Framework**: Typer (modern, type-safe, user-friendly)
- **Configuration**: PyYAML for environment profiles
- **Container Interface**: Docker SDK for Python
- **Distribution**: PyPI package (`pip install squadctl`)

---

### Layer 3: SquadOps Runtime (Agents + Services)

**Responsibility**: Execute the SquadOps application stack.

**Components:**
- **Infrastructure Services**: RabbitMQ, PostgreSQL, Redis, Prefect
- **API Services**: task-api, health-check
- **Agent Containers**: Max, Neo, EVE, Nat, Data, etc.
- **Application Containers**: WarmBoot apps, deployed services

**Key Principle**: The runtime layer is **environment-agnostic**.  
The same Docker images work identically on Mac, Jetson, AWS ECS, GCP Cloud Run, or Azure Container Instances.

---

## 📋 Environment Profiles

Environment profiles provide configuration templates for different deployment targets.

**Directory Structure:**
```
config/environments/
  local.yaml          # Local development (Mac/PC)
  jetson.yaml         # NVIDIA Jetson edge devices
  aws.yaml            # AWS ECS deployment
  gcp.yaml            # GCP Cloud Run deployment
  azure.yaml          # Azure Container Instances
  hybrid.yaml         # Hybrid: local agents + cloud infrastructure
```

### Example: `local.yaml`

```yaml
# SquadOps Environment Profile: Local Development
environment: local
adapter: docker-compose
description: "Local development on Mac/PC with Ollama LLMs"

# LLM Configuration
llm:
  provider: ollama
  endpoint: http://host.docker.internal:11434
  fallback: null  # No fallback for local dev

# Infrastructure Services
services:
  rabbitmq:
    enabled: true
    image: rabbitmq:3.12-management
    ports: ["5672:5672", "15672:15672"]
  
  postgres:
    enabled: true
    image: postgres:15
    ports: ["5432:5432"]
    max_connections: 200
  
  redis:
    enabled: true
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  prefect:
    enabled: true
    server_port: 4200
    ui_port: 4201

# Agents to Deploy
agents:
  - name: max
    role: lead
    model: llama3.1:8b
    enabled: true
  
  - name: neo
    role: dev
    model: qwen2.5:7b
    enabled: true
  
  - name: eve
    role: qa
    model: llama3-70b
    enabled: false  # Heavy model, disabled by default

# Resource Limits
resources:
  memory_limit: 512m
  cpu_limit: 0.5

# Volume Mounts
volumes:
  warm_boot: ./warm-boot:/app/warm-boot
  docker_sock: /var/run/docker.sock:/var/run/docker.sock

# Registry
registry:
  enabled: false  # Local dev doesn't push to registry
  url: null
```

### Example: `jetson.yaml`

```yaml
# SquadOps Environment Profile: NVIDIA Jetson Edge
environment: jetson
adapter: docker-compose
description: "Edge deployment on NVIDIA Jetson with GPU support"

llm:
  provider: ollama
  endpoint: http://localhost:11434
  gpu_enabled: true
  gpu_layers: 35  # Offload layers to Jetson GPU

services:
  rabbitmq:
    enabled: true
    image: rabbitmq:3.12-management-alpine  # Lighter for ARM
  
  postgres:
    enabled: true
    image: postgres:15-alpine
    max_connections: 50  # Lower for edge device
  
  redis:
    enabled: true
    image: redis:7-alpine
  
  prefect:
    enabled: false  # Skip Prefect on edge for resource conservation

agents:
  - name: max
    role: lead
    model: llama3.1:8b
    enabled: true
    gpu: true
  
  - name: neo
    role: dev
    model: qwen2.5:7b
    enabled: true
    gpu: true

resources:
  memory_limit: 2g  # Jetson has more RAM
  cpu_limit: 2.0

volumes:
  warm_boot: /data/squadops/warm-boot:/app/warm-boot

registry:
  enabled: true
  url: https://registry.squadops.cloud
  auth_token: ${SQUADOPS_REGISTRY_TOKEN}
```

### Example: `aws.yaml`

```yaml
# SquadOps Environment Profile: AWS ECS
environment: aws
adapter: ecs
description: "Cloud deployment on AWS ECS with Bedrock LLMs"

llm:
  provider: bedrock
  region: us-west-2
  fallback: openai  # Fallback to OpenAI if Bedrock unavailable

# Infrastructure Services (managed by AWS)
services:
  rabbitmq:
    enabled: false  # Use Amazon MQ
    amazon_mq_endpoint: ${AMAZON_MQ_ENDPOINT}
  
  postgres:
    enabled: false  # Use RDS
    rds_endpoint: ${RDS_ENDPOINT}
  
  redis:
    enabled: false  # Use ElastiCache
    elasticache_endpoint: ${ELASTICACHE_ENDPOINT}
  
  prefect:
    enabled: true
    ecs_task_definition: squadops-prefect-server

agents:
  - name: max
    role: lead
    model: anthropic.claude-3-sonnet
    enabled: true
  
  - name: neo
    role: dev
    model: anthropic.claude-3-haiku
    enabled: true
  
  - name: eve
    role: qa
    model: anthropic.claude-3-opus
    enabled: true

resources:
  memory_limit: 2048  # ECS task memory
  cpu_limit: 1024     # ECS CPU units

registry:
  enabled: true
  url: ${ECR_REGISTRY_URL}
  auth_token: ${AWS_ECR_TOKEN}

telemetry:
  enabled: true
  endpoint: https://telemetry.squadops.cloud
  cloudwatch_logs: true
```

---

## 🔄 LLM Provider Abstraction

To support multiple LLM providers across environments, add a provider abstraction layer.

**Update: `config/deployment_config.py`**

```python
# LLM Provider Configuration
LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "ollama"),  # ollama|openai|anthropic|bedrock
    "endpoint": os.getenv("LLM_ENDPOINT", "http://host.docker.internal:11434"),
    "api_key": os.getenv("LLM_API_KEY", None),
    "region": os.getenv("LLM_REGION", "us-west-2"),  # For Bedrock
    "fallback_provider": os.getenv("LLM_FALLBACK_PROVIDER", None),
    "fallback_api_key": os.getenv("LLM_FALLBACK_API_KEY", None),
    "gpu_enabled": os.getenv("LLM_GPU_ENABLED", "false").lower() == "true",
    "gpu_layers": int(os.getenv("LLM_GPU_LAYERS", "0"))
}

def get_llm_config(config_key: str) -> Any:
    """Get LLM provider configuration"""
    return LLM_CONFIG.get(config_key)

def get_llm_endpoint(provider: str = None) -> str:
    """Get LLM endpoint for specified provider"""
    provider = provider or LLM_CONFIG["provider"]
    
    endpoints = {
        "ollama": LLM_CONFIG["endpoint"],
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "bedrock": f"https://bedrock-runtime.{LLM_CONFIG['region']}.amazonaws.com"
    }
    
    return endpoints.get(provider, LLM_CONFIG["endpoint"])
```

---

## 📅 Implementation Phases

### Phase 1 (v0.3.0): squadctl CLI + Environment Profiles
**Target Date:** Q1 2025  
**Status:** Proposed

**Deliverables:**
1. ✅ Build `squadctl` CLI with Typer
   - Commands: `deploy`, `status`, `logs`, `teardown`, `connect`
   - Environment detection (OS, architecture)
   - Docker Compose orchestration

2. ✅ Create environment profiles
   - `config/environments/local.yaml`
   - `config/environments/jetson.yaml`
   - `config/environments/hybrid.yaml`

3. ✅ Add LLM provider abstraction
   - Support: Ollama, OpenAI, Anthropic
   - Fallback mechanism
   - GPU configuration for Jetson

4. ✅ Update documentation
   - Book Chapter 6: Infrastructure Setup (introduce `squadctl`)
   - Book Chapter 7: Agent Configuration (show environment profiles)
   - README: Quick start with `squadctl deploy --adapter local`

**Migration Path:**
- Existing `docker-compose up` workflow continues to work
- `squadctl` wraps and enhances Docker Compose
- No breaking changes

**Success Metrics:**
- `squadctl` runs successfully on Mac, Linux, and Jetson
- Deployment time < 2 minutes for local environment
- 90% reduction in manual configuration steps

---

### Phase 2 (v0.4.0): Terraform Modules + Registry Integration
**Target Date:** Q2 2025  
**Status:** Planned

**Deliverables:**
1. ✅ Create Terraform modules
   - AWS: ECS cluster, VPC, ALB, RDS, ECR
   - GCP: Cloud Run, VPC, Cloud SQL, Artifact Registry
   - Azure: Container Instances, VNet, Cosmos DB, ACR

2. ✅ Add environment profiles
   - `config/environments/aws.yaml`
   - `config/environments/gcp.yaml`
   - `config/environments/azure.yaml`

3. ✅ Build central registry service
   - FastAPI service to track deployed runtimes
   - Telemetry collection from all environments
   - Dashboard for runtime visibility

4. ✅ Integrate `squadctl` with Terraform
   - `squadctl deploy --adapter aws` reads Terraform outputs
   - Automatic authentication with cloud providers
   - Service discovery via Terraform state

**Success Metrics:**
- Cloud deployments complete in < 10 minutes
- Terraform modules pass validation for AWS, GCP, Azure
- Registry tracks 100% of deployed runtimes

---

### Phase 3 (v0.5.0): Advanced Orchestration
**Target Date:** Q3 2025  
**Status:** Future

**Deliverables:**
1. ✅ Kubernetes support
   - Helm charts for SquadOps stack
   - `squadctl deploy --adapter k8s --kubeconfig ~/.kube/config`
   - Auto-scaling policies for agents

2. ✅ Managed container services
   - AWS ECS Fargate integration
   - GCP Cloud Run (fully managed)
   - Azure Container Apps

3. ✅ Fleet management
   - Deploy to multiple edge devices simultaneously
   - `squadctl deploy --adapter fleet --targets jetson-001,jetson-002,jetson-003`
   - Centralized monitoring and updates

4. ✅ GitOps integration
   - ArgoCD/Flux CD workflows
   - Infrastructure-as-code for full stack
   - Automated rollbacks on failure

**Success Metrics:**
- Support for 10+ simultaneous edge deployments
- Kubernetes deployments with auto-scaling
- GitOps workflows with automated testing

---

## ✅ Benefits

| **Benefit** | **Description** |
|-------------|-----------------|
| **Industry Alignment** | Matches AWS, GCP, Azure DevOps best practices — terraform for infra, CLI for runtime |
| **Separation of Concerns** | Terraform handles infrastructure; squadctl handles runtime; agents handle logic |
| **Cross-Platform Parity** | Identical runtime experience on Mac, Jetson, AWS ECS, GCP Cloud Run |
| **Scalable Architecture** | Foundation for Kubernetes, ECS Fargate, fleet management |
| **Developer Experience** | `squadctl deploy --adapter local` replaces manual Docker Compose commands |
| **Book Reader Experience** | Professional deployment workflow from Chapter 6 onward |
| **Backward Compatible** | Existing `docker-compose up` continues to work |
| **LLM Flexibility** | Switch between Ollama, OpenAI, Anthropic, Bedrock per environment |
| **Registry Integration** | Central visibility into all deployed runtimes |
| **GitOps Ready** | Infrastructure-as-code foundation for CI/CD pipelines |

---

## 🔄 Migration Path

### For Existing Users

**Current Workflow:**
```bash
docker-compose up -d
```

**Post-SIP-028 (Backward Compatible):**
```bash
# Option 1: Continue using Docker Compose (no change)
docker-compose up -d

# Option 2: Use squadctl (recommended)
squadctl deploy --adapter local
```

**No Breaking Changes:**
- Existing `docker-compose.yml` remains valid
- Environment variables work identically
- Volume mounts unchanged
- Network configuration preserved

### For New Users (Book Readers)

**Recommended Workflow (Chapter 6):**
```bash
# Install squadctl
pip install squadctl

# Deploy SquadOps locally
squadctl deploy --adapter local

# Check status
squadctl status

# View logs
squadctl logs max
squadctl logs neo

# Tear down
squadctl teardown
```

---

## 📖 Book Integration

This SIP directly supports **Part II: Operational Mechanics** of the SquadOps companion book.

### Chapter 6: Infrastructure Setup & Configuration

**Before SIP-028:**
- Manual Docker Compose commands
- Copy-paste environment variables
- Troubleshoot networking issues

**After SIP-028:**
- Professional CLI experience
- One-command deployment
- Automatic health checks

**Chapter Content:**
```markdown
## 6.3 Deploying SquadOps Locally

With `squadctl`, deployment is a single command:

```bash
squadctl deploy --adapter local
```

This command:
1. Detects your OS and architecture
2. Loads the local environment profile
3. Pulls required Docker images
4. Starts infrastructure services (RabbitMQ, Postgres, Redis)
5. Launches agents (Max, Neo)
6. Validates health checks
7. Reports status

**Output:**
```
✓ Environment detected: macOS (arm64)
✓ Profile loaded: local
✓ Infrastructure services started (4/4)
✓ Agents launched (2/2)
✓ Health checks passed

SquadOps is ready at http://localhost:8000
Max (Lead): llama3.1:8b
Neo (Dev): qwen2.5:7b
```

### Chapter 7: Agent Configuration & Deployment

**Show environment profiles:**
- Demonstrate editing `config/environments/local.yaml`
- Explain LLM provider selection
- Show enabling/disabling agents

### Chapter 8: The WarmBoot Protocol

**Use squadctl for WarmBoot runs:**
```bash
# Deploy with WarmBoot UI
squadctl deploy --adapter local --enable-warmboot-ui

# Check WarmBoot status
squadctl status --warmboot
```

---

## 📊 Success Metrics

| **Metric** | **Target** | **Measurement** |
|------------|------------|-----------------|
| **CLI Adoption Rate** | 80% of new users | Track `squadctl` installs vs manual deployments |
| **Deployment Time** | < 2 min (local), < 10 min (cloud) | Time from `squadctl deploy` to healthy status |
| **Environment Parity** | 100% feature parity | All environments support identical agent capabilities |
| **Error Rate** | < 5% failed deployments | Track success rate across all adapters |
| **Book Reader Success** | 90% complete Chapter 6 | Survey readers post-deployment |
| **Registry Connection** | 95% of cloud deployments | Telemetry confirms registry registration |

---

## 🔐 Security Considerations

1. **Secrets Management**
   - Environment profiles reference secrets via `${ENV_VAR}` interpolation
   - Never commit API keys to version control
   - Use cloud secret managers (AWS Secrets Manager, GCP Secret Manager)

2. **Registry Authentication**
   - JWT tokens for registry connection
   - Tokens expire after 24 hours
   - Rotation handled by `squadctl connect --refresh`

3. **Terraform State Security**
   - Store Terraform state in remote backend (S3, GCS, Azure Blob)
   - Enable state encryption
   - Use IAM policies to restrict access

---

## 🚀 Next Steps

### Immediate Actions (Post-Approval)

1. **Create `squadctl` Repository**
   - Initialize Python project with Poetry
   - Set up Typer CLI framework
   - Implement `deploy` and `status` commands

2. **Create Environment Profiles**
   - Add `config/environments/` directory
   - Write `local.yaml`, `jetson.yaml`, `hybrid.yaml`
   - Validate YAML schemas

3. **Update Documentation**
   - Update Book Chapter 6 outline
   - Update README with `squadctl` examples
   - Create migration guide for existing users

### Phase 1 Milestone Tasks

- [ ] Build `squadctl` CLI (core commands)
- [ ] Create environment profile schema
- [ ] Implement Docker Compose adapter
- [ ] Add LLM provider abstraction
- [ ] Write integration tests
- [ ] Update book chapters
- [ ] Publish `squadctl` to PyPI

---

## 📝 References

- **IDEA Document**: `IDEA_Hybrid_Deployment_Model_for_SquadOps.md`
- **Current Deployment Config**: `config/deployment_config.py`
- **Docker Compose**: `docker-compose.yml`
- **Book Outline**: `docs/book/BOOK_OUTLINE.md` (Chapter 6)
- **Related SIPs**:
  - SIP-024: Execution Cycle Protocol (ECID standards)
  - SIP-027: WarmBoot Telemetry & Orchestration Protocol

---

## 🎯 Conclusion

The Hybrid Deployment Model transforms SquadOps from a development prototype into a production-grade framework with enterprise deployment capabilities. By introducing `squadctl`, environment profiles, and Terraform integration, we align with industry standards while maintaining the simplicity that makes SquadOps accessible to individual developers and researchers.

This architecture scales from a MacBook Air to a fleet of Jetson devices to AWS ECS clusters — all using the same agent code, the same coordination protocols, and the same governance model.

**Status**: ✅ Ready for review and approval  
**Next**: Begin Phase 1 implementation upon approval

---

**Approved by**: _Pending_  
**Implementation Lead**: _TBD_  
**Target Release**: v0.3.0 (Q1 2025)





