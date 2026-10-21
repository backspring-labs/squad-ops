---
template_id: request.source_repository_checks_block
version: "1"
required_variables:
  - checks
---

### How the product is checked

When the squad's work is done, the product's own checks run against it with your change, in the
product's own environment, and each is compared with how it ran before any change:

{{checks}}

So a test you add goes where these checks find it, named the way the product's own tests are, and
it runs with them. An acceptance criterion that runs a command can't run the product here:
describe what must hold, and these checks run it.
