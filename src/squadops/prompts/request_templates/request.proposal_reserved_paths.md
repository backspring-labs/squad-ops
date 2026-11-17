---
template_id: request.proposal_reserved_paths
version: "1"
required_variables:
  - reserved_lines
---
**Paths the product's owner reserves.** The owner changes these themselves, and no cycle writes
them. A change request whose `footprint` names one is refused, and so is a build that changes
one. Propose a change that leaves them as they are. If the item can't be done without one, say
so in `prd_delta` and propose the part that can (a path with no `*` is a file, or a folder and
everything in it):
{{reserved_lines}}
