---
template_id: request.proposal_unset_optional
version: "1"
required_variables:
  - unset_value
---

**An optional field a request leaves out comes back as `{{unset_value}}`, never left out of the
response.** The application's models are frozen from the manifest. Every field with
`required: false` and no default is returned as `"<field>": {{unset_value}}` when the request did not
supply it, so an observable that the field is absent fails on every correct build. For a capacity
added as an optional field, "a run created without a capacity returns `"capacity": {{unset_value}}`"
is checkable; "its response has no capacity key" is not.
