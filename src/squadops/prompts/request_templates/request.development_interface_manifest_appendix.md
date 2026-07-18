---
template_id: request.development_interface_manifest_appendix
version: "1"
required_variables:
  - stack
optional_variables: []
---
## Interface manifest (this build is scaffolded)

This build uses **contract-first scaffolding**: a deterministic tool generates the wired,
buildable application skeleton — entry files, config, data models, route stubs, error
handling, and frontend routing — from a typed **interface manifest**, and the developer
then fills only the endpoint and component *bodies*. Your job is to author that interface
manifest: a precise description of the application's **interface**, never its
implementation.

**Emit it as a SECOND fenced block, AFTER your `proposed_plan_tasks.yaml` block above** —
same output, one extra file. Order matters: the plan block must come first, the manifest
second. Use this exact schema and filename:

```yaml:interface_manifest.yaml
version: 1
kind: interface_manifest
project_id: <short-slug-for-this-app>
stack: fullstack_fastapi_react
entities:                          # the data types the app stores and returns
  - name: Item
    fields:
      - name: id
        type: string
        generated: true            # server-assigned identifier
      - name: title
        type: string
      - name: done
        type: boolean
        required: false
        default: false
api:
  base_path: /api
  request_shapes:                  # request BODIES — a projection of entity fields
    ItemCreate:
      required: [title]
      optional: [done]
  endpoints:                       # every HTTP endpoint the app exposes
    - method: GET
      path: /items
      response: list[Item]         # a list response — write list[Entity], no quotes
    - method: POST
      path: /items
      request: ItemCreate
      response: Item
      errors: [validation_error]
    - method: GET
      path: /items/{id}
      response: Item
      errors: [item_not_found]
  error_contract:
    shape: '{"error": {"code": "...", "message": "..."}}'
    codes:
      validation_error:
        http: 422
      item_not_found:
        http: 404
frontend:
  framework: react_vite
  routes:                          # one view component per route
    - path: /
      view: ItemsListView
      purpose: list items and a create form
    - path: /items/:id
      view: ItemDetailView
      purpose: one item's details
persistence: in_memory
```

Rules:
- Describe the **interface only** — entities, request shapes, endpoints, routes. Do NOT
  write endpoint logic or component code here; the scaffold wires the skeleton and the
  developer fills the bodies.
- Every `response` that names an entity, and every `request` that names a request shape,
  must be declared in `entities` / `request_shapes`.
- Keep `kind: interface_manifest` exactly, and set `stack: {{stack}}` (this build's stack).
- The example above is illustrative — replace it with THIS build's real entities,
  endpoints, and routes, drawn from the brief and PRD.
