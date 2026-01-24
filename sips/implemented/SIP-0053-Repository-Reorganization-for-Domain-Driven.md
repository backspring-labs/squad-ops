---
sip_uid: 01KEM71ECNVNS63NBBGJ7RNPBG
sip_number: 53
title: Repository Reorganization for Domain-Driven Design (DDD) and Hexagonal Isolation
status: implemented
author: Gemini (AI Thought Partner)
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T11:26:01.485581Z'
original_filename: SIP-REPO-REORG-DDD.md
---
# SIP-REPO-REORG-DDD — Version Target 1.0.0
Repository Reorganization for Domain-Driven Design (DDD) and Hexagonal Isolation

**Status:** Proposed  
**Target Version:** 1.0.0  
**Author:** Gemini (AI Thought Partner)  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

## 1. Purpose and Intent

This SIP defines the wholesale reorganization of the SquadOps repository to implement Domain-Driven Design (DDD) and Hexagonal Architecture. The intent is to establish a "Locked Architectural Boundary" between the SquadOps Engine (Python execution) and the Continuum Control-Plane (UI/Dashboard framework).

By adopting a src/ layout, we isolate the Cycle Protocol (Cycles, Pulses, Surges) from external vendor implementations, ensuring the framework is deterministic and scalable.

## 2. Problem Statements

**Logic Entanglement:** Agent capabilities and telemetry are currently interleaved with core execution logic.

**Boundary Leakage:** The framework lacks a formal boundary between the engine and UI surfaces, risking circular dependencies.

**Testing Regression:** Existing unit tests are coupled to a directory structure that is being deprecated.

## 3. Design Overview (Authority vs. Intent)

**Coordination Authority (Pulse):** All state management and "rewind boundaries" move to src/squadops/execution/.

**Execution Intent (Surge):** Task grouping and parallel execution logic are isolated within the execution context to prevent "stop and wait" bottlenecks.

**Bounded Contexts:** Each major concern (Memory, Observability, Artifacts) is isolated in its own directory under src/squadops/.

## 4. Immutable Invariants (The Guardrails)

**Rule 1:** src/squadops/core/ MUST NOT import from any other internal sub-package.

**Rule 2:** Core logic MUST NOT import from adapters/ or control-plane/.

**Rule 3:** The core remains the only legal home for shared IDs and system-wide constants.

## 5. Dependency & Impact Map

| Component | Action | Impact Level |
|-----------|--------|--------------|
| base_agent.py | Relocate to execution/ | High |
| agents/capabilities/ | Migrate to _v0_legacy/ | High |
| tests/ | Refactor for src/ layout | High |
| pyproject.toml | Full Rewrite | Medium |

## 6. Functional Requirements

**Namespace Transition:** All code must be importable via the squadops.<context> namespace.

**Adapter Decoupling:** Vendor-specific code (Langfuse, LanceDB) must move to adapters/ and satisfy interfaces in ports/.

**Legacy Access:** The _v0_legacy folder must remain accessible for a 48-hour migration period but must not be included in the final 1.0.0 build.

## 7. Implementation Considerations

**Python Path:** Using pip install -e . is required to link the new src/ layout to the development environment.

**OSGi Compatibility:** The control-plane/ must be structured to eventually support OSGi-style plug-ins via manifest.yaml.

## 8. Executive Summary — What Must Be Built

- [ ] Engine Shell: Initialize the src/squadops/ directory tree with __init__.py files.
- [ ] Legacy Archival: Move agents/, infra/, and config/ to _v0_legacy/.
- [ ] Test Refactor: Create tests/unit/core/ and tests/unit/execution/ to mirror the new structure.
- [ ] Build Config: Implement the src layout in pyproject.toml.

## 9. Test-Driven Definition of Done

- [ ] Namespace Test: import squadops.core succeeds in a clean virtual environment.
- [ ] Isolation Test: Running a test in src/squadops/core/ fails if it attempts to import from _v0_legacy/.
- [ ] Legacy Migration: At least one core capability (e.g., data.collect_cycle_snapshot) is migrated and passes unit tests in its new home.
- [ ] Rewind Test: A "Pulse" boundary test confirms that state restoration still functions under the new architecture.
