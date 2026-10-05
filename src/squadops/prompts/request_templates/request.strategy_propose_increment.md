---
template_id: request.strategy_propose_increment
version: "8"
required_variables:
  - objective_statement
  - objective_measurement
  - allowed_scope_lines
  - baseline_manifest
  - prior_criteria_lines
optional_variables:
  - frozen_conventions_section
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

**Criteria earlier increments froze**: each is something the application already does. Every one
keeps passing unless you retire it, with a reason, and the supervisor rules on the retirement. A
proposal that asserts one of them again adds nothing a test can fail on before the change:
{{prior_criteria_lines}}

**Each criterion you add names something the application does not do yet.** The evaluation runs its
test against the accepted application before your change, and the test must fail there, then pass
after it. A criterion the accepted application already meets cannot be proven, and the proposal is
returned. The usual miss is the default case of the feature you add. For a capacity limit, "a run
created without a capacity still accepts a tenth join" holds today, before any capacity exists, so it
is not a criterion. "A third join to a run with capacity 2 is refused" is, because today it succeeds.

**Your `prd_delta` states only what the rest of your request delivers.** The build implements the
`manifest_delta` inside the files it derives, and the evaluation checks your criteria. The PRD text is
read afterwards as true of the application. So a sentence in `prd_delta` that no `manifest_delta`
entry, criterion or footprint file carries describes something no build will do. For example, a
capacity change whose `prd_delta` said "show capacity status in run detail", while its
`manifest_delta` changed no client route and no criterion named the detail view, asked for a display
nothing would build, and it was returned. Either carry the display (the client route's change and a
criterion on it) or leave it out of the text.

{{frozen_conventions_section}}
{{supervisor_note_section}}
{{abandoned_increment_section}}
{{prd_section}}
**The manifest below is what the application does.** Every endpoint, error code, field and client
route it declares is built, accepted and running, so a criterion about one of them names nothing new.
Your change is what `manifest_delta` adds or modifies: the build may touch only the files those
declarations expand to, and tests. A `feature` or `fix` with an empty `manifest_delta` gives the build
nothing to change, and is refused. For example: where the manifest already gives Run a `capacity`
and the join endpoint a `capacity_reached` error, the capacity limit is already enforced, and
proposing it again with an empty delta has nothing to build.

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
