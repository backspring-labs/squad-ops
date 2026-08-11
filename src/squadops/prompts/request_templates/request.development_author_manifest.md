---
template_id: request.development_author_manifest
version: "1"
required_variables:
  - prd
  - stack
optional_variables:
  - time_budget_section
  - prior_outputs
  - authoring_rules_section
  - rejection_context_section
---
You are authoring this build's **interface manifest** — the typed description of the
application's interface that everything downstream is generated from.

This build is **scaffolded**: a deterministic tool expands your manifest into the wired,
buildable skeleton — entry files, config, data models, route stubs, error handling,
frontend routing — and the verification contract is derived from the same document. The
squad then fills only the endpoint and component *bodies*. So the manifest fixes the
interface for every author who comes after you: what they implement, and what they are
tested against.

Describe the **interface**, never the implementation. No endpoint logic, no component
code, no algorithms. If you find yourself deciding *how* something works rather than *what
its shape is*, that belongs to the developer filling the body — unless it is a judgment
the interface has to fix for the frontend and backend to agree, in which case it goes in
`decisions[]`.

## Product Requirements Document

{{prd}}
{{time_budget_section}}
{{prior_outputs}}
## Output

Emit exactly one fenced block, with this filename and this schema:

```yaml:interface_manifest.yaml
version: 1
kind: interface_manifest
project_id: <short-slug-for-this-app>
source_prd: <path or name of the requirements document above>
stack: {{stack}}
scope: <one line on what this manifest covers, and what it deliberately leaves out>
entities:                          # the data types the app stores and returns
  - name: Item
    fields:
      - { name: id,      type: string,  required: true, generated: true }
      - { name: title,   type: string,  required: true }
      - { name: done,    type: boolean, required: false, default: false }
      - { name: tags,    type: "list[Tag]", required: false, default: [] }   # QUOTE bracket types
api:
  base_path: ""                    # "" when the PRD's paths are unprefixed (/items)
  request_shapes:                  # request BODIES — a projection of entity fields
    ItemCreate:
      required: [title]
      optional: [done]
  endpoints:                       # every HTTP endpoint the app exposes
    - { method: GET,  path: /items, summary: list items,
        response: "list[Item]" }
    - { method: POST, path: /items, summary: create item,
        request: ItemCreate, response: Item,
        success_status: 201,
        errors: [validation_error] }
    - { method: GET,  path: "/items/{item_id}", summary: item details,
        response: Item, errors: [item_not_found] }
  error_contract:
    shape: '{"error": {"code": "...", "message": "..."}}'
    codes:
      validation_error: { http: 422 }
      item_not_found:   { http: 404 }
frontend:
  framework: react_vite
  routes:                          # one view component per route
    - path: /
      view: ItemsListView
      purpose: list items and a create form
      testids: [items-view, item-list, item-row, create-item-form, create-item-submit]
    - path: /items/:item_id
      view: ItemDetailView
      purpose: one item's details
      testids: [item-detail-view, item-title, item-status]
persistence: in_memory
decisions:                         # judgments the schema cannot express mechanically
  - id: item-ordering
    choice: newest first
    warrant: "PRD §3.2 — 'the most recent items appear at the top'"
  - id: pagination
    unresolved: true
    question: "PRD does not state a page size or whether listing is paginated at all"
```

**A type containing brackets must be quoted.** `type: list[Tag]` inside a `{ ... }`
entry is invalid YAML — the `[` opens a flow sequence and the document fails to parse
before any gate can read it. Write `type: "list[Tag]"`. This is the single most
common reason a first manifest attempt is rejected.

The example is illustrative. Replace it with THIS build's real entities, endpoints,
routes, anchors and decisions, drawn from the PRD and the framing documents above.

Fields that are **not** manifest content, because the blueprint owns them: entrypoints,
build/proxy config, CORS wiring, the standard health endpoint, test-runner wiring, and
package manifests. Do not declare them.
{{authoring_rules_section}}
{{rejection_context_section}}
