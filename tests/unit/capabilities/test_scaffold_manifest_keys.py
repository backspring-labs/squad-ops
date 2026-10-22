"""The manifest's declared keys are the ones its parser reads (#2205).

What bug would this catch? A key added to an element's parser and not to the table, so the
proposal rails refuse a definition the manifest would read; or a key in the table the parser
never reads, so a delta carrying it passes the rails and is dropped in the build.
"""

from __future__ import annotations

import pytest

from squadops.stacks.scaffold import (
    MANIFEST_ELEMENT_KEYS,
    InterfaceManifest,
    undefined_manifest_keys,
)

#: One value per declared key, each distinct, so a parse that reads a key shows it.
_ENDPOINT = {
    "method": "POST",
    "path": "/things",
    "summary": "make a thing",
    "request": "ThingRequest",
    "response": "Thing",
    "errors": ["validation_error"],
    "success_status": 201,
    "order": {"field": "kind", "direction": "desc"},
    "query": {"page": "integer"},
}
_ROUTE = {"path": "/things", "view": "ThingsView", "purpose": "list things", "testids": ["things"]}
_SHAPE = {"required": ["name"], "optional": ["note"], "values": {"kind": ["a", "b"]}}
_FIELD = {"name": "kind", "type": "str", "required": False, "generated": True, "default": "a"}
_CODE = {"http": 422, "message": "That thing is not valid."}


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_dict(
        {
            "version": 1,
            "kind": "interface_manifest",
            "project_id": "p",
            "stack": "fullstack_fastapi_react",
            "entities": [{"name": "Thing", "fields": [_FIELD]}],
            "api": {
                "request_shapes": {"ThingRequest": _SHAPE},
                "endpoints": [_ENDPOINT],
                "error_contract": {
                    "shape": "envelope",
                    "codes": {"validation_error": _CODE},
                },
            },
            "frontend": {"routes": [_ROUTE]},
        }
    )


def test_each_declared_key_is_one_the_parser_reads():
    m = _manifest()
    ep, route, shape = m.api.endpoints[0], m.frontend.routes[0], m.api.request_shapes[0]
    field = m.entities[0].fields[0]
    read = {
        "endpoint": {k for k in _ENDPOINT if getattr(ep, k) not in (None, "", ())},
        "client_route": {k for k in _ROUTE if getattr(route, k) not in (None, "", ())},
        "request_shape": {k for k in _SHAPE if getattr(shape, k)},
        "entity_field": {
            k for k in _FIELD if k == "name" or getattr(field, k) != {"required": True}.get(k)
        },
        "error_code": {k for k in _CODE if getattr(m.api.error_contract.codes[0], k) == _CODE[k]},
        "entity": {"name", "fields"} if m.entities[0].fields else set(),
    }
    assert read == {k: set(v) for k, v in MANIFEST_ELEMENT_KEYS.items()}


@pytest.mark.parametrize(
    ("element", "definition", "unknown"),
    [
        ("endpoint", {**_ENDPOINT, "messages": {"x": "y"}}, ["messages"]),
        ("endpoint", _ENDPOINT, []),
        (
            "entity",
            {"name": "Thing", "fields": [{**_FIELD, "label": "Kind"}]},
            ["fields[kind].label"],
        ),
        ("client_route", None, []),
    ],
    ids=["an undefined endpoint key", "every key defined", "an entity field's", "no mapping"],
)
def test_undefined_keys_are_named_as_written(element, definition, unknown):
    assert undefined_manifest_keys(element, definition) == unknown
