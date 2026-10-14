"""The memory watchdog's record is named for when it began (#2229).

What bug would this catch? Every watch appending to one undated ``watchdog.jsonl``, which the
release's records name and leave behind, because engine records travel by the day they began: the
only evidence of what the memory did during a gate or a cycle comparison stays on one box.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev" / "ops"))


def test_each_watch_writes_a_record_named_for_when_it_began():
    spec = importlib.util.spec_from_file_location(
        "memory_watchdog", ROOT / "scripts/dev/ops/memory_watchdog.py"
    )
    watchdog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watchdog)
    sys.path.insert(0, str(ROOT / "scripts" / "maintainer"))
    from attach_release_records import _DAY

    assert re.fullmatch(r"\d{8}T\d{6}Z-watchdog\.jsonl", watchdog.LOG.name)
    assert _DAY.match(watchdog.LOG.name)
