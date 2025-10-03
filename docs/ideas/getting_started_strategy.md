# 🚀 Getting Started Strategy for SquadOps

This guide provides a **zero-entry on-ramp** into SquadOps: starting
with the simplest introduction, then moving hands-on quickly, and
finally deepening into the core pool of protocols and practices.

------------------------------------------------------------------------

## 1. 🎧 Intro Concepts --- Zero Entry Point

Start here to build intuition before touching any code. These are the
minimum concepts to understand *why SquadOps exists* and *what makes it
different*.

-   **Chapter 1 & 2 of the SquadOps Book Draft**
    -   *Promise of Agent Squads*\
    -   *Forming Your First Squad*
-   **Meta Mission Statement** --- the Squad ↔ Business ↔ Guide flywheel
-   **Summarized Path of SquadOps Design** --- one-page history of the
    evolution
-   **Why Squads Failure Signals** --- explains why agent squads are
    different from human teams

📌 *Optional*: Provide these as a short **narrated audio aid (\~15
minutes)** so newcomers can absorb the vision quickly.

------------------------------------------------------------------------

## 2. 🛠 Hands-On Quickstart --- HelloSquad (Day 1 Plan)

The fastest way to understand SquadOps is to *run a squad*. The Day 1
Plan provides the "Hello World" of SquadOps.

### Steps

1.  Clone the `squad_ops` repo scaffold.
2.  Run Docker Compose to spin up core infra: **RabbitMQ + Postgres +
    Prefect + Max/Neo containers**.
3.  Launch the **HelloSquad** API (`/hello`).
4.  Run the first WarmBoot (Max + Neo only).
5.  Tag the run branch: `v0.1-warmboot-001`.
6.  Generate a Mermaid Gantt snippet of the run.

### Stretch Goal (Day 2)

-   Add **EVE** for test automation.
-   Enable **task logging** into Postgres.\
-   Launch the **Health Check Page** at `/health`.

------------------------------------------------------------------------

## 3. 📚 Core Protocol Anchors --- The Deep Pool

After the first hands-on run, dive into the structured knowledge base.
These protocols are the **anchor points** of SquadOps:

1.  **PID Traceability Protocol** --- everything hangs off a Process
    ID.\
2.  **Testing Protocol** --- ensures functional, performance, and
    security validation.\
3.  **Data Governance Protocol** --- enterprise-grade data lineage and
    compliance.\
4.  **Task Logging & Metrics Protocol** --- observability and
    optimization through logs.

------------------------------------------------------------------------

## 4. 🏊 Learning Progression Path

1.  **Read + Listen**: Ch1--2, Mission Statement, Design Summary,
    Failure Signals.\
2.  **Run HelloSquad (Day 1)**: feel the system work in practice.\
3.  **Explore PID**: see how processes bind all artifacts and tasks.\
4.  **Add Testing & Governance**: realize squads aren't just dev tools,
    but an operational model.\
5.  **Scale Up**: run a WarmBoot on a larger reference app (fitness
    tracker).

------------------------------------------------------------------------

✅ This strategy creates a **low-friction on-ramp** (audio + Day 1 run)
and then deepens into the structured pool of protocols once success is
felt.
