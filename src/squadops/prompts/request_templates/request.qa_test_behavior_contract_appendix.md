---
template_id: request.qa_test_behavior_contract_appendix
version: "1"
required_variables:
  - behavior_lines
optional_variables: []
---
**API BEHAVIOR CONTRACT (authoritative — your assertions MUST match these):**
{{behavior_lines}}

These statuses are pinned by the verification contract and enforced by probes
against the running app. A test that expects a different status for one of
these behaviors is asserting a bug: it will fail against a correct
implementation, and no change to the application code can ever make it pass.
Request paths are exactly as written above — do not add a URL prefix (such as
`/api`) that the contract does not declare; prefixes belong to the frontend
proxy, not the backend under test.
