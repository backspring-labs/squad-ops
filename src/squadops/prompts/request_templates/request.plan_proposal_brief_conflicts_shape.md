---
template_id: request.plan_proposal_brief_conflicts_shape
version: "1"
required_variables: []
optional_variables: []
---
brief_conflicts: []
# Leave the list empty when you agree with the brief. To disagree, write one entry per
# disagreement in place of the empty list, each with exactly these field names. An entry
# written with other field names can't be read as a conflict.
# brief_conflicts:
#   - brief_field: must_cover_requirements   # the brief's field you disagree with
#     proposed_change: "Drop the generated report from the first task's expected_artifacts."
#     reason: "The brief asks a task to write a file outside the paths this plan may write."
#     severity: warning                      # warning: recorded, and the plan proceeds
#                                            # blocking: an operator rules before the build
#     affected_proposal_task_keys: []        # the focus of each task above that depends on it
