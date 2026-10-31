---
template_id: request.proposal_product_tree
version: "1"
required_variables:
  - head_commit
  - repository_map
optional_variables:
  - instructions
---
### The product's tree at commit `{{head_commit}}`

Every file the product holds there. A footprint names these paths, or globs over them, exactly as
the map writes them:

{{repository_map}}
{{instructions}}
