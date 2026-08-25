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
