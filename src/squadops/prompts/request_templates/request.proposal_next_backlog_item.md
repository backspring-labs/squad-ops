---
template_id: request.proposal_next_backlog_item
version: "1"
required_variables:
  - item_id
  - item_title
  - item_description
  - serves_lines
---
**Your proposal serves {{item_id}}, and only it:** {{item_title}}. {{item_description}}

It is the first item of the order still pending in this campaign. Accepted items are built already,
and an abandoned item waits until the owner revises it. It serves these expected results, so your
criteria show them holding where they can be observed:
{{serves_lines}}

Name it in your change request, beside `kind`:

```yaml
backlog_item: {{item_id}}
```

A proposal that names another item, or none, is returned.
