---
template_id: request.manifest_authoring_rules_appendix
version: "2"
required_variables: []
---
## MANIFEST RULES (authoritative — a manifest that breaks one is rejected)

These are deterministic system gates, not reviewer preference. Every rule below is
checkable from the document you are writing — none depend on how the build turns out. A
manifest that breaks one is rejected before any code is written, and the rejection is
returned to you with the specific defect.

**use-the-stack-you-were-given** — The `stack:` field carries exactly the value the
request gave you, and nothing else. It is not a design choice: it names the scaffold that
will expand your manifest, and it has already been decided by the cycle. Declaring a
different one produces a working manifest for an application nobody asked for — the expander
builds that other stack's files, the plan claims them correctly, and the mismatch surfaces
hours later as an unrelated failure. If the technical design you were given describes a
different architecture than the stack you were given, **the stack wins** and the design is
the thing that was wrong.

**nothing-undeclared** — Every name the manifest uses is declared inside it. An endpoint's
`request` names a declared `request_shapes` entry or entity; an endpoint's `response` names
a declared entity (write `list[Entity]` for a collection, unquoted); every frontend route
declares a `view`. A reference to something you did not declare cannot be expanded into a
skeleton, so the manifest describes an application that cannot exist.

**declare-something-to-build** — The manifest declares at least one endpoint, and the
skeleton it implies leaves work to do. A manifest that expands with no fillable body
describes an application nobody can be asked to build: every file would be scaffold-frozen,
and the cycle would complete having produced nothing.

**paths-under-scaffold-roots** — Endpoint paths and route paths use the shapes this stack's
scaffold can place. Path parameters appear in braces (`/runs/{run_id}`), and the parameter
name is used consistently by every endpoint that addresses the same resource. The expander
is a closed surface: a path it cannot place is not a stretch goal, it is a rejection.

**declare-the-success-status** — Every POST to a collection path declares its
`success_status` explicitly (`success_status: 201` for a create that returns the new
resource). Leave it out and two components disagree about what the endpoint returns: the
verification contract asserts one status while the generated route serves another, which is
a contract no correct implementation can satisfy. State it and the disagreement cannot arise.

**warrant-a-status-that-breaks-convention** — The contract derives a success status from
the endpoint's shape: a POST to a collection path creates, so 201; a POST to a path with an
id segment acts on something that already exists, so 200. Declaring the derived value is
harmless; declaring a *different* one silently overrides the rule for every downstream
surface, and nothing records why.

So if you declare a status that differs from the shape's default, add a `decisions[]` entry
that names the endpoint path **and** states the status, warranting it from the PRD:

```yaml
decisions:
  - id: join-creates-a-participant
    choice: "POST /api/runs/{run_id}/join returns 201 — the join creates a participant record"
    warrant: "PRD §5.4 treats the participant as a created resource"
```

A decision that names the endpoint but not the status does not warrant the status — a
routing judgment about the same path is a different judgment. If you have no reason, leave
the field out and let the derived status stand: one value, and nothing to disagree with.

**declare-the-choices-a-body-carries** — When a request field's *value* selects which
behavior runs rather than carrying data — an `action` that is either `join` or `leave`, a
`status` that is either `open` or `closed` — declare its whole domain under the shape's
`values`:

```yaml
request_shapes:
  ParticipantAction:
    required: [action, name]
    values:
      action: [join, leave]
```

Without this the verification layer cannot test those behaviors at all. It has only the
field's *name*, so the only body it can build is `{"action": "sample"}` — which a correct
application rejects. Rather than manufacture that false failure it derives nothing, and the
endpoint ships with no behavioral check of its own. A design that folded a run's join and
leave into one such endpoint reached the end of a cycle with its central feature verified by
nothing deterministic, and every layer reported success.

Declare one such field per shape. Two would make the set of behaviors a cross product, and
which combinations are legal is not something the shape can state — so a shape naming two is
read as naming none.

**every-view-declares-anchors** — Every frontend route declares `testids`: the stable
`data-testid` values the view exposes, root container first. These are the only handles the
test suite is permitted to query, so a view with none is a view nothing can verify — and
the suite will otherwise invent selectors from roles and visible text that the
implementation never promised.

**error-shape-is-the-blueprints** — If you declare `error_contract.shape`, it must be
the blueprint's frozen envelope: rooted at `"error"`, i.e. `{"error": {"code", "message"}}`.
The scaffold writes this envelope into frozen code and every probe asserts it — a shape
rooted anywhere else (for example a framework default like `{"detail": "..."}`) describes a
body no response will ever carry, and a developer who trusts your document will write error
handling against a key that does not exist. Omitting the field entirely is fine; declaring
the error codes and their HTTP statuses in `error_contract.codes` is the part that is
genuinely yours to design.

**name-the-source-prd** — Set `source_prd` to the requirements document this design derives
from. A design with no stated source cannot be reviewed against its source; the reviewer is
left checking whether it is internally consistent, which is exactly what the gates already
did before a human saw it.

**record-judgments-with-warrants** — Every judgment the schema cannot express mechanically
goes in `decisions[]`: pagination, authorization boundaries, idempotency, caching,
uniqueness, ordering. Each entry needs an `id`, and then either:

- a `choice` **and** a `warrant` citing the PRD section it follows from — a choice with no
  citation is indistinguishable from an invention; or
- `unresolved: true` **and** a `question` stating exactly what the PRD does not determine.

Marking something unresolved is correct behavior, not a failure — it routes the question to
the human reviewer instead of hiding a guess inside the interface. What is not permitted is
an entry that does neither: deferring without saying what was deferred reads as diligence
while communicating nothing.
