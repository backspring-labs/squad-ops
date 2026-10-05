---
template_id: request.proposal_convention_required_string_trimmed
version: "1"
required_variables:
  - code
---
**A required string in a request is trimmed, and a blank one is refused, before any handler runs.**
The frozen request models strip the whitespace around every required string and refuse an empty
result with `{{code}}`, at the status the manifest's error contract gives it. So "a name joined with
surrounding spaces is stored trimmed" and "a whitespace-only name is refused" already hold, and
neither is a new criterion.
