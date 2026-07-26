"""WorkspaceRevision §4.6 semantics (SIP-0102, phase 102.1 slice a).

These tests enforce the revision contract the clean-room invariant depends on:
content-addressed determinism, honest pin verification, and a validated origin
taxonomy.
"""

import pytest

from squadops.sandbox.models import (
    RevisionOrigin,
    WorkspaceRevision,
    compute_revision_id,
)

FILES = {"backend/main.py": "print('a')\n", "frontend/index.html": "<html></html>\n"}


class TestRevisionIdDeterminism:
    def test_id_is_order_independent(self):
        """Bug caught: dict-insertion-order-dependent hashing — the same
        workspace content would pin different revisions across processes."""
        reordered = dict(reversed(list(FILES.items())))
        assert compute_revision_id(FILES) == compute_revision_id(reordered)

    @pytest.mark.parametrize(
        "mutation",
        [
            {**FILES, "backend/main.py": "print('b')\n"},  # content changed
            {**FILES, "backend/extra.py": "x = 1\n"},  # file added
            {k: v for k, v in FILES.items() if k != "frontend/index.html"},  # file removed
            {
                "backend/renamed.py": FILES["backend/main.py"],
                "frontend/index.html": FILES["frontend/index.html"],
            },  # path renamed
        ],
        ids=["content-changed", "file-added", "file-removed", "path-renamed"],
    )
    def test_id_changes_on_any_content_mutation(self, mutation):
        """Bug caught: hashing that ignores paths or file bodies — a mutated
        workspace would still 'match' its pinned revision (false clean-room)."""
        assert compute_revision_id(mutation) != compute_revision_id(FILES)

    def test_path_and_content_boundaries_do_not_collide(self):
        """Bug caught: naive concatenation hashing where {"ab": "c"} and
        {"a": "bc"} produce the same digest."""
        assert compute_revision_id({"ab": "c"}) != compute_revision_id({"a": "bc"})


class TestVerificationPinning:
    def test_matches_accepts_exact_content_and_rejects_drift(self):
        """Bug caught: a pin check that passes on mutated content — the exact
        false-verdict class the clean-room invariant exists to prevent."""
        rev = WorkspaceRevision.cut(
            cycle_id="cyc_1", origin=RevisionOrigin.SCAFFOLD_SEED, files=FILES
        )
        assert rev.matches(FILES)
        assert not rev.matches({**FILES, "backend/main.py": "print('tampered')\n"})


class TestLineageAndValidation:
    def test_cut_chains_parent_revision(self):
        """Bug caught: patch lineage dropped — evidence could not walk from a
        verdict revision back to its seed."""
        seed = WorkspaceRevision.cut(
            cycle_id="cyc_1", origin=RevisionOrigin.SCAFFOLD_SEED, files=FILES
        )
        patched = WorkspaceRevision.cut(
            cycle_id="cyc_1",
            origin=RevisionOrigin.AGENT_PATCH,
            files={**FILES, "backend/main.py": "print('b')\n"},
            parent=seed,
        )
        assert patched.parent_revision_id == seed.revision_id
        assert patched.revision_id != seed.revision_id

    def test_unknown_origin_is_rejected(self):
        """Bug caught: a typo'd origin string silently accepted, corrupting the
        §4.6 boundary taxonomy evidence relies on."""
        with pytest.raises(ValueError, match="unknown revision origin"):
            WorkspaceRevision(revision_id="r1", cycle_id="cyc_1", origin="warm_attempt")

    def test_self_parent_is_rejected(self):
        """Bug caught: a revision recorded as its own parent — an infinite
        lineage loop for any evidence walker."""
        with pytest.raises(ValueError, match="own parent"):
            WorkspaceRevision(
                revision_id="r1",
                cycle_id="cyc_1",
                origin=RevisionOrigin.AGENT_PATCH,
                parent_revision_id="r1",
            )

    def test_dict_round_trip_preserves_identity_and_validates(self):
        """Bug caught: serialization key drift between to_dict/from_dict (the
        persistence path 102.1-b will rely on), and a from_dict that skips
        origin validation."""
        rev = WorkspaceRevision.cut(
            cycle_id="cyc_1", origin=RevisionOrigin.PROMOTED_OUTPUTS, files=FILES
        )
        assert WorkspaceRevision.from_dict(rev.to_dict()) == rev
        with pytest.raises(ValueError, match="unknown revision origin"):
            WorkspaceRevision.from_dict({**rev.to_dict(), "origin": "bogus"})
