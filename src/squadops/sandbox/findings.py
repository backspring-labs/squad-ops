"""A product check's findings, read from its whole output (SIP-0112 #2609; X-3a's ``findings``).

A check that already fails at the inherited baseline can't show a regression by its result alone: a
change that adds new failures inside it still reads FAIL. So a check may declare a findings reader,
and the sandbox applies it to the run's whole stdout and stderr, before the tails are cut, so only
counts cross the boundary. The baseline and the candidate are both read here, by one reader at one
version, so the two compare like with like.

Each reader keys a finding so it survives the edits around it: ruff by rule and path, never line;
pytest by node id. Each says when a run is readable. A failing run the reader can't account for (a
tool error, a collection error, a summary its findings don't add up to, more distinct findings than
the bound) is unreadable, never clean: read as clean, it would erase the baseline's failures as an
improvement.

A leaf: it imports nothing of SquadOps's, so the sandbox service and the runtime API read alike.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

RUFF, PYTEST, LINES = "ruff", "pytest", "lines"
#: The closed set a check's ``findings:`` declaration names, with each reader's version. A version
#: changes whenever a key or the readable rule does, so readings of two versions never compare.
READERS: Mapping[str, int] = {RUFF: 1, PYTEST: 1, LINES: 1}
#: More distinct findings than this is unreadable, never a partial count.
MAX_KEYS = 10_000

#: A rule code, or a syntax error, which ruff names without one (``invalid-syntax``; older ruff,
#: ``E999`` or ``SyntaxError``) and counts in its "Found" line all the same.
_RUFF_CODE = r"(?P<code>[A-Z]+[0-9]+|invalid-syntax|SyntaxError)"
_RUFF_CONCISE = re.compile(rf"^(?P<path>\S.*?):\d+:\d+: {_RUFF_CODE}[: ]")
_RUFF_FULL_HEAD = re.compile(rf"^{_RUFF_CODE}[: ]")
_RUFF_FULL_AT = re.compile(r"^\s*--> (?P<path>.+?):\d+:\d+\s*$")
_RUFF_FOUND = re.compile(r"^Found (\d+) errors?\.")
_PYTEST_ROW = re.compile(r"^(?P<kind>FAILED|ERROR) (?P<node>\S.*?)(?: - .*)?$")
_PYTEST_SUMMARY = re.compile(r"^=*\s*(?P<counts>\d+ [a-z]+(?:, \d+ [a-z]+)*) in [\d.]+s\b")
_PYTEST_COUNT = re.compile(r"(\d+) ([a-z]+)")
#: The outcomes a run's summary counts as tests it collected and ran.
_RAN = {"passed", "failed", "error", "errors", "skipped", "xfailed", "xpassed"}
_DIGITS = re.compile(r"\d+")


class UnknownReader(ValueError):
    """A findings reader outside ``READERS``: a declaration's error, refused before anything runs."""


@dataclass(frozen=True)
class FindingsReading:
    """One run's findings as a reader read them. ``counts`` is by key, and empty when the run is
    unreadable, whose ``reason`` says why. ``collected`` is the tests a pytest run ran, the floor a
    later reading must reach to compare (a run that ran fewer may have lost failures)."""

    reader: str
    version: int
    readable: bool
    reason: str | None = None
    counts: Mapping[str, int] = field(default_factory=dict)
    collected: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reader": self.reader,
            "version": self.version,
            "readable": self.readable,
            "reason": self.reason,
            "counts": dict(sorted(self.counts.items())),
            "collected": self.collected,
        }

    @classmethod
    def from_dict(cls, doc: Mapping[str, Any]) -> FindingsReading:
        reader = doc["reader"]
        if reader not in READERS:
            raise UnknownReader(f"no findings reader {reader!r}")
        counts = doc.get("counts") or {}
        if not all(isinstance(k, str) and isinstance(v, int) and v > 0 for k, v in counts.items()):
            raise ValueError("a reading's counts are positive integers by key")
        collected = doc.get("collected")
        if collected is not None and (
            isinstance(collected, bool) or not isinstance(collected, int) or collected < 0
        ):
            raise ValueError("a reading's collected tests are a count, or absent")
        return cls(
            reader=reader,
            version=int(doc["version"]),
            readable=bool(doc["readable"]),
            reason=doc.get("reason"),
            counts=dict(counts),
            collected=collected,
        )


def read(reader: str, stdout: str, stderr: str, exit_code: int | None) -> FindingsReading:
    """Read a check's whole output with ``reader``. Raises :class:`UnknownReader` for one outside
    ``READERS``; any other output reads, readable or not, with the reason."""
    if reader not in READERS:
        raise UnknownReader(f"no findings reader {reader!r}; readers are {', '.join(READERS)}")
    version = READERS[reader]
    if reader == RUFF:
        counts, reason, collected = _read_ruff(stdout, exit_code)
    elif reader == PYTEST:
        counts, reason, collected = _read_pytest(stdout + "\n" + stderr, exit_code)
    else:
        counts, reason, collected = _read_lines(stdout, stderr, exit_code)
    if reason is None and len(counts) > MAX_KEYS:
        reason = f"too many findings: {len(counts)} distinct, over {MAX_KEYS}"
    if reason is not None:
        return FindingsReading(reader, version, readable=False, reason=reason)
    return FindingsReading(reader, version, readable=True, counts=dict(counts), collected=collected)


def _read_ruff(stdout: str, exit_code: int | None):
    """``ruff check``: readable at exit 0 (nothing found) and exit 1, its findings keyed
    ``"<code> <path>"``, in either output format, adding up to its own "Found N errors." when it
    prints one. Exit 2 is a tool error."""
    if exit_code == 0:
        return {}, None, None
    if exit_code != 1:
        return {}, f"ruff exited {exit_code}: a tool error, with no findings to read", None
    counts: Counter[str] = Counter()
    found = None
    code = None
    for line in stdout.splitlines():
        concise = _RUFF_CONCISE.match(line)
        if concise:
            counts[f"{concise['code']} {concise['path']}"] += 1
            code = None
            continue
        head = _RUFF_FULL_HEAD.match(line)
        if head:
            code = head["code"]
            continue
        at = _RUFF_FULL_AT.match(line)
        if at and code is not None:
            counts[f"{code} {at['path']}"] += 1
            code = None
            continue
        summary = _RUFF_FOUND.match(line)
        if summary:
            found = int(summary.group(1))
    total = sum(counts.values())
    if not total:
        return {}, "ruff failed and no finding was read", None
    if found is not None and found != total:
        return {}, f"ruff found {found}, and {total} were read", None
    return counts, None, None


def _read_pytest(output: str, exit_code: int | None):
    """``pytest``: readable at exit 0 (all passed) and exit 1 (tests failed), never 2 (a collection
    error or an interrupt) or above, its ``FAILED`` and ``ERROR`` rows keyed ``"<kind> <node id>"``,
    adding up to its summary, which also gives the tests it ran."""
    if exit_code not in (0, 1):
        return {}, f"pytest exited {exit_code}: the run didn't finish its tests", None
    counts: Counter[str] = Counter()
    summary = None
    for line in output.splitlines():
        row = _PYTEST_ROW.match(line)
        if row:
            counts[f"{row['kind']} {row['node']}"] += 1
            continue
        match = _PYTEST_SUMMARY.match(line.strip())
        if match:
            summary = match["counts"]
    if summary is None:
        return {}, "pytest printed no summary to read", None
    outcomes: Counter[str] = Counter()
    for n, word in _PYTEST_COUNT.findall(summary):
        outcomes[word] += int(n)
    failing = outcomes["failed"] + outcomes["error"] + outcomes["errors"]
    if failing != sum(counts.values()):
        return {}, f"pytest's summary has {failing} failing, and {sum(counts.values())} rows", None
    collected = sum(n for word, n in outcomes.items() if word in _RAN)
    return counts, None, collected


def _read_lines(stdout: str, stderr: str, exit_code: int | None):
    """Any other tool: each non-empty output line is a finding, its digits replaced, so a count or a
    line number that moves doesn't make it new. Readable at exit 0 (nothing failed), and at any
    other exit with a line to read."""
    if exit_code == 0:
        return {}, None, None
    if exit_code is None:
        return {}, "the check reached no exit status", None
    counts = Counter(
        _DIGITS.sub("#", line.strip())
        for line in (stdout + "\n" + stderr).splitlines()
        if line.strip()
    )
    if not counts:
        return {}, "the check failed with no output to read", None
    return counts, None, None


def comparable(baseline: FindingsReading, candidate: FindingsReading) -> str | None:
    """Why two readings can't be compared, or ``None`` when they can: one reader at one version,
    both readable, and a pytest candidate that ran no fewer tests than its baseline."""
    if (baseline.reader, baseline.version) != (candidate.reader, candidate.version):
        return (
            f"read by {candidate.reader} v{candidate.version}, and its baseline by "
            f"{baseline.reader} v{baseline.version}"
        )
    for side, reading in (("the baseline", baseline), ("the candidate", candidate)):
        if not reading.readable:
            return f"{side} is unreadable: {reading.reason}"
    if (
        baseline.collected is not None
        and candidate.collected is not None
        and candidate.collected < baseline.collected
    ):
        return f"the candidate ran {candidate.collected} tests, fewer than its baseline's {baseline.collected}"
    return None


def grown(baseline: FindingsReading, candidate: FindingsReading) -> dict[str, tuple[int, int]]:
    """Each key whose count grew from ``baseline`` to ``candidate``, with both counts. Only for two
    readings ``comparable`` accepts."""
    return {
        key: (baseline.counts.get(key, 0), count)
        for key, count in sorted(candidate.counts.items())
        if count > baseline.counts.get(key, 0)
    }
