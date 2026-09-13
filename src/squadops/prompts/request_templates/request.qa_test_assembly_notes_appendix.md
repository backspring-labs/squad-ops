---
template_id: request.qa_test_assembly_notes_appendix
version: "1"
required_variables:
  - notes
  - artifact_id
optional_variables: []
---
**ASSEMBLY NOTES FROM THE BUILDER** (artifact `{{artifact_id}}`):

{{notes}}

The builder wrote these while packaging the application you are testing. They are the
one thing about the delivered system that is not already in the contracts you were
given, so read them for what they change about behaviour — a credential the app needs,
a path or permission the packaging fixes, a deviation from the obvious deployment.

They are notes, not a contract. Where they disagree with the interface manifest or the
behaviour contract above, those win, and the disagreement is itself worth a test.
