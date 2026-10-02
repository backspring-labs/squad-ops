---
template_id: request.strategy_propose_increment
version: "2"
required_variables:
  - objective_statement
  - objective_measurement
  - allowed_scope_lines
  - baseline_manifest
  - prior_criteria_lines
optional_variables:
  - supervisor_note_section
  - prd_section
  - abandoned_increment_section
---
## Propose the next increment of this application

The application below is accepted and running. Your job is to propose **one** change that moves it
toward the campaign's objective, small enough to build and verify in one cycle. You do not build it.
A supervisor rules on your proposal; only an approved proposal is built.

**The objective:** {{objective_statement}}

**How the campaign will know it is met:** {{objective_measurement}}

**The files a proposal may reach** (a proposal whose change reaches outside these is refused whole,
not trimmed):
{{allowed_scope_lines}}

**Criteria earlier increments froze** (every one keeps passing unless you retire it, with a reason,
and the supervisor rules on the retirement):
{{prior_criteria_lines}}
{{supervisor_note_section}}
{{abandoned_increment_section}}
{{prd_section}}
### The accepted application's interface manifest, exactly as it stands

```yaml
{{baseline_manifest}}
```

### What you emit

Exactly one fenced block whose header carries the filename `change_request.yaml`, in this shape. The
example proposes a different application's change; yours changes the manifest above.

```yaml:change_request.yaml
kind: feature            # feature | fix | refactor (a refactor adds no new criteria)
prd_delta:
  - id: item-tags
    op: add              # add | modify | retire
    text: "An item may carry tags, and the list can be filtered by one tag."
manifest_delta:
  # add and modify carry the target's WHOLE new definition, written exactly as the manifest above
  # writes that kind of thing; remove carries none.
  - op: modify
    target: entity       # entity | request_shape | endpoint | client_route | error_code
    key: Item            # entity / request_shape: its name; endpoint: "METHOD /path";
                         # client_route: its path; error_code: the code
    definition:
      name: Item
      fields:
        - { name: id, type: string, required: true, generated: true }
        - { name: title, type: string, required: true }
        - { name: tags, type: "list[string]", required: false, default: [] }
  - op: add
    target: error_code
    key: unknown_tag
    definition: { http: 422 }
criteria:
  - id: T1
    statement: An item created with tags returns them
    surface_kind: endpoint          # endpoint | client_route
    surface: "POST /items"          # must exist in the manifest your delta produces
    observable: "the 201 response carries tags: ['a']"
must_not_break: []                  # earlier criteria ids, from the list above
```

Write `key` exactly as the manifest writes the thing it names. Every error code an endpoint lists
must be defined under `error_contract.codes`: add the code in the same change when it is new.

The framework derives the files your change touches from the manifest it produces, and computes
the proposal's identity and hash. Leave `footprint`, `content_hash`, `proposal_id` and `version`
out: a proposal that sets them is refused.
