---
template_id: request.builder_assemble.build_assemble
version: "2"
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

## Output format (MANDATORY)

Each file MUST be emitted as a fenced code block whose opening line is `` ```<language>:<filepath> `` — language and filepath separated by a single colon, no space, on its own line. Closing line is `` ``` ``.

Worked example (copy this exact shape):

````
```dockerfile:Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "-m", "myapp"]
```

```markdown:qa_handoff.md
## How to Run
docker build -t myapp . && docker run -p 8000:8000 myapp

## How to Test
pytest

## Expected Behavior
Service responds with HTTP 200 on GET /health.
```
````

Output that does NOT use this exact `<language>:<filepath>` header will be rejected.

## File path rules

- File paths use forward slashes only. No colons, no spaces, no leading slash.
- Do NOT re-emit source files the developer already wrote.
- Only emit NEW files needed for packaging and deployment.

## Which files to produce

The exact set of required and optional files for this build, plus the
`qa_handoff.md` required sections, is given in the system prompt for the
build profile. Produce exactly that set — no more, no less.
