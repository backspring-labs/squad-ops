---
template_id: request.source_repository_new_files_block
version: "1"
required_variables:
  - files
optional_variables: []
---

The product holds no file at these paths this task names:

{{files}}

Each is a new file: write it whole. A change to a file the product holds goes at that file's own
path, exactly as the map writes it.
