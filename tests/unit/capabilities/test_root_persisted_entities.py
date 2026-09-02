"""#1087 — which declared entities a correct application stores as rows of their own.

The frozen store used to export a table per declared entity. On ``group_run`` that is
three tables for one stored thing: ``Participant`` exists only as ``Run.participants``'
element shape and ``RunSummary`` only as ``GET /runs``' projection, and a qa fill asserting
``all(TABLES.Participant)`` rejected two working applications in the 1.6.3 set.

Bug classes guarded: an embedded shape or projection getting a table; a genuinely stored
entity losing its table (the widening fallbacks); the derivation reordering the store.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.scaffold import InterfaceManifest, root_persisted_entities

pytestmark = [pytest.mark.domain_capabilities]

_BASE = """
version: 1
kind: interface_manifest
project_id: p
stack: nextjs_ts
entities:
  - name: Participant
    fields:
      - {{ name: name, type: string, required: true }}
  - name: Run
    fields:
      - {{ name: id, type: string, required: true, generated: true }}
      - {{ name: participants, type: "list[Participant]", required: true, default: [] }}
  - name: RunSummary
    fields:
      - {{ name: id, type: string, required: true }}
api:
  endpoints:
{endpoints}
"""


def _manifest(endpoints: str) -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_BASE.format(endpoints=endpoints))


@pytest.mark.parametrize(
    ("endpoints", "expected"),
    [
        # group_run's shape: Run is created and read by id; the others are shape/projection.
        (
            """    - { method: POST, path: /api/runs, response: Run }
    - { method: GET, path: /api/runs, response: "list[RunSummary]" }
    - { method: GET, path: "/api/runs/{run_id}", response: Run }
""",
            ("Run",),
        ),
        # Only collections are ever returned: keep every entity some endpoint returns,
        # never narrow on a guess — RunSummary here might genuinely be stored.
        (
            """    - { method: GET, path: /api/runs, response: "list[RunSummary]" }
""",
            ("RunSummary",),
        ),
        # No typed responses at all: the manifest says nothing, so every entity keeps
        # its table — the pre-#1087 behaviour, and the only safe one without evidence.
        (
            """    - { method: GET, path: /api/health }
""",
            ("Participant", "Run", "RunSummary"),
        ),
    ],
)
def test_root_tables_are_the_single_object_responses_with_widening_fallbacks(endpoints, expected):
    assert root_persisted_entities(_manifest(endpoints)) == expected


def test_declaration_order_is_kept_so_the_first_table_is_stable():
    """The store's first table is what the harness demonstrates; a derivation that sorted
    would reorder the frozen harness under an unrelated manifest edit."""
    m = _manifest(
        """    - { method: POST, path: /api/summaries, response: RunSummary }
    - { method: POST, path: /api/runs, response: Run }
"""
    )
    assert root_persisted_entities(m) == ("Run", "RunSummary")


# --------------------------------------------------------------------------- #
# #1112 — a single-object projection is the shape of a root, not a second root
# --------------------------------------------------------------------------- #

_DETAIL = """
version: 1
kind: interface_manifest
project_id: p
stack: fullstack_fastapi_react
entities:
  - name: Run
    fields:
      - {{ name: id, type: string, required: true, generated: true }}
      - {{ name: title, type: string, required: true }}
      - {{ name: participant_count, type: integer, required: true }}
  - name: RunDetail
    fields:
      - {{ name: id, type: string, required: true }}
      - {{ name: title, type: string, required: true }}
      - {{ name: participant_count, type: integer, required: true }}
      - {{ name: participants, type: "list[Participant]", required: true, default: [] }}
  - name: Participant
    fields:
      - {{ name: name, type: string, required: true }}
{extra_entities}api:
  endpoints:
{endpoints}
"""


def _detail_manifest(endpoints: str, extra_entities: str = "") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(
        _DETAIL.format(endpoints=endpoints, extra_entities=extra_entities)
    )


def test_the_widest_shape_under_one_resource_is_the_row_and_the_narrower_is_its_projection():
    """Bug caught (#1112, 1.6.6 roll 4): the create returned `Run` (with a count) and the
    read-by-id returned `RunDetail` (with the participants); both are single-object
    responses, so both got a table, and the fill kept `run_store`, `run_detail_store` and
    a `participant_store` in sync by hand. `Run`'s field names are a proper subset of
    `RunDetail`'s under the same `/runs` resource: it is the detail seen without its
    participants, and the detail is the row."""
    m = _detail_manifest(
        """    - { method: POST, path: /runs, response: Run }
    - { method: GET, path: /runs, response: "list[Run]" }
    - { method: GET, path: "/runs/{run_id}", response: RunDetail }
    - { method: POST, path: "/runs/{run_id}/join", response: RunDetail }
"""
    )
    assert root_persisted_entities(m) == ("RunDetail",)


def test_an_action_response_with_a_field_no_sibling_has_keeps_its_table():
    """The rule narrows only on proof. 1.6.6 roll 3 declared `JoinResult {id, participants}`
    (a subset of `Run` — projection) and `LeaveResult {id, participants, removed}`;
    `removed` is nobody else's field, so `LeaveResult` is not provably a shape of `Run`
    and keeps a table — the widening direction, deliberately (#1112's remaining edge)."""
    m = _detail_manifest(
        """    - { method: POST, path: /runs, response: RunDetail }
    - { method: POST, path: "/runs/{run_id}/join", response: JoinResult }
    - { method: POST, path: "/runs/{run_id}/leave", response: LeaveResult }
""",
        extra_entities="""  - name: JoinResult
    fields:
      - { name: id, type: string, required: true }
      - { name: participants, type: "list[Participant]", required: true }
  - name: LeaveResult
    fields:
      - { name: id, type: string, required: true }
      - { name: removed, type: boolean, required: true }
""",
    )
    assert root_persisted_entities(m) == ("RunDetail", "LeaveResult")


def test_containment_is_read_per_resource_so_two_roots_stay_two():
    """A genuine second root whose fields happen to be a subset of another's must not be
    demoted: `Participant {name}` created and read under `/participants` is a row of its
    own, whatever `/runs` returns."""
    m = _detail_manifest(
        """    - { method: POST, path: /runs, response: RunDetail }
    - { method: GET, path: "/runs/{run_id}", response: RunDetail }
    - { method: POST, path: /participants, response: Participant }
    - { method: GET, path: "/participants/{name}", response: Participant }
"""
    )
    assert root_persisted_entities(m) == ("RunDetail", "Participant")


@pytest.mark.parametrize(
    ("path", "prefix"),
    [
        ("/runs/{run_id}/join", "/runs"),
        ("/api/runs/{run_id}", "/api/runs"),
        ("/api/runs", "/api/runs"),
        ("/{id}", "/"),
    ],
)
def test_the_resource_prefix_is_the_path_before_its_first_parameter(path, prefix):
    from squadops.capabilities.scaffold import _resource_prefix

    assert _resource_prefix(path) == prefix


def test_equal_field_sets_under_one_resource_are_both_kept():
    """Neither is a PROPER subset of the other, so neither is provably the projection —
    the rule refuses to pick, and both keep a table."""
    m = _detail_manifest(
        """    - { method: POST, path: /runs, response: Run }
    - { method: GET, path: "/runs/{run_id}", response: Twin }
""",
        extra_entities="""  - name: Twin
    fields:
      - { name: id, type: string, required: true }
      - { name: title, type: string, required: true }
      - { name: participant_count, type: integer, required: true }
""",
    )
    assert root_persisted_entities(m) == ("Run", "Twin")


def test_shape_entities_is_the_complement_in_declaration_order():
    from squadops.capabilities.scaffold import shape_entities

    m = _detail_manifest(
        """    - { method: POST, path: /runs, response: Run }
    - { method: GET, path: "/runs/{run_id}", response: RunDetail }
"""
    )
    assert shape_entities(m) == ("Run", "Participant")
