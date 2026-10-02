---
template_id: request.increment_framing_section
version: "1"
required_variables:
  - change_request
---

## THIS CYCLE IS AN INCREMENT — the approved change request is its objective

The application the requirements document above describes is already built and accepted. This
cycle changes it, and only as the change request below says. A supervisor approved the change
request against that accepted application: it is this cycle's framed objective, in place of the
research and objective framing a new application gets.

Your deliverable covers this change and nothing else. Re-describing parts of the application the
change does not touch re-decides work that was accepted, and a plan built from it is refused at
the plan gate once it reaches outside the footprint.

What each part of the change request decides:

- `prd_delta`: the requirements this change adds, rewrites or retires. The rest of the
  requirements document stands as accepted.
- `manifest_delta`: the change to the accepted interface. It is already applied, and the build's
  skeleton expands from the result, so design to it rather than redesigning the interface.
- `footprint`: the only files this cycle may change. Every other file keeps its accepted
  implementation, and the build starts from that code.
- `criteria`: what this cycle's tests prove. The accepted application's own checks already pass;
  `must_not_break` names the ones this change must leave passing.

### The approved change request

{{change_request}}
