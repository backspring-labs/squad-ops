---
sip_uid: 01KEM71ECNSHEVZPZDPKGZK6ZV
sip_number: 57
title: Hexagonal Layered Prompt System — DDD-Patterned Deterministic Assembly
status: accepted
author: Framework Committee
approver: Jason F Ladd
created_at: '2026-01-24T19:50:00Z'
updated_at: '2026-01-25T21:42:09.134988Z'
---
# SIP-0.8.5: Domain-Driven Layered Prompt System (Hexagonal Architecture)

## 1. Purpose and Intent
This SIP defines a Domain-Driven Prompt System for SquadOps. It moves prompt management from ad-hoc string manipulation to a structured Domain Service. By utilizing Hexagonal Architecture (Ports and Adapters), we decouple the core assembly logic from the storage medium (Mac Filesystem/Containers) and the execution client (BaseAgent). 

The intent is to ensure prompt behavior is deterministic, versioned, and auditable, providing a stable foundation for 0.9.x observability while strictly separating Behavior (Prompts) from State (Message Context).

## 2. Strategic Domain Design (DDD)

### 2.1 Bounded Context: Prompt Assembly
* Aggregate Root: PromptManifest — The single source of truth for all versioned fragments. It handles integrity validation and version anchoring.
* Entity: PromptFragment — An immutable unit of text identified by a fragment_id. It must possess a SHA256 hash and metadata identifying its layer.
* Value Object: AssembledPrompt — The final, immutable output string. It carries a lineage of the fragment hashes used in its construction.
* Domain Service: PromptAssembler — Stateless logic that implements the layering and Winning Rule selection logic.

### 2.2 Core Principles
1. Prompts define behavior, not state. Dynamic run data must be passed via message context, never injected into prompt fragments.
2. Deterministic Assembly: Given the same role, hook, and version, the output hash must be identical.
3. Fail-Fast Sovereignty: If a local file hash mismatch occurs against the Manifest at runtime, the system must halt execution immediately.

## 3. Technical Architecture (Hexagonal)

### 3.1 Ports (Interfaces)
* IPromptRepository (Driven Port): Defines the contract for fetching fragments. It abstracts the storage layer so the Domain logic is isolated from the physical storage implementation.
* IPromptService (Driving Port): The interface used by the BaseAgent to request a prompt assembly based on the current ACI TaskEnvelope.

### 3.2 Adapters (Implementation)
* FileSystemAdapter: macOS/POSIX implementation optimized for local development on your MacBook Pro.
* BaseAgentAdapter: Orchestrates the hook-in to the existing SquadOps BaseAgent lifecycle.

## 4. Selection & Assembly Logic (The "Winning" Rule)

### 4.1 Hierarchical Search Path (Search Order)
The PromptAssembler MUST support an ordered search path to allow role-specific specializations while maintaining shared global standards:
1. Role Specific: agents/prompts/roles/{role_id}/{fragment_id}.md
2. Shared Global: agents/prompts/shared/{layer_type}/{fragment_id}.md

Winning Rule: If a fragment exists in both tiers, the role-specific fragment overrides the shared one.

### 4.2 Deterministic Layer Ordering (Bottom-Up)
The assembler concatenates fragments in this strict sequence:
1. Identity Layer: Agent role identity, tone constraints, and operating boundaries.
2. Global Constraints: Non-negotiables (safety, non-leakage of secrets, ACI immutability).
3. Lifecycle Layer: Instructions specific to the hook (e.g., agent_start, task_complete).
4. Task Type Layer: Behavioral instructions for the ACI task_type (e.g., code_generate).
5. Recovery Layer: (Conditional) Added only during failure analysis or recovery tasks.

## 5. Implementation Specification

### 5.1 Project Organization
The implementation must reside within the squad-ops repository under a domain/prompt_system directory. The Domain Layer contains the assembler logic, frozen dataclasses for models, and domain-specific exceptions. The Ports Layer defines abstract base classes for the Repository and Service. The Adapters Layer contains the storage implementation for Mac filesystem access and the squad-specific implementation for BaseAgent integration.

### 5.2 Fragment Format & Header
All .md fragments MUST include a machine-parseable header block containing a unique fragment_id, the system version, the layer type, and the role IDs it applies to.

### 5.3 Manifest Schema (manifest.yaml)
A master manifest must be maintained at agents/prompts/manifest.yaml. It must enumerate all fragments with their relative paths and SHA256 hashes, anchoring the system to a version.

## 6. Packaging & Migration (Shared vs. Role Packs)

### 6.1 Container Strategy
To support lean agent container builds, global folders (shared/) are copied into all images, while only the specific role folder (roles/{role_id}/) is copied into that agent's image. The PromptAssembler must fail gracefully if a role fragment is missing but a shared fallback exists.

### 6.2 Migration Rules
All duplicated prompts across roles must be moved to the shared directory. Role-exclusive copies of lifecycle prompts should be eliminated unless a specific role requires materially different lifecycle behavior.

## 7. Testing Requirements

### 7.1 Domain Unit Tests (Isolated)
Tests must verify that the PromptAssembler correctly resolves the search path using a Mock Repository. It must confirm that missing mandatory layers trigger a DomainViolation and ensure the assembly hash is 100% deterministic given the same inputs.

### 7.2 Adapter Integration Tests (Mac-Specific)
Tests must verify that the FileSystemAdapter correctly maps POSIX paths on macOS. They must also ensure that changing a fragment file without updating the manifest.yaml triggers a HashMismatchError at runtime.

## 8. Constraints & "Must Not" (Normative)
1. No Runtime Injection: No dynamic strings or runtime data may be inserted into the prompt text.
2. No Ad-hoc Assembly: Agents MUST NOT construct prompts manually; they must request them from the IPromptService.
3. Strict Immutability: Once a cycle starts, fragment hashes are locked. Any mutation triggers an immediate halt.

## 9. Definition of Done
* [ ] PromptAssembler implements the hierarchical winning rule.
* [ ] Integrity hashes are verified before string concatenation.
* [ ] BaseAgent is successfully integrated with the PromptService hooks.
* [ ] Unit tests confirm isolated domain logic works without filesystem access.