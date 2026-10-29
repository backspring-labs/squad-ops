"""What a correction repair's prompt shows of the tree it repairs (#2810).

A repair carries the whole accepted tree its failed task was evaluated on
(``acceptance_workspace_files``, forwarded for its own evaluation, #1229) and the failed task's own
files (``failed_task_artifacts``, #1264). Its prompt shows a part of that tree, the base the
repair's edits resolve against (:func:`repair_base_files`):

- **the current files** (#1576): each named file that already exists in the base, verbatim, the
  scaffold's shells aside (:func:`current_files`);
- **the edit form** (SIP-0107 §9.1): the same files, each with the entities its resolver can
  address (:func:`edit_form`);
- **a qa repair's failing-case frames** (1.8.2 item 6): the lines around each failing case's line,
  cut from the base (:func:`failing_case_frames`).

The repair handlers render each through these functions, on the agents. The composer
(``squadops.capabilities.prompt_budget``, SIP-0110 Appendix A §3.6) calls
:func:`repair_prompt_contents` alone, in the runtime. Counted apart, the composer measured the whole
tree: on a repository-backed product larger than about half its model's window, the budget left for
memory's sections read 0, and every repair was held on its binding (the 2.5 main demonstration's
round 2).

**What runs where.** Listing a file's entities takes its resolver: the stdlib ``ast`` for Python,
in process; tree-sitter in a worker process for JavaScript and TypeScript, which only the agents'
images carry. :func:`edit_form` lists every file's, on the agent. The composer never calls it: it
calls :func:`repair_prompt_contents`, which reads no file and starts no process, and counts the
edit form by :func:`edit_form_bound`. That lists a Python file's entities through ``ast`` and
counts a file no resolver reads by its path, both exactly, and bounds a JavaScript or TypeScript
file's from its text, with no parser. So it runs in the runtime, which carries no JavaScript
parser, on its event loop.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from squadops.capabilities.anchored_edits import (
    EDIT_FORM_ENTITIES,
    EDIT_FORM_FILE,
    EDIT_FORM_MORE,
    EDIT_FORM_SEPARATOR,
    MAX_LISTED_ENTITIES,
    editable_file_lines,
    verbatim_block,
)
from squadops.capabilities.context_assembly import REPAIR_FAILED_ARTIFACTS_KEY, scaffold_shell_paths
from squadops.cycles.failure_evidence import failing_cases_from_evidence
from squadops.cycles.structural_jsx import ECMASCRIPT_SUFFIXES, SELECTORS_PER_STATEMENT_MAX
from squadops.cycles.structural_resolution import (
    PYTHON_SUFFIXES,
    SELECTOR_KIND_MAX,
    SELECTOR_NAMES_MAX,
    SELECTOR_SUFFIX_MAX,
    reads_structure,
)
from squadops.cycles.write_authorization import normalize_ws_path

#: The inputs a repair's prompt shows a part of, through :func:`repair_prompt_contents`: the tree
#: it repairs and the failed task's own files over it. Neither is shown otherwise.
REPAIR_BASE_INPUTS = frozenset({"acceptance_workspace_files", REPAIR_FAILED_ARTIFACTS_KEY})

#: Lines of the suite shown on each side of a failing line (1.8.2 item 6): enough to take in
#: the assertion, the setup it rests on and the lines after it in the same case.
FAILING_LINE_CONTEXT = 6


def repair_prompt_contents(inputs: Mapping[str, Any]) -> dict[str, str]:
    """What the composer counts of a repair's prompt, by the template variable that shows it, each
    ``""`` when the prompt shows none: the current files and the failing-case frames as the prompt
    shows them, and, for the edit form's file list, as many characters as :func:`edit_form_bound`
    says it can take, since listing a JavaScript file's entities takes a parser the runtime doesn't
    carry. Reads no file, starts no process, and parses only Python, with ``ast`` in process.

    Two parts can be upper bounds: a JavaScript or TypeScript file's line in the edit form, and the
    frames, which are a qa repair's alone, so a dev or builder repair's count is over by them."""
    return {
        "current_files": current_files(inputs),
        "editable_files": " " * edit_form_bound(inputs),
        "case_frames": failing_case_frames(inputs),
    }


def repair_base_files(inputs: Mapping[str, Any]) -> dict[str, str]:
    """The tree the repair patches: the workspace the verifier materialises, with the failed
    task's own files over it (#1264), the same tree the typed checks evaluate on."""
    workspace = {
        str(k): str(v) for k, v in (inputs.get("acceptance_workspace_files") or {}).items()
    }
    for art in inputs.get(REPAIR_FAILED_ARTIFACTS_KEY) or ():
        if isinstance(art, dict) and isinstance(art.get("name"), str):
            workspace[art["name"]] = str(art.get("content") or "")
    return workspace


def anchorable_files(inputs: Mapping[str, Any]) -> list[str]:
    """The named files a repair may revise by anchored edit: those it may emit that already
    exist in its base, minus the scaffold's shells. A qa repair in fill mode revises its
    shells by slot (§9.3) and never anchors them; a free-authored file it also owns — a
    suite beside the shells — is anchorable like any other file (#1583: with the shells'
    rule applied to every file, deploy D's Next.js qa repair had no scoped path to the one
    assertion it had to fix and re-emitted the whole suite, unread as a whole-file response
    because nothing had been offered)."""

    base = repair_base_files(inputs)
    shells = scaffold_shell_paths(inputs)
    named = [normalize_ws_path(str(e)) for e in (inputs.get("expected_artifacts") or [])]
    return sorted({n for n in named if n and n in base and n not in shells})


def current_files(inputs: Mapping[str, Any]) -> str:
    """The current-files section's body (SIP-0107 §9.2, §46m; #1576): each file the repair may
    revise, verbatim, from the base its edits resolve against, or ``""`` when it may revise none."""
    base = repair_base_files(inputs)
    return "\n\n".join(verbatim_block(path, base[path]) for path in anchorable_files(inputs))


def edit_form(inputs: Mapping[str, Any]) -> tuple[list[str], dict[str, int]]:
    """The edit form's file list and what it offered (SIP-0107 §9.1, §9.2): each file the repair
    may revise with the entities its resolver can address, read from the same base, and how many
    were listed for each. Nothing when it may revise none.

    It parses each file, JavaScript and TypeScript through tree-sitter in a worker process, so the
    handler calls it on the agent, and the composer never does: it counts :func:`edit_form_bound`
    instead."""
    files = anchorable_files(inputs)
    if not files:
        return [], {}
    return editable_file_lines(files, repair_base_files(inputs))


def edit_form_bound(inputs: Mapping[str, Any]) -> int:
    """At least as many characters as the composer counts :func:`edit_form`'s file list at, its
    JSON escapes included (``prompt_budget`` counts a structure as its JSON), with no file parsed
    out of process: each file's line by :func:`_file_line_bound`, and the lines between them."""
    base = repair_base_files(inputs)
    files = anchorable_files(inputs)
    between = _escaped("\n" * max(0, len(files) - 1))
    return between + sum(_file_line_bound(path, base[path]) for path in files)


def _file_line_bound(path: str, content: str) -> int:
    """At least the escaped length of the edit form's line for ``path``.

    - **Exactly, for a file no resolver reads and for Python.** The first is listed by its path
      alone. Python's resolver is the stdlib ``ast``, in process, with no worker and no I/O.
    - **For JavaScript and TypeScript, by the least of three bounds,** since their resolver is
      tree-sitter in a worker process, which the runtime doesn't carry. The line is its path's
      framing, at most ``MAX_LISTED_ENTITIES`` selectors between backticks, and the count of those
      left out (``anchored_edits.EDIT_FORM_*``). A selector is a kind, its names and a suffix
      (``structural_resolution.SELECTOR_*``), so only the names vary, and their total is at most:
      1. each name's logical line (:func:`_longest_name`), as many as a selector carries. A name
         never spans one: an identifier never does, and an import's source spans physical lines
         only through a backslash continuation, which it joins;
      2. ``SELECTORS_PER_STATEMENT_MAX`` times the file's text, since each statement's names lie
         inside it;
      3. the longest identifier-like run in the file for each selector
         (:func:`_longest_identifier`), every name but an import's source being an identifier,
         and the logical line for each import the file can have.
    - **For any other resolver,** by the first bound alone.
    """
    if path.endswith(PYTHON_SUFFIXES) or not reads_structure(path):
        [line], _offered = editable_file_lines([path], {path: content})
        return _escaped(line)
    longest = _longest_name(content)
    names = MAX_LISTED_ENTITIES * (SELECTOR_NAMES_MAX * longest + SELECTOR_NAMES_MAX - 1)
    if path.endswith(ECMASCRIPT_SUFFIXES):
        imports = min(MAX_LISTED_ENTITIES, content.count("import"))
        names = min(
            names,
            SELECTORS_PER_STATEMENT_MAX * _escaped(content),
            MAX_LISTED_ENTITIES * _longest_identifier(content) + imports * longest,
        )
    framing = MAX_LISTED_ENTITIES * (SELECTOR_KIND_MAX + SELECTOR_SUFFIX_MAX + len("``"))
    separators = (MAX_LISTED_ENTITIES - 1) * len(EDIT_FORM_SEPARATOR)
    # The count left out is under the selectors a file can carry: three a statement and
    # ``imports``, with at most one statement starting on each line.
    more = _escaped(EDIT_FORM_MORE.format(count=3 * (len(content) + 1) + 1))
    head = _escaped(EDIT_FORM_FILE.format(path=path) + EDIT_FORM_ENTITIES)
    return head + framing + names + separators + more


def _longest_name(content: str) -> int:
    """The most characters a name read from ``content`` can take, escaped as JSON: its longest
    logical line, the lines a trailing backslash continues joined. Split on ``\\n`` alone: every
    other line break either resolver reads (``\\r``, U+2028, U+2029) only lengthens a line here."""
    longest = current = 0
    for line in content.split("\n"):
        current += _escaped(line + "\n")
        if not line.rstrip("\r").endswith("\\"):
            longest, current = max(longest, current), 0
    return max(longest, current)


#: A run of the characters a JavaScript or TypeScript identifier is written with, escapes and the
#: joiners included, and more: any identifier lies inside one such run.
_IDENTIFIER_RUN = re.compile(r"[\w$\\{}\u200c\u200d]+")


def _longest_identifier(content: str) -> int:
    """The most characters an identifier in ``content`` can take, escaped as JSON."""
    return max((_escaped(run) for run in _IDENTIFIER_RUN.findall(content)), default=0)


def _escaped(text: str) -> int:
    """``text``'s length as JSON writes it, without its quotes."""
    return len(json.dumps(text)) - 2


def failing_case_frames(inputs: Mapping[str, Any]) -> str:
    """Each failing case's frame from the failure evidence, cut from the base: what a qa repair's
    failing-cases section shows of the suite (:func:`failing_line_excerpts`)."""
    cases = failing_cases_from_evidence(inputs.get("failure_evidence"))
    return failing_line_excerpts(cases, repair_base_files(inputs)) if cases else ""


def failing_line_excerpts(cases: list[dict[str, Any]], files: Mapping[str, str]) -> str:
    """Each failing case's failing line in the suite as the repair will edit it, numbered, with
    the line that failed marked — or "" when no case's file and line are in hand.

    The model sees the assertion that failed instead of a line number to find it by (1.8.2
    item 6, from the retest readout on 1.8.1's corpus): two scoped qa repairs edited lines
    near the failing one and failed again on it, and two fixed the failing line and failed on
    the next line of the same case.

    #2810 moved it here from ``handlers.impl.repair_handlers``.
    """
    blocks = []
    for case in cases:
        path, at = str(case.get("file") or ""), case.get("failing_line") or case.get("line")
        content = files.get(path)
        if not content or not isinstance(at, int):
            continue
        source = content.splitlines()
        if not 1 <= at <= len(source):
            continue
        first = max(1, at - FAILING_LINE_CONTEXT)
        last = min(len(source), at + FAILING_LINE_CONTEXT)
        numbered = "\n".join(
            f"{'→' if n == at else ' '} {n:>4} | {source[n - 1]}" for n in range(first, last + 1)
        )
        title = str(case.get("title") or "(suite-level)")
        blocks.append(f"`{path}:{at}` › {title}\n```\n{numbered}\n```")
    return "\n\n".join(blocks)
