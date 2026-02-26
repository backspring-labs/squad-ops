"""
Output formatting for the SquadOps CLI (SIP-0065 §6.5).

Supports table, JSON, and quiet modes.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

_console = Console()
_err_console = Console(stderr=True)


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
        table.add_row(*[str(cell) for cell in row])
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
        _console.print(f"[bold]{key}:[/bold] {value}")


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def print_error(message: str) -> None:
    """Print error message to stderr."""
    _err_console.print(f"[bold red]{message}[/bold red]")


def print_success(message: str) -> None:
    """Print success message to stdout."""
    _console.print(f"[bold green]{message}[/bold green]")
