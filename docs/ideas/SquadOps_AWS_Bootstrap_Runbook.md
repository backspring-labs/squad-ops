# 🚀 SquadOps AWS Bootstrap Runbook (MVP → Scale)

## Why AWS now?
DGX is delayed and a full squad won’t fit on a Nano. This runbook gets you to a **production-like** deployment quickly on AWS, with an upgrade path to GPUs (or Bedrock) when needed.

---

## Architecture (MVP-first, upgrade-ready)

### Core layout
- **VPC**: 2 public + 2 private subnets, 1 NAT Gateway (can be zonal to save cost).
- **Orchestrator**: ECS on Fargate (or a single EC2) running the **SquadOps Console** + **Max**.
- **Agents**: ECS services (one per role): Pak, Yelena, Rom, Lore, Trin, Rune, Rachael.
- **Queueing**: SQS (task queue) + EventBridge (schedules, cron for WBA).
- **State & Logs**: RDS Postgres (PID, DNA, metrics), S3 (artifacts), CloudWatch Logs (stdout), optional OpenSearch (searchable logs).
- **Secrets**: AWS Secrets Manager (API keys, DB creds).
- **Artifacts**: ECR for container images.
- **WBA pipeline**: Step Functions or Lambda to generate SIP‑006/6.1 WBA markdown and drop into S3 + notify Slack/Email.
- **Network ingress**: ALB → Orchestrator service (private agents behind NLB or service discovery).

### Optional model backends
- **Managed**: Amazon Bedrock (Claude, Llama, Mistral). No GPU ops to manage.
- **Self-host** (when needed): GPU ASG for inference workers:
  - Start with **g5.xlarge** (L4) or **g6.xlarge** when available.
  - For heavy loads: **p5.2xlarge** (H100 slice) if whitelisted.
  - Agents call inference via internal NLB.

---

## Environments
- **dev**: single‑AZ, tiny RDS, 1 NAT, on‑demand/spot mix.
- **stage**: multi‑AZ RDS, two ECS capacity providers, SQS DLQs enabled.
- **prod**: multi‑AZ, WAF on ALB, backups + cross‑region S3 replication (if needed).

---

## Minimal sizing (reasonable starting point)
- **Orchestrator (ECS Fargate)**: 1 vCPU / 2 GB (burstable) → scale to 2/4.
- **Agents (ECS Fargate)**:
  - **Pak, Lore, Trin, Rune, Rachael**: 0.5–1 vCPU / 1–2 GB each.
  - **Yelena, Rom** (light CPU): 0.25–0.5 vCPU / 0.5–1 GB.
- **DB (RDS Postgres)**: db.t3.small (dev), db.t4g.medium (stage), enable autoscaling storage.
- **Queue (SQS)**: standard queue + DLQ per domain (flips, imports, digital).

> If you self-host models, add a GPU worker group (see “GPU path” below). Otherwise use **Bedrock** to keep infra simple and fast.

---

## Cost guardrails (ballpark, dev)
- **Fargate (7 services, low duty)**: ~$80–200/mo depending on runtime.
- **RDS t3.small**: ~$40–70/mo.
- **NAT (1 AZ)**: ~$35–45/mo + data egress.
- **S3/CloudWatch**: $5–20/mo for light usage.
- **SQS/EventBridge/Secrets**: single‑digit dollars.
- **GPU (spot g5.xlarge when needed)**: budget ~$0.30–0.60/hr; cap with schedules.
> Set **budgets + alerts** in AWS Budgets day one (hard monthly caps).

---

## Security & Governance
- **IAM least privilege** per agent; each task gets its own task role.
- **VPC endpoints** for S3, SQS, Secrets to avoid public egress where possible.
- **WAF + Shield** on ALB (prod).
- **KMS** CMKs for RDS, S3, and Secrets.
- **Audit**: CloudTrail enabled; GuardDuty on.
- **Change control**: All infra via Git + Terraform; app configs via GitOps (e.g., CodePipeline or GitHub Actions to ECR/ECS).

---

## Data model (ties to your SIPs)
- **RDS schemas**:
  - `runs` (warmboots), `wba_reports` (SIP‑006/6.1 outputs),
  - `agent_dna` (version, changelog, fitness deltas; SIP‑004),
  - `squad_config` (profile/version; SIP‑005 layer 3),
  - `prd` (or playbooks in ops mode; SIP‑005 layer 1),
  - `metrics_agent`, `metrics_squad`, `metrics_ops/app` (SIP‑005 layer 4).

- **S3 structure**:
  - `artifacts/{run_id}/…`
  - `reports/{run_id}/WBA.md`
  - `dna/{agent}/vX.Y.Z.md`
  - `squad/{version}/changelog.md`

---

## WBA (Warm Boot Analysis) automation
- **EventBridge** triggers a Step Function after each run ends.
- Steps:
  1. Lambda aggregates metrics from RDS + CloudWatch.
  2. Applies SIP‑005 attribution (PRD/Agent/Squad/Ops).
  3. Emits **Good/Bad/Ugly** + **Recommendations** to S3 as `WBA.md` (SIP‑006/6.1).
  4. Notifies Slack/Email with a link and diff summary.
- Optional: render HTML/PDF for the console.

---

## GPU path (when you outgrow Bedrock or need custom models)
- **ASG** of GPU nodes (EC2 Launch Template) in private subnets.
- **Capacity providers** in ECS tied to the GPU ASG (spot + on‑demand mix).
- **NLB** internal → “model‑gateway” service (gRPC/HTTP).
- **Auto‑scaling** on QPS/backlog; **schedules** to shut down nights/weekends.
- Keep model weights in **EFS** or encrypted S3 + local caching.

---

## Terraform module sketch (pseudo)
```
module "network" { vpc_cidr = "10.0.0.0/16"; subnets_public = 2; subnets_private = 2 }
module "rds"     { engine = "postgres", size = "t3.small", multi_az = false }
module "ecr"     {}
module "ecs"     { cluster = "squadops"; services = ["orchestrator","pak","lore","trin","rune","rachael","yelena","rom"] }
module "sqs"     { queues = ["flips","imports","digital"]; dlq = true }
module "secrets" { items = ["db_url","api_keys/*"] }
module "alb"     { target = "orchestrator" }
module "eventbridge_wba" { rule = "run-finished"; target = "stepfunctions_wba" }
```

---

## Deployment steps (fast path)
1. **Bootstrap repo**: `infra/` (Terraform), `services/` (Dockerized agents).
2. **Create ECR** repos; build/push images for all agents + orchestrator.
3. **terraform apply** for: VPC, RDS, ECS, SQS, Secrets, ALB, EventBridge.
4. **Seed DB** with baseline SIP entities (PRD, Agent DNA v1.0.0, Squad v1.0).
5. **Set budgets/alarms** and NAT/GPU schedules (if any).
6. **Run first WarmBoot** → verify logs/metrics, WBA report in S3.
7. **Tighten IAM** and scale task counts as needed.

---

## Operational playbook
- **Daily**: review WBA summary, approve any agent DNA bumps, confirm bankroll limits (Rom).
- **Weekly**: capacity/cost review, tweak queues/concurrency.
- **Monthly**: resilience test (chaos day), restore drill from backup snapshot.

---

## What to start with today
- MVP on **Fargate + Bedrock** (no GPU ops). Get WBA cycle running.
- As throughput grows, add **GPU capacity** and move select agents to GPU workers.
- Keep **horizontal scaling** focus for the Paperclip squad: more low‑ticket flips at steady margins.
