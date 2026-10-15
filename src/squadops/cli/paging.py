"""A page of a list command, as the runtime API pages its lists (#1891, #1976).

The limits mirror ``squadops.api.paging``. The CLI doesn't import that module, because it imports
FastAPI and the console script talks to the API only over HTTP (#582). A test holds the two equal.
"""

from __future__ import annotations

import typer

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def limit_option(noun: str) -> typer.models.OptionInfo:
    return typer.Option(DEFAULT_LIMIT, "--limit", min=1, max=MAX_LIMIT, help=f"{noun} per page")


def offset_option(order: str) -> typer.models.OptionInfo:
    return typer.Option(0, "--offset", min=0, help=f"Skip this many, {order}")


def say_when_full(shown: int, limit: int, offset: int) -> None:
    """A full page is not the whole list, so say so rather than end silently (#1891)."""
    if shown == limit:
        typer.echo(f"{limit} shown; there may be more: --offset {offset + limit}")
