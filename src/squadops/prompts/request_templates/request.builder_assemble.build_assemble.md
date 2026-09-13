---
template_id: request.builder_assemble.build_assemble
version: "4"
required_variables:
  - prd
  - source_files
optional_variables:
  - prior_outputs
  - task_tags
  - task_section
  - contract_expectations
---
## Product Requirements Document

{{prd}}
{{task_section}}
{{contract_expectations}}

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

```markdown:assembly_notes.md
The image runs as UID 1000 and the data directory must be writable by it; a
read-only mount makes every write endpoint return 500.
```
````

Output that does NOT use this exact `<language>:<filepath>` header will be rejected.

## File path rules

- File paths use forward slashes only. No colons, no spaces, no leading slash.
- Do NOT re-emit source files the developer already wrote.
- Only emit NEW files needed for packaging and deployment.

## Which files to produce

The exact set of required and optional files for this build is given in the
system prompt for the build profile. Produce every required file. Produce an
optional one only when it earns its place.

`assembly_notes.md` is the optional file to be most careful with. It carries
only what the test author cannot already have — the system prompt lists what
the stack's contracts already supply, and restating any of it is worse than
writing nothing. Omitting the file is a complete answer.

Where a Contract Expectations block appears above, every one of its checks is
evaluated against your output exactly as written.
