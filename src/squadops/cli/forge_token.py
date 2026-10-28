"""The caller's own forge token, for one act (SIP-0112 FR-06; SIP-0109 §24ci (b)).

A contribution, a private Project's validation or sync, and a Campaign's review-request push each
take the caller's token with the request, for that request alone: the deploy stores none of
them. ``--token-from-gh`` reads it from the GitHub CLI's login on the machine running the command.
"""

from __future__ import annotations

import typer

from squadops.cli.output import print_error


def gh_token() -> str:
    """The caller's own GitHub token, from the GitHub CLI's login. Never printed."""
    import subprocess

    try:
        done = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        print_error(f"--token-from-gh needs the GitHub CLI logged in: {type(e).__name__}")
        raise typer.Exit(code=2) from e
    token = done.stdout.strip()
    if done.returncode != 0 or not token:
        print_error("--token-from-gh: `gh auth token` gave no token; run `gh auth login` first")
        raise typer.Exit(code=2)
    return token
