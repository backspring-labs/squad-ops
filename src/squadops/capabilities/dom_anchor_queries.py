"""The DOM anchor contract's enforcement layer — #668, the suite half.

#659 pinned each view's ``data-testid`` anchors in the interface manifest and threaded
them to both authors: the view author attaches and preserves them, the suite author is
told to query only them. Prompts alone under-delivered on the suite side. fay-14
(``cyc_42eed09efbec``): the qa role's RTL suite made **zero** anchor queries in every
version — 16 ``getByText`` / 3 ``getByRole`` / 3 ``getByPlaceholderText`` at first, 26/14/14
at the last — while the same deploy's views carried the manifest's anchors at first fill.
The DOM channel was the sole green-killer in three windows running (fay-6, fay-12, fay-14).

Two rules, read off the suite's own bytes against the manifest's inventory, so an app
defect cannot produce either (the test-gaming footing of ``contract_assertions_match``):

* ``no_anchor_queries`` — the suite renders something and queries none of the inventory's
  anchors: it is locating elements by roles, text or structure the views never promised.
* ``view_anchors_not_queried`` — the suite imports a contract view and queries none of
  THAT view's anchors. Any of the view's anchors, not its root: measured over the vault
  before landing, seven of the nine accepted-roll suites that import a view never query
  its root container but every one queries some anchor of it — the root form would have
  cost accepted rolls an authoring retry.

Banked beside the verdict, never a rule: the anchors queried that the inventory does not
declare (``unknown_anchors`` — an assertion no application can satisfy, the qa-side
signal #1123 routes on) and the count of text/role/label/placeholder queries (texture).

Anchors arbitrate WHERE the suite looks, not the data-fetch contract; that half is the
frozen client's call surface, threaded to the author as data (``client_surface_lines``).
Pure functions over strings.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

RULE_NO_ANCHOR_QUERIES = "no_anchor_queries"
RULE_VIEW_ANCHORS_NOT_QUERIED = "view_anchors_not_queried"

#: Testing-library's ``*ByTestId('x')`` family and a raw ``[data-testid="x"]`` selector.
_ANCHOR_QUERY_RE = re.compile(
    r"""(?:getBy|queryBy|findBy|getAllBy|queryAllBy|findAllBy)TestId\(\s*['"`]([^'"`]+)['"`]"""
    r"""|data-testid=['"`]([^'"`]+)['"`]"""
)
#: The queries the anchor contract exists to replace.
_TEXT_QUERY_RE = re.compile(
    r"""\b(?:getBy|queryBy|findBy|getAllBy|queryAllBy|findAllBy)"""
    r"""(?:Text|Role|LabelText|PlaceholderText|DisplayValue|AltText|Title)\("""
)
#: ``import X from '.../views/X'`` (either stack's view module path shape). The imported
#: name is what the suite renders; the file stem is what the manifest names.
_VIEW_IMPORT_RE = re.compile(
    r"""^\s*import\s+(\w+)\s+from\s+['"`][^'"`]*/views/(\w+)(?:\.[jt]sx?)?['"`]""", re.M
)
_RENDER_RE = re.compile(r"\brender\s*\(")


@dataclass(frozen=True)
class AnchorFinding:
    """One rule the suite broke, with the detail the author is handed back."""

    rule: str
    detail: str


def anchor_queries(content: str) -> set[str]:
    """Every ``data-testid`` the suite queries, by either form."""
    return {a or b for a, b in _ANCHOR_QUERY_RE.findall(content)}


def text_query_count(content: str) -> int:
    return len(_TEXT_QUERY_RE.findall(content))


def imported_views(content: str, inventory: Mapping[str, list[str]]) -> list[str]:
    """The contract views the suite imports, in import order (by module stem or name)."""
    names: list[str] = []
    for name, stem in _VIEW_IMPORT_RE.findall(content):
        view = stem if stem in inventory else name if name in inventory else None
        if view and view not in names:
            names.append(view)
    return names


def renders(content: str) -> bool:
    return _RENDER_RE.search(content) is not None


def anchor_findings(content: str, inventory: Mapping[str, list[str]]) -> list[AnchorFinding]:
    """The rules the suite breaks against ``inventory`` (``{view: [anchors…]}``)."""
    if not inventory:
        return []
    declared = {a for anchors in inventory.values() for a in anchors}
    queried = anchor_queries(content)
    findings: list[AnchorFinding] = []
    if renders(content) and not (queried & declared):
        findings.append(
            AnchorFinding(
                RULE_NO_ANCHOR_QUERIES,
                "renders a view and queries none of the manifest's anchors "
                f"({text_query_count(content)} text/role/label queries instead); the views "
                "promise only their data-testid anchors, so every other locator asserts "
                "render details a correct implementation need not have.",
            )
        )
    for view in imported_views(content, inventory):
        anchors = inventory[view]
        if not (set(anchors) & queried):
            findings.append(
                AnchorFinding(
                    RULE_VIEW_ANCHORS_NOT_QUERIED,
                    f"imports `{view}` and queries none of its anchors — root `{anchors[0]}`; "
                    f"anchors: {', '.join(f'`{a}`' for a in anchors)}.",
                )
            )
    return findings


def anchor_observations(content: str, inventory: Mapping[str, list[str]]) -> dict[str, object]:
    """What the record banks beside the verdict, rules or not."""
    declared = {a for anchors in inventory.values() for a in anchors}
    queried = anchor_queries(content)
    return {
        "queried": sorted(queried),
        "unknown_anchors": sorted(queried - declared),
        "covered_views": imported_views(content, inventory),
        "text_queries": text_query_count(content),
    }
