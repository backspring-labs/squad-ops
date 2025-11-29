---
sip_uid: "01KB65HFBMNSMTDPDSPQJRNWRZ"
sip_number: null
title: "Prefect Integration + Pulse Context Framework"
status: "proposed"
author: "Jason Ladd"
approver: null
created_at: "2025-11-28T21:22:42Z"
updated_at: "2025-11-28T21:22:42Z"
original_filename: "SIP-Prefect-Pulse-Context.md"
---

# SIP: Prefect Integration + Pulse Context Framework (Unnumbered Draft)

## Status
**Draft** — Unnumbered (awaiting maintainer acceptance)

## Overview
This SIP introduces:
- A Prefect-based Task Orchestration Adapter to replace direct SQL-backed task execution logic.
- The Pulse Context abstraction layered between Agent Context and Cycle Context.
- Unified design ensuring Prefect can optionally run tasks while SquadOps retains full control over orchestration semantics, ECIDs, and Cycle Data.

## Goals
1. Introduce a pluggable PrefectTasksAdapter behind the existing Task Adapter Framework.
2. Define Pulse Context as a shared context span covering multi-agent, interdependent sequences.
3. Maintain backward compatibility with SQL adapter and existing FastAPI endpoints.
4. No changes required to SIP: Cycle Data Store — Pulse Context mounts naturally onto its structure.

## Key Requirements
### Prefect Task Adapter
- New module: `agents/tasks/prefect_adapter.py`
- Implements full `TaskAdapterBase`.
- Manages:
  - Prefect flows as EC-equivalent logs
  - Prefect tasks as SquadOps task states
  - Mapping between Prefect state machine and SquadOps TaskState enum
- Integrates with Cycle Context:
  - Pulse ID references
  - ECID references
  - Artifact emission
  - Task status updates

### Pulse Context
Pulse Context sits between:
- **Agent Context** (local LLM scratchpad)
- **Cycle Context** (EC-wide shared storage and artifacts)

Pulse Context:
- Tracks inter-agent shared state for a related cluster of tasks.
- Persists to:
  - `cycle_data/ECID/pulses/PULSE_ID/`
- Enables rollback to last known good pulse.
- Enables lower-level milestone checkpoints.

### No Changes to Cycle Data Store SIP
Because:
- Pulse Context writes into a dedicated folder under Cycle Data.
- No structural changes are needed.
- Existing CycleDataStore interface already supports hierarchical artifact writing.

## Architecture Summary
- Task Adapter Registry chooses **sql** or **prefect** depending on `TASKS_BACKEND`.
- FastAPI interface does not change.
- Agents continue using HTTP API.
- Prefect Flows wrap Task-&-Pulse orchestration but never replace SquadOps pipeline controls.

## Deliverables
- `agents/tasks/prefect_adapter.py` implemented.
- Registry support for backend selection.
- Pulse Context interface added to:
  - `agents/context/pulse_context.py`
  - Passed into capability methods that participate in pulses
- Unit tests & integration tests.

## Revision History
- **v0.1 Draft** — Initial creation of SIP.

