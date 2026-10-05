"""#1988: mypy as a ratchet. The check reads mypy's output; these hold the reading."""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "mypy_ratchet.py"
_spec = importlib.util.spec_from_file_location("mypy_ratchet", _SCRIPT)
ratchet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet)

_KEY = 'src/a.py\tunion-attr\tItem "None" of "X | None" has no attribute "y"'


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ('src/a.py:12: error: Item "None" of "X | None" has no attribute "y"  [union-attr]', _KEY),
        # The same error moved by an edit above it: the same key, so it is not "new".
        ('src/a.py:40: error: Item "None" of "X | None" has no attribute "y"  [union-attr]', _KEY),
        ("src/a.py:3: note: See https://mypy.readthedocs.io", None),
    ],
)
def test_an_error_is_keyed_by_file_code_and_message_never_line(line, key):
    """Bug caught: a key carrying the line number, so every edit above an error reads as a new
    error and the ratchet fails on unrelated changes; or a note counted as an error."""
    m = ratchet._ERROR.match(line)
    got = "\t".join((m["path"], m["code"], m["message"])) if m else None
    assert got == key


def test_a_new_error_and_a_fixed_one_are_both_reported():
    """Bugs caught: a second instance of a baselined error passing as already known, and a fixed
    error left in the baseline, so the baseline stops shrinking."""
    baseline = Counter({_KEY: 1, "src/b.py\targ-type\tbad": 2})
    now = Counter({_KEY: 2, "src/b.py\targ-type\tbad": 1})

    new, fixed = ratchet.compare(now, baseline)

    assert [n.split("  (")[0] for n in new] == [_KEY.replace("\t", " | ")]
    assert [f.split("  (")[0] for f in fixed] == ["src/b.py | arg-type | bad"]
    assert ratchet.compare(baseline, baseline) == ([], [])
