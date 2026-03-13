---
template_id: request.builder_assemble.build_assemble
version: "1"
required_variables:
  - prd
  - source_files
optional_variables:
  - prior_outputs
  - task_tags
---
## Product Requirements Document

{{prd}}

## Source Files (from developer)

{{source_files}}
{{prior_outputs}}
{{task_tags}}

You are ASSEMBLING the source code above into a deployable package. Do NOT rewrite or regenerate the source code — it is already written. Your job is to add deployment and packaging artifacts.

Use tagged fenced code blocks with the language and path separated by a colon, for example:
```dockerfile:Dockerfile
<content>
```
```markdown:qa_handoff.md
<content>
```

Produce the following deployment artifacts:
- __main__.py entrypoint (if not already present)
- Dockerfile for containerized deployment
- requirements.txt (if not already present)
- Any startup scripts or config files needed for deployment

IMPORTANT: You MUST also include a `qa_handoff.md` file with these required sections:
- ## How to Run
- ## How to Test
- ## Expected Behavior

File path rules:
- File paths must use forward slashes, no colons, no spaces.
- Do NOT re-emit source files that the developer already wrote.
- Only emit NEW files needed for packaging and deployment.
