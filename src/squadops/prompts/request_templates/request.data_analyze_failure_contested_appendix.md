---
template_id: request.data_analyze_failure_contested_appendix
version: "1"
required_variables:
  - contested
optional_variables: []
---
## Disputed checks

The producer disputed these failed checks: it says the check is wrong, not the work.

{{contested}}

For EACH one, decide from the Failure Evidence whether the dispute holds, and add one entry per
disputed check to your JSON, copying its `check`, `file` and `criterion_id` exactly as listed:

```json
"dispute_rulings": [
  {
    "check": "acceptance:declared_imports",
    "file": "frontend/src/views/RunList.jsx",
    "criterion_id": "vc-view-compiles-run-list",
    "dispute_confirmed": true,
    "reason": "tsconfig.json declares the @/lib alias in compilerOptions.paths; the import resolves"
  }
]
```

Confirm a dispute only when the evidence shows the check itself is wrong for this task: a false
positive, a check run on a tree that lacks the file it reads, a criterion the PRD contradicts.
"The work might be right" is not enough. An unconfirmed dispute is handled as the failure it
disputes, so say which evidence decides it either way.
