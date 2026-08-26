"""What a success response must contain, derived from the interface manifest (#1029).

The shells pin statuses, and since #913 the error envelope. Nothing pinned what a
**success** body contains, so response-field paths were re-invented independently on
both sides of the contract — the app deciding one shape, the suite asserting another —
and the disagreement surfaced as burned correction rounds or a dead roll.

The facts were already declared and simply unread. ``entities[].fields`` are typed and
carry ``required``; endpoints declare ``response: Run`` / ``response: list[Run]``. This
module is the one derivation those facts flow through, so the frozen shell spine, the
probes, and the agent briefs cannot disagree about the shape they are each describing —
a second implementation of this rule is a second answer.

**The pinning budget is deliberately a floor, and every exclusion below is a
false-positive source rather than an oversight** (the ruling, 2026-08-22):

- **Declared-required fields must be present.** Never an exact field set: a serializer
  that adds a field is making a legitimate choice, and failing it would spend the
  budget punishing correctness.
- **A ``list[X]`` field's elements must match the declared kind of X.** This is the
  half with teeth. The 1.6.1 shakedown declared ``participants: list[Participant]``
  (``Participant`` = ``{name: string}``) and two successive dev attempts returned bare
  strings — `art_cded59f89624` sets ``run.participants = [...current, name]`` and
  `art_e4ca71914e18` types it ``string[]`` — which no status assertion can see.
- **Optional fields are never asserted.** Absent is a valid rendering of optional.
- **Generated fields are asserted present, never to a value.** The id exists; what it
  equals is the app's business.
- **Nothing about ordering, extra fields, or nested internals below the first level.**

Empty collections satisfy everything here: an empty array has no elements to violate a
kind, which keeps a legitimately-empty list from reading as a shape defect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from squadops.capabilities.scaffold import Entity, InterfaceManifest

#: Manifest primitive tokens → the JavaScript ``typeof`` they must produce. A token
#: absent here is an entity reference (or a type this pass cannot check), and is
#: handled by presence of the entity's required fields instead.
_PRIMITIVE_TYPEOF = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "float": "number",
    "boolean": "boolean",
}


@dataclass(frozen=True)
class ElementExpectation:
    """What one element of a declared collection field must look like.

    Exactly one of ``typeof``/``required_fields`` is populated: a ``list[string]``
    constrains the element's primitive kind, a ``list[Participant]`` constrains the
    fields its elements carry. Both are subset checks.
    """

    field: str
    typeof: str = ""
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResponseShape:
    """The floor a success body must clear for one endpoint."""

    entity: str
    is_collection: bool
    #: Declared-required field names on the responding entity, in declaration order.
    required_fields: tuple[str, ...] = ()
    #: Collection-typed fields of that entity whose element kind is checkable.
    elements: tuple[ElementExpectation, ...] = ()

    def __bool__(self) -> bool:
        """Falsey when there is nothing to assert — an entity with no required fields
        and no typed collections yields no pin, and callers must emit nothing rather
        than a vacuous ``expect`` that reads as coverage."""
        return bool(self.required_fields or self.elements)


def _element_token(type_str: str) -> str:
    """The element token of a collection type, or ``""`` for a non-collection.

    Kept local rather than reusing the expander's ``_base_type_name``: that helper
    unwraps nesting to the *innermost* name, which is the right answer for naming a
    model class and the wrong one here — this pass must decline to check what it
    cannot see one level down, not silently assert the inner kind of a nested list.
    """
    t = type_str.strip()
    if t.startswith("list[") and t.endswith("]"):
        return t[len("list[") : -1].strip()
    return ""


def _required_field_names(entity: Entity) -> tuple[str, ...]:
    return tuple(f.name for f in entity.fields if f.required)


def element_kinds(shape: ResponseShape | None) -> dict[str, dict[str, Any]]:
    """The declared element kind of each checkable collection field, as plain data (#1094).

    The floor asserts this in the frozen spine; the fill gate needs the same fact to
    reject a fill that contradicts it — roll 5 of the 1.6.3 set asserted strings on a
    field the manifest declares as objects, the floor passed a correct repair, the fill
    failed it, and the loop discarded the fix. One derivation, rendered a third time.
    """
    if not shape:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for element in shape.elements:
        if element.typeof:
            out[element.field] = {"kind": "primitive", "typeof": element.typeof}
        elif element.required_fields:
            out[element.field] = {
                "kind": "object",
                "required_fields": list(element.required_fields),
            }
    return out


def derive_response_shape(
    manifest: InterfaceManifest, response: str | None
) -> ResponseShape | None:
    """The success-body floor for a ``response:`` declaration, or ``None``.

    ``None`` for an endpoint that declares no response, or one naming something the
    manifest does not define as an entity — an undeclared shape is not a shape this
    pass may invent, and asserting against a guess is how a pin becomes a false
    positive rather than a contract.
    """
    if not response:
        return None
    raw = response.strip()
    element = _element_token(raw)
    is_collection = bool(element)
    name = element or raw
    entities = {e.name: e for e in manifest.entities}
    entity = entities.get(name)
    if entity is None:
        return None

    elements: list[ElementExpectation] = []
    for f in entity.fields:
        inner = _element_token(f.type)
        if not inner:
            continue
        typeof = _PRIMITIVE_TYPEOF.get(inner, "")
        if typeof:
            elements.append(ElementExpectation(field=f.name, typeof=typeof))
        elif inner in entities:
            required = _required_field_names(entities[inner])
            if required:
                elements.append(ElementExpectation(field=f.name, required_fields=required))

    return ResponseShape(
        entity=name,
        is_collection=is_collection,
        required_fields=_required_field_names(entity),
        elements=tuple(elements),
    )


def response_surface_instructions(manifest: InterfaceManifest | None) -> list[str]:
    """Per-endpoint success-body lines for the developer's brief (#1029).

    The frozen shell spine now asserts this floor, but the developer building the
    endpoint could not see it: ``development.develop`` receives the error contract, the
    model surface, the testids and the frozen index, and nothing at all about what a
    success response must carry. So the suite derived the shape from the manifest, the
    app decided one independently, and the disagreement was discovered by burning
    correction rounds — the green roll's whole budget went on it, and the shakedown died
    on it.

    Pinning the shell without this only converts burned rounds into a deterministic red:
    the gate gets stricter while the author it judges still cannot see the target. This
    is the half that lets the app be right the first time.

    The line also carries the endpoint's declared ``success_status`` (#1042). That fact
    had exactly one surviving channel to a Next.js implementer — a sentence in plan prose
    that some author had to remember to write. The skeleton writes it as a TODO comment
    *inside the fill body*, which the fill replaces (``stack_nextjs_ts.py``), and
    ``development.develop`` binds no behavioral surface, so nothing else carried it.
    V38 slot 6 shipped 200 against a declared 201, and ``cyc_e3912098c0cf`` was rejected
    at the plan gate for the same omission on the same endpoint kind. Same class as the
    body floor above, one field over: derived and threaded beats remembered and restated.

    A status is rendered only when the manifest DECLARES one. An endpoint that leaves it
    unset takes the framework default, and which default that should be is the open
    question in #772 — stating one here would be this module taking a position on it by
    side effect.

    Data only — the prose lives in the appendix asset (CLAUDE.md #448). Empty for a
    manifest whose endpoints declare neither a resolvable response nor a status, which
    contributes no section at all rather than an empty heading.
    """
    if manifest is None:
        return []
    lines: list[str] = []
    for endpoint in manifest.api.endpoints:
        shape = derive_response_shape(manifest, endpoint.response)
        status = endpoint.success_status
        clauses = []
        if shape:
            subject = "each element of the array" if shape.is_collection else "the response body"
            if shape.required_fields:
                fields = ", ".join(f"`{name}`" for name in shape.required_fields)
                clauses.append(f"{subject} carries {fields}")
            for element in shape.elements:
                if element.typeof:
                    clauses.append(f"`{element.field}` is an array of {element.typeof}s")
                else:
                    required = ", ".join(f"`{name}`" for name in element.required_fields)
                    clauses.append(f"each `{element.field}` element carries {required}")
        if not clauses and status is None:
            continue
        # Status first: it is the fact an implementer acts on before it composes a body,
        # and the one that shipped wrong while the body was right.
        returns = f"HTTP {status}" if status is not None else ""
        if shape:
            body = f"{'a list of ' if shape.is_collection else ''}`{shape.entity}`"
            returns = f"{returns} with {body}" if returns else body
        line = f"`{endpoint.method.upper()} {endpoint.path}` returns {returns}"
        if clauses:
            line += " — " + "; ".join(clauses)
        lines.append(line)
    return lines
