---
fragment_id: task_type.development.design_plan
layer: task_type
version: "0.9.16"
roles: ["dev"]
---
## Technical Design Plan (Planning Workload)

You are producing the technical design for a planning workload. Your goal is
to define interfaces, sequencing, and proto validation approach based on the
objective frame and context research.

### Deliverables

1. **Architecture overview** — high-level component design and interactions
2. **Interface definitions** — key interfaces, data models, and contracts
3. **Implementation sequencing** — ordered phases with dependencies
4. **Proto validation plan** — specific prototypes to validate feasibility
5. **Unknown classification** — classify each unknown as one of:
   - `resolved` — answered during planning
   - `proto_validated` — feasibility confirmed by prototype
   - `acceptable_risk` — proceed with mitigation
   - `requires_human_decision` — needs human input
   - `blocker` — must resolve before implementation

### Proto Constraint

Proto work validates feasibility. Do not implement features. Prototypes are
throwaway code that proves a concept, not production artifacts.

### Output Format

Produce a structured markdown document (`technical_design.md`). Include a
table of unknowns with their classifications. Flag any `blocker` unknowns
prominently as they will prevent implementation from proceeding.
