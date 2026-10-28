---
template_id: request.source_repository_runners_block
version: "1"
required_variables:
  - runners
optional_variables: []
---

Those checks run the product's tests with its own runners. Each runner finds a test file under
one of its roots, by its name, and runs it for the product paths it tests:

{{runners}}

A test file under no runner's root, or named as no runner takes tests, is never run, and verifies
nothing.
