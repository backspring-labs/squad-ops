---
template_id: request.disputed_checks_appendix
version: "1"
required_variables:
  - checks
optional_variables: []
---
### If a check you are judged by is wrong

Checks you may dispute:

{{checks}}

If you believe one of these is wrong, or does not apply to this task, do not work around it and
do not degrade correct work to satisfy it. Name it in one block at the end of your response,
after your files, copying its `check`, `file` and `criterion_id` exactly as listed above and
saying why:

```disputed_checks
- check: acceptance:declared_imports
  file: frontend/src/views/RunList.jsx
  criterion_id: vc-view-compiles-run-list
  reason: the @/lib alias is declared in tsconfig.json's paths, which the check does not read
```

A dispute is read and judged; it never passes a failing check by itself, so still emit your best
work for everything you do not dispute.
