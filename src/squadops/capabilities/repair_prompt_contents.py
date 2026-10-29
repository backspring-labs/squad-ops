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

The repair handlers render each through these functions, and the composer counts the three through
:func:`repair_prompt_contents` (``squadops.capabilities.prompt_budget``, SIP-0110 Appendix A §3.6).
Counted apart, the composer measured the whole tree: on a repository-backed product larger than
about half its model's window, the budget left for memory's sections read 0, and every repair was
held on its binding (the 2.5 main demonstration's round 2).

Pure: no I/O and no handler class, so the runtime's composer and the agent's handler both call it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.capabilities.anchored_edits import editable_file_lines, verbatim_block
from squadops.capabilities.context_assembly import REPAIR_FAILED_ARTIFACTS_KEY, scaffold_shell_paths
from squadops.cycles.failure_evidence import failing_cases_from_evidence
from squadops.cycles.write_authorization import normalize_ws_path

#: The inputs a repair's prompt shows a part of, through :func:`repair_prompt_contents`: the tree
#: it repairs and the failed task's own files over it. Neither is shown otherwise.
REPAIR_BASE_INPUTS = frozenset({"acceptance_workspace_files", REPAIR_FAILED_ARTIFACTS_KEY})

#: Lines of the suite shown on each side of a failing line (1.8.2 item 6): enough to take in
#: the assertion, the setup it rests on and the lines after it in the same case.
FAILING_LINE_CONTEXT = 6


def repair_prompt_contents(inputs: Mapping[str, Any]) -> dict[str, str]:
    """What a repair's prompt shows of its base, by the template variable that shows it: the
    current files, the edit form's file list and the failing-case frames, each ``""`` when the
    prompt shows none. The frames are a qa repair's alone, so a dev or builder repair's count is
    over by them, an upper bound."""
    lines, _offered = edit_form(inputs)
    return {
        "current_files": current_files(inputs),
        "editable_files": "\n".join(lines),
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
    were listed for each. Nothing when it may revise none."""
    files = anchorable_files(inputs)
    if not files:
        return [], {}
    return editable_file_lines(files, repair_base_files(inputs))


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

    #2810 moved it here from ``handlers.impl.repair_handlers``, which still exports it.
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
