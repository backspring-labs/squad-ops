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
