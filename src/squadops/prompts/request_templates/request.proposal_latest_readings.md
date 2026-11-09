---
template_id: request.proposal_latest_readings
version: "1"
required_variables:
  - reading_lines
---
**How the product measured at the last increment this campaign accepted.** Each line is what the
product's own reading printed. Tests passing says the criteria held; this says what the product did.
It doesn't decide whether your change is accepted:
{{reading_lines}}
