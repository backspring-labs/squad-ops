"""
Output formatting for the SquadOps CLI (SIP-0065 §6.5).

Supports table, JSON, and quiet modes.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

_console = Console()
_err_console = Console(stderr=True)


def _literal(value: Any) -> Text:
    """Render a data value as itself, never as Rich markup (#931).

    Rich reads ``[...]`` in a string as a style tag and **removes** it. Every value the
    CLI prints is data, not markup, so a Next.js dynamic route arrived on screen as
    ``app/runs//page.tsx`` — the segment silently deleted, with nothing to indicate a
    path had been rewritten between the store and the terminal.

    That is worse than a display bug. The artifact table is the first surface a person
    reads when triaging a cycle, and it was showing them a filename that does not exist
    while looking authoritative. Any bracketed data has the same exposure — a JSON list,
    a parameterised path, a regex.
    """
    return Text(str(value))


def print_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    quiet: bool = False,
    title: str | None = None,
) -> None:
    """Print data as a Rich table or quiet tab-separated values.

    Args:
        headers: Column header names.
        rows: Row data (list of lists).
        quiet: If True, print raw tab-separated values without chrome.
        title: Optional table title.
    """
    if quiet:
        for row in rows:
            print("\t".join(str(cell) for cell in row))
        return

    table = Table(title=title)
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[_literal(cell) for cell in row])
    _console.print(table)


def print_detail(data: dict, *, quiet: bool = False) -> None:
    """Print a key-value detail view.

    Args:
        data: Dictionary of field names to values.
        quiet: If True, print raw tab-separated key=value pairs.
    """
    if quiet:
        for key, value in data.items():
            print(f"{key}\t{value}")
        return

    for key, value in data.items():
        # The label is ours and may carry markup; the value is data and never may.
        # Interpolating it into the same f-string is what let `[run_id]` disappear.
        _console.print(Text.assemble((f"{key}: ", "bold"), _literal(value)))


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def print_error(message: str) -> None:
    """Print error message to stderr."""
    _err_console.print(f"[bold red]{message}[/bold red]")


def print_success(message: str) -> None:
    """Print success message to stdout."""
    _console.print(f"[bold green]{message}[/bold green]")
