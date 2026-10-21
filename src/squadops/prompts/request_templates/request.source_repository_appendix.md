---
template_id: request.source_repository_appendix
version: "2"
required_variables:
  - commit
  - repository_map
optional_variables:
  - checks
  - instructions
  - existing_files
---

## THE PRODUCT YOU ARE CHANGING

This cycle changes an existing product, in its own repository, at commit `{{commit}}`. It is not a
new app. Its layout, its tools and its conventions are the product's, and they stay as they are.

Every file it holds at that commit:

{{repository_map}}

{{checks}}

{{instructions}}

{{existing_files}}

A file you emit replaces that path whole, so emit each file you change in full, with your change,
at its own path exactly as the map writes it. A path you don't emit keeps its content at that
commit. A new file goes where the product's own layout would put it.
