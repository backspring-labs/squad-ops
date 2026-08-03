---
template_id: request.plan_reroll_rejected_plan_appendix
version: "1"
required_variables:
  - rejected_plan_yaml
---
The rejected plan, for revision reference (fix the listed defects; keep what was sound):

```yaml
{{rejected_plan_yaml}}
```
