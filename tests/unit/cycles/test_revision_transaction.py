"""SIP-0107 rollout step 2 — the revision transaction.

Each test names what it catches: a partially applied transaction (the #1323 class at smaller
granularity), a revision applied against a base it was not resolved on, an edit that moved
another edit's range, a grant consulted by task type rather than carried, or a candidate whose
identity is not step 1's.
"""

from __future__ import annotations

import hashlib

import pytest

from squadops.capabilities.verification_scaffold import (
    slot_begin_marker as slot_begin,
)
from squadops.capabilities.verification_scaffold import (
    slot_body_span,
)
from squadops.capabilities.verification_scaffold import (
    slot_end_marker as slot_end,
)
from squadops.cycles.patch_verification import candidate_revision_id
from squadops.cycles.revision_transaction import (
    RefusalReason,
    Revision,
    RevisionOperation,
    RevisionTransaction,
    base_revision_id,
    resolve_and_apply,
)
from squadops.cycles.write_authorization import WriteGrant
from squadops.sandbox.models import compute_revision_id

pytestmark = [pytest.mark.domain_orchestration]

_SHELL = "__tests__/scaffold/runs.scaffold.test.ts"
_OTHER = "__tests__/scaffold/join.scaffold.test.ts"


def _shell(*slots: tuple[str, str]) -> str:
    lines = ["import { it } from 'vitest'", "it('probe', () => {"]
    for slot_id, body in slots:
        lines += [slot_begin(slot_id), *([body] if body else []), slot_end(slot_id)]
    lines += ["})", ""]
    return "\n".join(lines)


_BASE = {
    _SHELL: _shell(("slot-a", "    // fill me"), ("slot-b", "")),
    _OTHER: _shell(("slot-c", "    // fill me too")),
    "lib/store.ts": "export const x = 1\n",
}


def _resolve(_path: str, content: str, region_id: str):
    return slot_body_span(content, region_id)


def _txn(*revisions: Revision, writable=(_SHELL, _OTHER), base=_BASE) -> RevisionTransaction:
    return RevisionTransaction(
        base_revision_id=base_revision_id(base),
        grant=WriteGrant(producer="qa.test", stage="qa_fill", writable=frozenset(writable)),
        task_id="task-run_1-m005-qa.test",
        revisions=revisions,
    )


def _replace(path: str, region: str, body: str) -> Revision:
    return Revision(
        artifact_path=path,
        region_id=region,
        operation=RevisionOperation.REPLACE_REGION,
        replacement=body,
    )


class TestAccepted:
    def test_edits_in_one_artifact_do_not_move_each_others_ranges(self):
        """Bug caught: applying in ascending order, so the first replacement (longer than what
        it replaced) shifts the second's offsets and it lands inside the wrong lines."""
        outcome = resolve_and_apply(
            _BASE,
            _txn(
                _replace(_SHELL, "slot-a", "    expect(1).toBe(1)\n    expect(2).toBe(2)\n"),
                _replace(_SHELL, "slot-b", "    expect(3).toBe(3)\n"),
            ),
            _resolve,
        )
        assert outcome.accepted
        assert outcome.candidate_files[_SHELL] == _shell(
            ("slot-a", "    expect(1).toBe(1)\n    expect(2).toBe(2)"),
            ("slot-b", "    expect(3).toBe(3)"),
        )
        # Untouched artifacts are the base, byte for byte.
        assert outcome.candidate_files["lib/store.ts"] == _BASE["lib/store.ts"]
        assert outcome.changed_files().keys() == {_SHELL}

    def test_each_edit_records_the_span_it_replaced_and_the_base_it_was_resolved_on(self):
        outcome = resolve_and_apply(_BASE, _txn(_replace(_OTHER, "slot-c", "    ok()\n")), _resolve)
        (edit,) = outcome.edits
        base = _BASE[_OTHER]
        assert edit.base_artifact_sha256 == hashlib.sha256(base.encode()).hexdigest()
        assert base[edit.start : edit.end] == "    // fill me too\n"
        assert edit.pre_sha256 == hashlib.sha256(b"    // fill me too\n").hexdigest()
        assert (edit.producer, edit.task_id) == ("qa.test", "task-run_1-m005-qa.test")

    def test_the_candidate_is_named_with_step_ones_identity(self):
        """Bug caught: a second identity function for transactions — the candidate would read
        differently in the verdict than in the store."""
        outcome = resolve_and_apply(_BASE, _txn(_replace(_OTHER, "slot-c", "    ok()\n")), _resolve)
        changed = [{"name": _OTHER, "content": outcome.candidate_files[_OTHER]}]
        assert outcome.candidate_revision_id == candidate_revision_id(_BASE, changed)
        assert outcome.candidate_revision_id == compute_revision_id(outcome.candidate_files)


class TestRefused:
    def test_one_bad_revision_refuses_the_whole_transaction(self):
        """SIP-0107 §14. Bug caught: keeping the two good revisions — a collection of revisions
        is one proposed repair, and applying part of it is a change nobody proposed."""
        outcome = resolve_and_apply(
            _BASE,
            _txn(
                _replace(_SHELL, "slot-a", "    a()\n"),
                _replace("lib/store.ts", "slot-x", "export const x = 2\n"),
                _replace(_OTHER, "slot-c", "    c()\n"),
            ),
            _resolve,
        )
        assert not outcome.accepted
        assert (outcome.edits, dict(outcome.candidate_files), outcome.candidate_revision_id) == (
            (),
            {},
            None,
        )
        assert [(r.revision_index, r.reason) for r in outcome.refusals] == [
            (1, RefusalReason.OUT_OF_GRANT)
        ]

    def test_a_base_that_moved_is_stale_not_rebased(self):
        """SIP-0107 §12. Bug caught: resolving against whatever tree arrived, so a revision
        planned on one shell lands on another version of it."""
        moved = {**_BASE, _SHELL: _BASE[_SHELL].replace("probe", "renamed")}
        outcome = resolve_and_apply(moved, _txn(_replace(_SHELL, "slot-a", "    a()\n")), _resolve)
        assert [r.reason for r in outcome.refusals] == [RefusalReason.STALE_BASE]

    @pytest.mark.parametrize(
        ("revision", "reason"),
        [
            (
                _replace("__tests__/scaffold/gone.test.ts", "slot-a", "x\n"),
                RefusalReason.UNKNOWN_ARTIFACT,
            ),
            (_replace(_SHELL, "slot-nope", "x\n"), RefusalReason.UNRESOLVED_REGION),
            (
                Revision(
                    artifact_path=_SHELL,
                    region_id="slot-a",
                    operation="insert",  # type: ignore[arg-type]
                    replacement="x\n",
                ),
                RefusalReason.UNSUPPORTED_OPERATION,
            ),
        ],
    )
    def test_each_unresolvable_revision_names_its_reason(self, revision, reason):
        writable = (_SHELL, _OTHER, "__tests__/scaffold/gone.test.ts")
        outcome = resolve_and_apply(_BASE, _txn(revision, writable=writable), _resolve)
        assert [(r.revision_index, r.reason) for r in outcome.refusals] == [(0, reason)]

    def test_two_revisions_of_one_region_overlap(self):
        """Bug caught: two replacements of one slot applied one after the other — the result
        depends on their order, which §13 forbids."""
        outcome = resolve_and_apply(
            _BASE,
            _txn(
                _replace(_SHELL, "slot-b", "    one()\n"), _replace(_SHELL, "slot-b", "    two()\n")
            ),
            _resolve,
        )
        assert [r.reason for r in outcome.refusals] == [RefusalReason.OVERLAPPING_RANGES]


class TestTheSlotRegion:
    def test_an_empty_body_is_an_empty_span_between_the_markers(self):
        text = _BASE[_SHELL]
        start, end = slot_body_span(text, "slot-b")
        assert start == end
        assert text[:start].endswith(slot_begin("slot-b") + "\n")
        assert text[end:].startswith(slot_end("slot-b"))

    def test_an_undeclared_slot_has_no_span(self):
        assert slot_body_span(_BASE[_SHELL], "slot-z") is None


# --- SIP-0107 step 4: exact anchored targets ------------------------------------------------

#: The manifest #451 corrupted: a placeholder hash of '0' among a version, a timestamp and a
#: sibling hash that all contain zeros. An unanchored replace of '0' rewrote every one of them.
_MANIFEST = "prompts/manifest.yaml"
_MANIFEST_TEXT = (
    "version: 0.9.99\n"
    "updated_at: '2026-07-15T00:00:00.000000Z'\n"
    "fragments:\n"
    "- fragment_id: task_type.good\n"
    "  sha256: 0a5f00c1\n"
    "- fragment_id: task_type.new\n"
    "  sha256: '0'\n"
    "manifest_hash: placeholder\n"
)
_ANCHOR_BASE = {
    _MANIFEST: _MANIFEST_TEXT,
    "backend/routes.py": "def a():\n    return 1\n\ndef b():\n    return 1\n",
    _SHELL: _shell(("slot-a", "    expect(x).toBe(1)"), ("slot-b", "    expect(x).toBe(1)")),
    "lib/store.ts": "export const x = 1\n",
}


def _anchored(path: str, anchor: str, replacement: str, region: str = "") -> Revision:
    return Revision(
        artifact_path=path,
        operation=RevisionOperation.REPLACE_ANCHOR,
        anchor=anchor,
        replacement=replacement,
        region_id=region,
    )


def _anchor_txn(*revisions: Revision) -> RevisionTransaction:
    return _txn(*revisions, writable=(_MANIFEST, "backend/routes.py", _SHELL), base=_ANCHOR_BASE)


class TestExactAnchoredTargets:
    def test_the_451_placeholder_anchored_to_its_line_changes_that_line_and_nothing_else(self):
        """#451, applied. Bug caught: any byte outside the anchored line changing — the version,
        the timestamp, the sibling hash — when only the placeholder was meant."""
        outcome = resolve_and_apply(
            _ANCHOR_BASE,
            _anchor_txn(_anchored(_MANIFEST, "  sha256: '0'\n", "  sha256: 7e3b9c\n")),
            _resolve,
        )

        assert outcome.accepted
        assert outcome.changed_files()[_MANIFEST] == _MANIFEST_TEXT.replace(
            "  sha256: '0'\n", "  sha256: 7e3b9c\n"
        )
        (edit,) = outcome.edits
        assert _MANIFEST_TEXT[edit.start : edit.end] == "  sha256: '0'\n"

    def test_the_451_bare_zero_is_ambiguous_and_nothing_is_applied(self):
        """§39.5: a multi-match anchor fails rather than choosing. Bug caught: the #451 replace —
        the first match, or every match, rewritten."""
        outcome = resolve_and_apply(
            _ANCHOR_BASE, _anchor_txn(_anchored(_MANIFEST, "0", "7e3b9c")), _resolve
        )

        assert not outcome.accepted
        assert outcome.candidate_files == {}
        (refusal,) = outcome.refusals
        assert refusal.reason == RefusalReason.ANCHOR_AMBIGUOUS
        assert f"occurs {_MANIFEST_TEXT.count('0')} times" in refusal.detail

    @pytest.mark.parametrize(
        ("anchor", "reason"),
        [
            ("    return 1\n", RefusalReason.ANCHOR_AMBIGUOUS),
            ("    return  1\n", RefusalReason.ANCHOR_NOT_FOUND),
            ("    RETURN 1\n", RefusalReason.ANCHOR_NOT_FOUND),
            ("", RefusalReason.EMPTY_ANCHOR),
        ],
        ids=["two matches", "whitespace differs", "case differs", "empty"],
    )
    def test_an_anchor_that_does_not_occur_exactly_once_is_refused(self, anchor, reason):
        """Bug caught: a normalized, case-folded or first-of-many match written — the fuzzy
        application §9.2 prohibits."""
        outcome = resolve_and_apply(
            _ANCHOR_BASE, _anchor_txn(_anchored("backend/routes.py", anchor, "")), _resolve
        )
        assert [r.reason for r in outcome.refusals] == [reason]

    def test_overlapping_occurrences_count_as_two(self):
        """Bug caught: a non-overlapping count reading ``aa`` in ``aaa`` as one match."""
        base = {"notes.txt": "aaa\n"}
        txn = RevisionTransaction(
            base_revision_id=base_revision_id(base),
            grant=WriteGrant(producer="dev", stage="dev_fill", writable=frozenset({"notes.txt"})),
            task_id="t",
            revisions=(_anchored("notes.txt", "aa", "b"),),
        )
        (refusal,) = resolve_and_apply(base, txn, _resolve).refusals
        assert refusal.reason == RefusalReason.ANCHOR_AMBIGUOUS

    def test_a_named_region_bounds_the_search(self):
        """§9.2: the framework searches only within the authorized region. The same assertion
        sits in two slots: named, one slot's copy resolves; unnamed, the file holds two."""
        shell = _ANCHOR_BASE[_SHELL]
        inside = resolve_and_apply(
            _ANCHOR_BASE,
            _anchor_txn(
                _anchored(_SHELL, "    expect(x).toBe(1)\n", "    expect(x).toBe(2)\n", "slot-b")
            ),
            _resolve,
        )
        unnamed = resolve_and_apply(
            _ANCHOR_BASE,
            _anchor_txn(_anchored(_SHELL, "    expect(x).toBe(1)\n", "    expect(x).toBe(2)\n")),
            _resolve,
        )

        (edit,) = inside.edits
        start, end = slot_body_span(shell, "slot-b")
        assert start <= edit.start < edit.end <= end
        assert [r.reason for r in unnamed.refusals] == [RefusalReason.ANCHOR_AMBIGUOUS]

    def test_an_anchor_outside_the_grant_or_overlapping_another_refuses_the_transaction(self):
        """§13/§14. Bug caught: one good anchored edit applied while its sibling was refused."""
        good = _anchored("backend/routes.py", "def a():\n", "def a_renamed():\n")
        overlapping = _anchored("backend/routes.py", "def a():\n    return 1\n", "")
        outside = _anchored("lib/store.ts", "export const x = 1\n", "export const x = 2\n")

        for siblings, reasons in (
            ((good, overlapping), [RefusalReason.OVERLAPPING_RANGES]),
            ((good, outside), [RefusalReason.OUT_OF_GRANT]),
        ):
            outcome = resolve_and_apply(_ANCHOR_BASE, _anchor_txn(*siblings), _resolve)
            assert not outcome.accepted
            assert outcome.candidate_files == {}
            assert [r.reason for r in outcome.refusals] == reasons
