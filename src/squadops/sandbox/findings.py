"""A product check's findings, read from its whole output (SIP-0112 #2609; X-3a's ``findings``).

A check that already fails at the inherited baseline can't show a regression by its result alone: a
change that adds new failures inside it still reads FAIL. So a check may declare a findings reader,
and the sandbox applies it to the run's whole stdout and stderr, before the tails are cut, so only
counts cross the boundary. The baseline and the candidate are both read here, by one reader at one
version, so the two compare like with like.

Each reader keys a finding so it survives the edits around it: ruff by rule and path, never line;
pytest by node id; vitest by its file and the test's name path. Each says when a run is readable.

The two test-id readers (pytest, vitest) also carry each failing test's exception class where the
output names it (SIP-0109 §24ci (a)), so a criterion failing on the baseline only by an import or
setup failure isn't read as discriminating. A class is extra: it changes no key and no readable
rule, so it changes no version, and a reading without one compares as before (H.5). A failing run the reader can't account for (a
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

RUFF, PYTEST, LINES, VITEST = "ruff", "pytest", "lines", "vitest"
#: The closed set a check's ``findings:`` declaration names, with each reader's version. A version
#: changes whenever a key or the readable rule does, so readings of two versions never compare.
READERS: Mapping[str, int] = {RUFF: 1, PYTEST: 1, LINES: 1, VITEST: 1}
#: A test's own failure, and one in its setup, collection or teardown: each key of a test-id
#: reader (pytest, vitest) starts with one of the two.
FAILED, ERROR = "FAILED", "ERROR"
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
#: pytest's long report: its FAILURES and ERRORS banners, each failure's head line, and the line
#: that ends its traceback, ``<path>:<line>: <ExceptionClass>`` (``--tb=auto`` and ``long``), or
#: else (``--tb=short``) its first ``E   <ExceptionClass>: …`` line.
_PYTEST_BANNER = re.compile(r"^=+ (?:FAILURES|ERRORS) =+$")
_PYTEST_HEAD = re.compile(r"^_+ (?P<head>.+?) _+$")
_PYTEST_SETUP_HEAD = re.compile(r"^ERROR at (?:setup|teardown) of (?P<head>.+)$")
_PYTEST_COLLECT_HEAD = re.compile(r"^ERROR collecting (?P<head>.+)$")
_EXCEPTION_CLASS = r"(?P<cls>[A-Z]\w*(?:\.[A-Za-z_]\w*)*)"
_PYTEST_CRASH = re.compile(rf"^\S+:\d+: {_EXCEPTION_CLASS}$")
_PYTEST_E = re.compile(rf"^E\s+{_EXCEPTION_CLASS}(?::\s|:$|$)")
#: vitest's default reporter (2.x, with no TTY), its colour codes taken out: the summary's
#: ``Tests`` and ``Errors`` lines on stdout, and on stderr the ``Failed Tests N`` and ``Failed
#: Suites N`` sections. Each failure there is a `` FAIL  <file> > <name path>`` line (a suite's
#: ``<file> [ <file> ]``), followed by its error, ``<ExceptionClass>: <message>``.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_VITEST_SECTION = re.compile(r"^⎯+ Failed (?P<kind>Tests|Suites) (?P<n>\d+) ⎯+$")
_VITEST_FAIL = re.compile(r"^ FAIL  (?P<id>\S.*?)\s*$")
_VITEST_SUITE_FILE = re.compile(r"^(?P<path>\S+) \[ (?P=path) \]$")
_VITEST_TESTS = re.compile(r"^\s*Tests {2}(?P<counts>\S.*?)\s*$")
_VITEST_ERRORS = re.compile(r"^\s*Errors {2}\d+ errors?\b")
_VITEST_TOTAL = re.compile(r"\((?P<n>\d+)\)$")
_VITEST_CLASS = re.compile(r"^(?P<cls>[A-Za-z_$][\w$]*(?:\.[\w$]+)*)(?::\s|:$|$)")
_DIGITS = re.compile(r"\d+")


class UnknownReader(ValueError):
    """A findings reader outside ``READERS``: a declaration's error, refused before anything runs."""


@dataclass(frozen=True)
class FindingsReading:
    """One run's findings as a reader read them. ``counts`` is by key, and empty when the run is
    unreadable, whose ``reason`` says why. ``collected`` is the tests a test runner's run ran, the
    floor a later reading must reach to compare (a run that ran fewer may have lost failures).
    ``classes`` is each failing key's exception class, for the keys whose class the output names
    (§24ci (a)). A key it leaves out has a class that wasn't read. ``passed`` is how many of the
    ``collected`` tests ran and passed, by a test runner's own summary (SIP-0109 §24cl item 13): a
    run whose tests were all skipped collects them and passes none, so a reading that says
    nothing failed is not yet evidence that anything ran. Like a class, it changes no key and no
    readable rule, so no version, and a reading without it is stored as before."""

    reader: str
    version: int
    readable: bool
    reason: str | None = None
    counts: Mapping[str, int] = field(default_factory=dict)
    collected: int | None = None
    classes: Mapping[str, str] = field(default_factory=dict)
    passed: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reader": self.reader,
            "version": self.version,
            "readable": self.readable,
            "reason": self.reason,
            "counts": dict(sorted(self.counts.items())),
            "collected": self.collected,
            # Only when there are any, so a reading with none is stored as it was before them.
            **({"classes": dict(sorted(self.classes.items()))} if self.classes else {}),
            **({"passed": self.passed} if self.passed is not None else {}),
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
        classes = doc.get("classes") or {}
        if not all(isinstance(v, str) and k in counts for k, v in classes.items()):
            raise ValueError("a reading's classes name an exception class for a key it counts")
        passed = doc.get("passed")
        if passed is not None and (
            isinstance(passed, bool) or not isinstance(passed, int) or passed < 0
        ):
            raise ValueError("a reading's passed tests are a count, or absent")
        return cls(
            reader=reader,
            version=int(doc["version"]),
            readable=bool(doc["readable"]),
            reason=doc.get("reason"),
            counts=dict(counts),
            collected=collected,
            classes=dict(classes),
            passed=passed,
        )


def read(reader: str, stdout: str, stderr: str, exit_code: int | None) -> FindingsReading:
    """Read a check's whole output with ``reader``. Raises :class:`UnknownReader` for one outside
    ``READERS``; any other output reads, readable or not, with the reason."""
    if reader not in READERS:
        raise UnknownReader(f"no findings reader {reader!r}; readers are {', '.join(READERS)}")
    version = READERS[reader]
    classes: dict[str, str] = {}
    if reader == RUFF:
        counts, reason, collected = _read_ruff(stdout, exit_code)
    elif reader == PYTEST:
        output = stdout + "\n" + stderr
        counts, reason, collected = _read_pytest(output, exit_code)
        if reason is None:
            classes = _pytest_classes(output, counts)
    elif reader == VITEST:
        counts, reason, collected, classes = _read_vitest(stdout, stderr, exit_code)
    else:
        counts, reason, collected = _read_lines(stdout, stderr, exit_code)
    if reason is None and len(counts) > MAX_KEYS:
        reason = f"too many findings: {len(counts)} distinct, over {MAX_KEYS}"
    if reason is not None:
        return FindingsReading(reader, version, readable=False, reason=reason)
    return FindingsReading(
        reader,
        version,
        readable=True,
        counts=dict(counts),
        collected=collected,
        classes=classes,
        passed=_passed(reader, stdout, stderr),
    )


def _passed(reader: str, stdout: str, stderr: str) -> int | None:
    """How many tests a readable test runner's run passed, from the summary its readable rule
    already read: pytest's counts line, vitest's ``Tests`` line. ``None`` for any other reader."""
    summary = None
    if reader == PYTEST:
        for line in (stdout + "\n" + stderr).splitlines():
            match = _PYTEST_SUMMARY.match(line.strip())
            if match:
                summary = match["counts"]
    elif reader == VITEST:
        for line in _ANSI.sub("", stdout).splitlines():
            tests = _VITEST_TESTS.match(line)
            if tests:
                summary = tests["counts"]
    if summary is None:
        return None
    outcomes: Counter[str] = Counter()
    for n, word in _PYTEST_COUNT.findall(summary):
        outcomes[word] += int(n)
    return outcomes["passed"]


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


def _pytest_classes(output: str, counts: Mapping[str, int]) -> dict[str, str]:
    """Each failing key's exception class, from pytest's long report (§24ci (a)).

    A section's head names its test as its node id does after the file (``Class.test[param]``),
    an error's after "ERROR at setup of" or "teardown of", a collection error's after "ERROR
    collecting". Each of these leaves its keys' classes unread, never guessed:
    - a head two keys share (one name in two files);
    - a report with no sections (``--tb=no``, ``line`` or ``native``);
    - a section that prints no class."""
    by_head: dict[tuple[str, str], list[str]] = {}
    for key in counts:
        kind, _, node = key.partition(" ")
        path, _, name = node.partition("::")
        by_head.setdefault((kind, name.replace("::", ".") if name else path), []).append(key)
    classes: dict[str, str] = {}
    head: tuple[str, str] | None = None
    found: list[str | None] = [None, None]  # the crash line's class, the first E line's

    def close() -> None:
        named = found[0] or found[1]
        keys = by_head.get(head, []) if head is not None else []
        if named is not None and len(keys) == 1:
            classes[keys[0]] = named.rsplit(".", 1)[-1]

    in_report = False
    for line in output.splitlines():
        if _PYTEST_BANNER.match(line):
            close()
            in_report, head, found = True, None, [None, None]
            continue
        if not in_report:
            continue
        if line.startswith("="):  # the report ends at the short summary or the counts
            close()
            in_report, head = False, None
            continue
        section = _PYTEST_HEAD.match(line)
        if section and section["head"].strip("_ "):  # not "_ _ _", a traceback's separator
            close()
            text = section["head"]
            errored = _PYTEST_SETUP_HEAD.match(text) or _PYTEST_COLLECT_HEAD.match(text)
            head = (ERROR, errored["head"]) if errored else (FAILED, text)
            found = [None, None]
            continue
        crash = _PYTEST_CRASH.match(line)
        if crash:
            found[0] = crash["cls"]
            continue
        raised = _PYTEST_E.match(line)
        if raised and found[1] is None:
            found[1] = raised["cls"]
    close()
    return classes


def _read_vitest(stdout: str, stderr: str, exit_code: int | None):
    """vitest's default reporter (2.x), as a product's own ``npm test`` prints it with no TTY.

    Readable at exit 0 and 1, when:
    - it prints its ``Tests`` summary;
    - it caught no unhandled error, which vitest itself says may make its results false;
    - the failures in its ``Failed Tests`` and ``Failed Suites`` sections add up to their counts,
      and the tests' to the summary's.

    A test's failure is keyed ``"FAILED <file> > <name path>"``. A suite's (its file never
    loaded, or a hook failed) is ``"ERROR <file>"`` or ``"ERROR <file> > <suite>"``. The file is
    as vitest prints it, relative to its package."""
    if exit_code not in (0, 1):
        return {}, f"vitest exited {exit_code}: the run didn't finish its tests", None, {}
    summary = None
    for line in _ANSI.sub("", stdout).splitlines():
        if _VITEST_ERRORS.match(line):
            return {}, "vitest caught unhandled errors, so its results may be false", None, {}
        tests = _VITEST_TESTS.match(line)
        if tests:
            summary = tests["counts"]
    if summary is None:
        return {}, "vitest printed no summary to read", None, {}
    total = _VITEST_TOTAL.search(summary)
    outcomes: Counter[str] = Counter()
    for n, word in _PYTEST_COUNT.findall(summary):
        outcomes[word] += int(n)
    failing = outcomes["failed"]
    counts, classes, declared = _vitest_failures(stderr)
    rows = {
        k: sum(n for key, n in counts.items() if key.startswith(f"{k} ")) for k in (FAILED, ERROR)
    }
    if not rows[FAILED] == failing == declared.get(FAILED, 0):
        return {}, f"vitest's summary has {failing} failed, and {rows[FAILED]} rows", None, {}
    if rows[ERROR] != declared.get(ERROR, 0):
        named = declared.get(ERROR, 0)
        return {}, f"vitest named {named} failed suites, and {rows[ERROR]} rows", None, {}
    if (exit_code == 1) != bool(counts):
        return {}, f"vitest exited {exit_code}, and {sum(counts.values())} failures read", None, {}
    return counts, None, int(total["n"]) if total else 0, classes


def _vitest_failures(stderr: str) -> tuple[Counter[str], dict[str, str], dict[str, int]]:
    """vitest's ``Failed Tests`` and ``Failed Suites`` sections: each failure's key, the class of
    the error printed under it, and the count each section's header declares. vitest prints one
    error once under every failure that shares it, so each line of a group takes its class."""
    counts: Counter[str] = Counter()
    classes: dict[str, str] = {}
    declared: dict[str, int] = {}
    kind: str | None = None
    group: list[str] = []
    for line in _ANSI.sub("", stderr).splitlines():
        section = _VITEST_SECTION.match(line)
        if section:
            kind, group = (FAILED if section["kind"] == "Tests" else ERROR), []
            declared[kind] = int(section["n"])
            continue
        if kind is None:
            continue
        failed = _VITEST_FAIL.match(line)
        if failed:
            suite = _VITEST_SUITE_FILE.match(failed["id"])
            key = f"{kind} {suite['path'] if suite else failed['id']}"
            counts[key] += 1
            group.append(key)
        elif group and line.strip():
            error = _VITEST_CLASS.match(line.strip())
            if error:
                for key in group:
                    classes[key] = error["cls"].rsplit(".", 1)[-1]
            group = []
    return counts, classes, declared


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
