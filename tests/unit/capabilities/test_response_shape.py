"""Tests for the success-body shape derivation (#1029).

The pinning budget is the subject: what the floor must catch, and — equally — what it
must decline to assert, because every over-pin spends the false-positive budget
punishing a legitimate app. Each test names the bug it catches.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.response_shape import (
    derive_response_shape,
    response_surface_instructions,
)
from squadops.capabilities.scaffold import InterfaceManifest

_BASE = """
version: 1
kind: interface_manifest
project_id: p
stack: nextjs_ts
entities:
  - name: Run
    fields:
      - {{ name: id, type: string, required: true, generated: true }}
      - {{ name: title, type: string, required: true }}
      - {{ name: distance, type: string, required: false }}
      - {{ name: participants, type: "{participants}", required: false, default: [] }}
{extra_entities}
api:
  endpoints:
    - {{ method: GET, path: /api/runs, response: "list[Run]" }}
"""

_PARTICIPANT_ENTITY = """  - name: Participant
    fields:
      - { name: name, type: string, required: true }
      - { name: joinedAt, type: string, required: false }
"""


def _manifest(participants: str = "list[string]", extra_entities: str = "") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(
        _BASE.format(participants=participants, extra_entities=extra_entities)
    )


def test_only_declared_required_fields_are_pinned():
    """#1029: the floor is required-fields-exist. Pinning optionals would fail an app
    that legitimately omits one — `distance` is declared `required: false` and an app
    that never emits it is correct, so asserting it spends the budget on a non-defect."""
    shape = derive_response_shape(_manifest(), "Run")
    assert shape.required_fields == ("id", "title")
    assert "distance" not in shape.required_fields
    assert "participants" not in shape.required_fields


def test_a_generated_field_is_pinned_present_and_nothing_more():
    """#1029: `id` is `generated: true` — it must exist, and what it equals is the
    app's business. A value pin here would fail every app with a different id scheme."""
    shape = derive_response_shape(_manifest(), "Run")
    assert "id" in shape.required_fields
    assert all(e.field != "id" for e in shape.elements)


def test_a_primitive_collection_pins_its_element_kind():
    """#1029, the half with teeth. `participants: list[string]` returning objects — or
    `list[Participant]` returning bare strings — is invisible to every status assertion,
    and it is what killed the 1.6.1 shakedown."""
    shape = derive_response_shape(_manifest(participants="list[string]"), "Run")
    assert [(e.field, e.typeof, e.required_fields) for e in shape.elements] == [
        ("participants", "string", ())
    ]


def test_an_entity_collection_pins_its_elements_required_fields():
    """#1029: the shakedown's actual declaration. `list[Participant]` means each element
    carries Participant's required fields; two dev attempts returned bare strings."""
    shape = derive_response_shape(
        _manifest(participants="list[Participant]", extra_entities=_PARTICIPANT_ENTITY), "Run"
    )
    element = shape.elements[0]
    assert element.field == "participants"
    assert element.required_fields == ("name",)  # NOT joinedAt — optional
    assert element.typeof == ""


@pytest.mark.parametrize(
    ("response", "expected_collection", "expected_entity"),
    [("Run", False, "Run"), ("list[Run]", True, "Run"), (" list[Run] ", True, "Run")],
)
def test_collection_responses_are_distinguished_from_single_ones(
    response, expected_collection, expected_entity
):
    """#1029: `list[Run]` and `Run` need different assertions — pinning required fields
    on an array object, or array-ness on a single object, fails a correct app either way."""
    shape = derive_response_shape(_manifest(), response)
    assert shape.is_collection is expected_collection
    assert shape.entity == expected_entity


@pytest.mark.parametrize("response", [None, "", "   ", "Unknown", "list[Unknown]"])
def test_an_undeclared_response_yields_no_pin(response):
    """#1029: an endpoint with no response, or one naming something the manifest never
    defines, must produce nothing. Guessing a shape is how a pin becomes a false
    positive — and `lint()` already owns rejecting an undeclared entity name."""
    assert derive_response_shape(_manifest(), response) is None


def test_a_nested_collection_is_declined_rather_than_guessed():
    """#1029: `list[list[string]]` — this pass checks one level. Unwrapping to the
    innermost kind would assert that the OUTER elements are strings, which is false for
    every correct app; declining is the only safe answer."""
    shape = derive_response_shape(_manifest(participants="list[list[string]]"), "Run")
    assert shape.elements == ()


def test_an_entity_with_nothing_checkable_is_falsey():
    """#1029: an entity of only-optional scalars yields no assertions. The shape must
    read as empty so callers emit nothing — a vacuous `expect` reads as coverage."""
    manifest = InterfaceManifest.from_yaml(
        """
version: 1
kind: interface_manifest
project_id: p
stack: nextjs_ts
entities:
  - name: Blob
    fields:
      - { name: note, type: string, required: false }
api:
  endpoints:
    - { method: GET, path: /api/blob, response: Blob }
"""
    )
    shape = derive_response_shape(manifest, "Blob")
    assert shape.required_fields == ()
    assert not shape


@pytest.mark.parametrize(
    ("declared", "expected_typeof"),
    [("list[integer]", "number"), ("list[number]", "number"), ("list[boolean]", "boolean")],
)
def test_numeric_and_boolean_collections_map_to_their_javascript_kind(declared, expected_typeof):
    """#1029: the assertion is rendered as a JS `typeof`, so `integer` must become
    `number` — emitting `typeof x === 'integer'` would fail every correct app."""
    shape = derive_response_shape(_manifest(participants=declared), "Run")
    assert shape.elements[0].typeof == expected_typeof


# --- #1042: the declared success status travels with the shape --------------------


def _manifest_with(endpoints: str, entities: str = "") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(
        f"""
version: 1
kind: interface_manifest
project_id: p
stack: nextjs_ts
entities:
  - name: Run
    fields:
      - {{ name: id, type: string, required: true, generated: true }}
      - {{ name: title, type: string, required: true }}
{entities}
api:
  endpoints:
{endpoints}
"""
    )


def test_a_declared_status_is_stated_to_the_developer():
    """#1042: on nextjs the declared status reached the implementer ONLY as a TODO
    comment inside the fill body it replaces, plus a plan sentence some author had to
    remember. V38 slot 6 shipped 200 against a declared 201."""
    manifest = _manifest_with(
        "    - { method: POST, path: /api/runs, response: Run, success_status: 201 }\n"
    )
    (line,) = response_surface_instructions(manifest)
    assert line.startswith("`POST /api/runs` returns HTTP 201 with `Run`")


def test_an_undeclared_status_states_nothing_rather_than_a_default():
    """#1042 must not settle #772 by side effect. An endpoint that declares no status
    takes the framework default, and which default is correct is that issue's open
    question — asserting one here would answer it silently and in the wrong place."""
    manifest = _manifest_with("    - { method: GET, path: /api/runs, response: Run }\n")
    (line,) = response_surface_instructions(manifest)
    assert "HTTP" not in line
    assert line.startswith("`GET /api/runs` returns `Run`")


def test_a_status_survives_an_endpoint_whose_response_cannot_be_resolved():
    """#1042: the status and the body floor are independent facts. An endpoint whose
    response names nothing the manifest defines still has a status the implementer must
    return — dropping the line because the body is underivable loses the very fact this
    issue is about."""
    manifest = _manifest_with(
        "    - { method: POST, path: /api/ping, response: Unknown, success_status: 202 }\n"
    )
    (line,) = response_surface_instructions(manifest)
    assert line == "`POST /api/ping` returns HTTP 202"


def test_an_endpoint_with_neither_a_status_nor_a_shape_contributes_no_line():
    """A line naming an endpoint and stating nothing about it is noise that reads as
    guidance — the section must stay empty rather than pad."""
    manifest = _manifest_with("    - { method: GET, path: /api/health }\n")
    assert response_surface_instructions(manifest) == []
