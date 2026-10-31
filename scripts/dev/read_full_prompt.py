#!/usr/bin/env python3
"""Print the full rendered request a generation was sent, by its generation id (#1756).

LangFuse displays a prompt cut at ``MAX_OBSERVABILITY_TEXT_LENGTH``. A longer one is kept whole,
redacted and compressed, in the generation's metadata (``squadops.telemetry.full_text``). This
reads it back through LangFuse's public API and prints it, or the display text when the prompt fit
under the cap.

    python scripts/dev/read_full_prompt.py <generation_id> [--out FILE]

The host and keys come from the deploy's own settings: ``SQUADOPS__LANGFUSE__HOST`` (default
``http://localhost:3001``), ``SQUADOPS__LANGFUSE__PUBLIC_KEY`` and ``SQUADOPS__LANGFUSE__SECRET_KEY``.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from squadops.telemetry.full_text import FULL_PROMPT_KEY, FullTextUnreadable, decode_full_text


def full_prompt(observation: Mapping[str, Any]) -> str:
    """The whole request: the stored full text when the prompt was longer than the cap, otherwise
    the display text, which then holds all of it."""
    metadata = observation.get("metadata") or {}
    stored = metadata.get(FULL_PROMPT_KEY) if isinstance(metadata, Mapping) else None
    if stored is not None:
        return decode_full_text(stored)
    shown = observation.get("input")
    return shown if isinstance(shown, str) else json.dumps(shown)


def fetch_observation(
    generation_id: str,
    *,
    host: str,
    public_key: str,
    secret_key: str,
    opener: Callable[[urllib.request.Request], Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """The generation, from ``GET /api/public/observations/{id}``."""
    request = urllib.request.Request(f"{host.rstrip('/')}/api/public/observations/{generation_id}")
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    with opener(request) as response:
        return json.loads(response.read().decode())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("generation_id")
    parser.add_argument("--out", type=Path, help="write the request here instead of stdout")
    args = parser.parse_args(argv)
    host = os.environ.get("SQUADOPS__LANGFUSE__HOST", "http://localhost:3001")
    keys = (
        os.environ.get("SQUADOPS__LANGFUSE__PUBLIC_KEY", ""),
        os.environ.get("SQUADOPS__LANGFUSE__SECRET_KEY", ""),
    )
    if not all(keys):
        print(
            "set SQUADOPS__LANGFUSE__PUBLIC_KEY and SQUADOPS__LANGFUSE__SECRET_KEY", file=sys.stderr
        )
        return 2
    try:
        observation = fetch_observation(
            args.generation_id, host=host, public_key=keys[0], secret_key=keys[1]
        )
        text = full_prompt(observation)
    except urllib.error.HTTPError as e:
        print(f"LangFuse answered {e.code} for generation {args.generation_id}", file=sys.stderr)
        return 1
    except FullTextUnreadable as e:
        print(f"generation {args.generation_id}: {e}", file=sys.stderr)
        return 1
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"{len(text)} characters written to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
