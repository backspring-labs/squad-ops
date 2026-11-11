"""Text digests (#1990).

Four modules hashed text with their own ``_sha256``: the bound scaffold record, the revision
transaction, the scaffold contract and the verification scaffold. Each digest is stored, in a
contract, a record or an edit, and compared later against the text it was taken from. So the
encoding is part of every stored identity, and it is decided here, once: UTF-8.

``canonical_json`` and ``canonical_sha256`` are the same decision for a structured record
(SIP-0116 §10's skillset record is the first to use them). A dozen modules each hold a private
``json.dumps(..., sort_keys=True, separators=(",", ":"))`` whose stored digests were taken with
their own settings, so they are left as they are: moving one would change what it compares.
"""

from __future__ import annotations

import hashlib
import json


def text_sha256(text: str) -> str:
    """The SHA-256 hex digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: object) -> str:
    """``value`` as canonical JSON: keys sorted, no insignificant whitespace, and text left
    as written, so its UTF-8 encoding is the identity (SIP-0116 §10). A value JSON can't
    represent raises ``TypeError``: a record that is hashed holds only what it can store."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    """The SHA-256 hex digest of ``value``'s canonical JSON, encoded as UTF-8."""
    return text_sha256(canonical_json(value))
