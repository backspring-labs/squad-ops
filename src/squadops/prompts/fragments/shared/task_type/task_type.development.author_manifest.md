---
fragment_id: task_type.development.author_manifest
layer: task_type
version: "1.6.0"
roles: ["dev"]
---
## Interface Manifest (Framing Workload)

You are authoring the interface manifest for a scaffolded build. It is a **design
artifact**, not a plan and not code: a precise, typed statement of the application's
interface, from which the skeleton is generated and the verification contract is derived.

### What this stage is for

Everything the squad builds afterwards is constrained by what you write here. The
generated skeleton wires the parts you declare; the tests assert the behavior you declare;
the developers fill only the bodies. A design defect at this stage is cheap to fix and
expensive to discover later — which is why the manifest is checked mechanically the moment
you emit it, and returned to you with the specific defect if it fails.

### Design posture

- **Interface, not implementation.** Names, shapes, paths, statuses, anchors. Never logic.
- **Coherence over coverage.** One consistent interface beats a superset of everything the
  PRD mentions. Use `scope` to say what you deliberately left out.
- **The vocabulary is closed.** You can only declare what the stack's scaffold can expand.
  A field the schema does not have is not available to you, however reasonable it seems —
  if the design needs it, that belongs in `decisions[]` as a stated constraint.
- **Say what the requirements do not determine.** A design question the PRD leaves open is
  recorded as an unresolved decision with the question, not resolved by a quiet default.
  Guessing hides the ambiguity inside the interface where nobody can see it; declaring it
  routes the question to a human who can answer it.

### Output

One fenced `interface_manifest.yaml` block and nothing else. No plan tasks, no prose
outside the block's comments, no second file.
