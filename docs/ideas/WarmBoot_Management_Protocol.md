# ✅ WarmBoot Management & Deployment Protocol (v1.0)

------------------------------------------------------------------------

## 📌 Purpose

Define a repeatable, governed process for running, managing, and
deploying **WarmBoot executions** in SquadOps.\
This ensures that requirements, implementations, failures, and
deployments are all **traceable to PIDs** and **reproducible from Git
history**.

------------------------------------------------------------------------

## 🔑 Core Principles

1.  **PID = anchor**
    -   One Process ID (PID) per business process.\
    -   All artifacts (BP, UC, TC, wireframes, diagrams) inherit PID.
2.  **PRD = requirements definition**
    -   Each PRD (`PRD-###-App.md`) defines the scope for a WarmBoot
        run.\
    -   New PRD when requirements change. Same PRD for retries.
3.  **Run = execution attempt**
    -   Each WarmBoot run gets its own branch and Run-ID.\
    -   Always linked back to PRD + PID.\
    -   Every run, success or failure, is logged and tagged.
4.  **Transparency \> Ego**
    -   Failed runs are preserved for root cause analysis.\
    -   Failure signals are logged, not hidden.

------------------------------------------------------------------------

## ⚙️ Workflow

### 1. Prep

-   Assign PID in `process_registry.md` (`PID-001: HelloSquad`).
-   Write PRD under `/docs/prd/PRD-###-{App}.md`.
-   Check in to GitHub before WarmBoot kickoff.

### 2. Run Execution

-   Console starts run → select PRD.
-   Branch created: `warmboot/run-###`.
-   Agents execute tasks:
    -   **Max** orchestrates & approves
    -   **Neo** codes
    -   **EVE** tests
    -   **Data** logs metrics
-   Artifacts produced under PID:
    -   `/business_processes/BP-###.md`
    -   `/use_cases/UC-###.md`
    -   `/testing/test_cases/TC-###.md`

### 3. Logging

-   Task logs → Postgres.
-   Run summary created under `/warmboot_runs/run-###-summary.md`.
-   Mermaid Gantt snippet auto-generated.
-   Metrics (time, duration, failures) captured per agent.

### 4. Git Tags

-   Each run tagged:
    -   `v0.1-warmboot-001`\
    -   `v0.2-warmboot-002`\
-   Stable releases merged to `main` tagged:
    -   `v1.0`, `v1.1`, etc.

### 5. Deployment

-   Use **release manifest** under `/warmboot_runs/run-###/` to pin
    infra + code versions.\

-   Redeploy old run by checking out its branch or tag:

    ``` bash
    git checkout warmboot/run-007
    docker compose -f infra/compose.yaml --env-file warmboot_runs/run-007.env up -d
    ```

-   For hotfixes: branch off past run → patch → tag as
    `v0.x.y-warmboot-###-hotfix`.

------------------------------------------------------------------------

## 🔄 Decision Rules

-   **Requirements flawed?** → New PRD (`PRD-002-...`), new run.\
-   **Agent code flawed?** → Same PRD, new run (`run-002`).\
-   **Business process changed?** → New PID.\
-   **Need to redeploy historical build?** → Checkout its run
    branch/tag.

------------------------------------------------------------------------

## 📂 Directory Structure (HelloSquad Example)

    /docs/prd/
       PRD-001-HelloSquad.md
    /docs/framework/business-processes/
       BP-001-HelloSquad.md
    /docs/framework/use-cases/
       UC-001-HelloSquad.md
    /testing/test_cases/
       TC-001-HelloSquad.md
    /warm-boot/runs/
       run-001-summary.md
       run-001-logs.json
       run-001.env
       release_manifest.yaml

------------------------------------------------------------------------

## ✅ Governance & Compliance

-   **Max** ensures every run links to a PRD + PID.\
-   **EVE** validates test artifacts exist before merge.\
-   **Data** verifies KDEs and metrics mapping.\
-   **Nat** and **Joi** ensure tagging/UX docs align with use cases.

------------------------------------------------------------------------

## ✅ Benefits

-   Reproducibility: Any run can be redeployed.\
-   Traceability: Clear linkage PRD → Run → PID.\
-   Transparency: Failures are logged, not hidden.\
-   Governance: Testing, data, and tagging integrated into each
    WarmBoot.

------------------------------------------------------------------------

> This protocol ensures that WarmBoot runs are **managed like production
> releases** --- reproducible, auditable, and tied to requirements and
> processes, while enabling rapid iteration without losing discipline.
