"""A generation's full rendered request, kept beside the capped display text (#1756).

``MAX_OBSERVABILITY_TEXT_LENGTH`` caps what LangFuse displays. A prompt longer than the cap is
also kept whole, compressed, in the generation's metadata under ``FULL_PROMPT_KEY``, so "what did
the model see?" has an answer by generation id. The adapter encodes it after redaction, and
``scripts/dev/read_full_prompt.py`` reads it back; both use this one format.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
from collections.abc import Mapping
from typing import Any

FULL_PROMPT_KEY = "full_prompt"
ENCODING = "gzip+base64"


class FullTextUnreadable(ValueError):
    """A stored full text that doesn't decode to what its own record says it holds."""


def encode_full_text(text: str) -> dict[str, Any]:
    """The stored form: the text gzipped and base64-encoded, with its length and its sha256, so
    a reader can tell a whole copy from a damaged one."""
    raw = text.encode("utf-8")
    return {
        "encoding": ENCODING,
        "chars": len(text),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "data": base64.b64encode(gzip.compress(raw, mtime=0)).decode("ascii"),
    }


def decode_full_text(stored: Mapping[str, Any]) -> str:
    """The text a stored form holds, refused unless it is exactly what the form records."""
    if stored.get("encoding") != ENCODING:
        raise FullTextUnreadable(f"not a {ENCODING} full text: {stored.get('encoding')!r}")
    try:
        raw = gzip.decompress(base64.b64decode(str(stored["data"]), validate=True))
    except (KeyError, ValueError, OSError) as e:
        raise FullTextUnreadable(f"the full text doesn't decode: {e}") from e
    if hashlib.sha256(raw).hexdigest() != stored.get("sha256"):
        raise FullTextUnreadable("the full text doesn't match its sha256")
    text = raw.decode("utf-8")
    if len(text) != stored.get("chars"):
        raise FullTextUnreadable(f"the full text is {len(text)} characters, not {stored['chars']}")
    return text
