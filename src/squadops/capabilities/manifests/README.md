# Capability Manifests

This directory contains capability contracts, workload definitions, and JSON schemas
per SIP-0.8.6.

## Directory Structure

```
manifests/
├── README.md                          # This file
├── schemas/                           # JSON Schema definitions
│   ├── capability_contract.schema.json
│   ├── workload.schema.json
│   └── workload_run_report.schema.json
├── contracts/                         # Capability contracts by domain
│   └── data/
│       ├── collect_cycle_snapshot.yaml
│       ├── profile_cycle_metrics.yaml
│       └── compose_cycle_summary.yaml
└── workloads/                         # Workload definitions
    └── data_cycle_wrapup_smoke.yaml
```

## YAML Conventions

### Capability Contracts

Contracts define what a capability accepts and produces:

```yaml
capability_id: domain.capability_name    # e.g., data.collect_cycle_snapshot
version: 1.0.0                           # Semantic version
description: >                           # Multi-line description
  Human-readable description of
  what this capability does.

owner_roles:                             # Roles that can fulfill this
  - data

lifecycle_scope: cycle                   # cycle, pulse, or project
trigger: on_demand                       # on_demand, scheduled, event_driven

inputs:                                  # Input parameters
  - name: cycle_id
    type: string                         # v1: string, number, boolean only
    required: true
    description: Parameter description

outputs:                                 # Output values
  - name: artifact_count
    type: number
    description: Output description

artifacts:                               # File outputs
  - name: snapshot_manifest
    path_template: runs/{cycle_id}/snapshots/cycle_snapshot.json
    description: Artifact description

acceptance_checks:                       # Validation checks
  - check_type: file_exists              # file_exists, non_empty, json_field_equals
    target: runs/{cycle_id}/snapshots/cycle_snapshot.json
    description: Check description

timeout_seconds: 120
```

### Workloads

Workloads compose capabilities into DAGs:

```yaml
workload_id: workload_name
version: 1.0.0
description: >
  Multi-line description.

vars:                                    # Global variables
  default_value: true

tasks:                                   # Task sequence (DAG)
  - task_id: first_task
    capability_id: domain.capability
    inputs:
      param: "{cycle_id}"                # Template syntax
      var_param: "{vars.default_value}"
    depends_on: []                       # No dependencies

  - task_id: second_task
    capability_id: domain.other_capability
    inputs:
      from_first: "{first_task.output_name}"
    depends_on:
      - first_task                       # Depends on first_task

acceptance_checks:                       # Workload-level checks
  - check_type: file_exists
    target: runs/{cycle_id}/final_output.json
```

## Template Syntax

Templates use `{variable}` syntax:

| Variable | Description |
|----------|-------------|
| `{cycle_id}` | Current cycle identifier |
| `{workload_id}` | Workload identifier |
| `{run_root}` | Run root directory |
| `{vars.name}` | Workload variable |
| `{task_id.output_name}` | Task output value |

## v1 Primitive Types

SIP-0.8.6 v1 supports only primitive types:

- `string`: Text values
- `number`: Integer or floating-point
- `boolean`: true/false

## Acceptance Check Types

| Type | Required Fields | Description |
|------|-----------------|-------------|
| `file_exists` | `target` | Verify file exists |
| `non_empty` | `target` | Verify file exists and is non-empty |
| `json_field_equals` | `target`, `field_path`, `expected_value` | Verify JSON field has expected value (strict type check) |

### json_field_equals Notes

- Uses dot-path notation: `metadata.status`
- Type comparison is strict: `1` (int) != `1.0` (float)
- Only primitive expected values allowed
