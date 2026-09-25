---
template_id: request.disputed_checks_appendix
version: "1"
required_variables: []
optional_variables: []
---
### If a check you were given is wrong

If you believe one of the checks or criteria above is wrong, or does not apply to this task,
do not work around it and do not degrade correct work to satisfy it. Name it in one block at
the end of your response, after your files:

```disputed_checks
- check: acceptance:declared_imports
  file: frontend/src/views/RunList.jsx
  criterion_id: vc-view-compiles-run-list
  reason: the @/lib alias is declared in tsconfig.json's paths, which the check does not read
```

`check` is the check's name as it was given to you; `file` and `criterion_id` say which one when
the same check ran on several. A dispute is read and judged; it never passes a failing check by
itself, so still emit your best work for everything you do not dispute.
