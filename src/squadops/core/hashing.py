"""Text digests (#1990).

Four modules hashed text with their own ``_sha256``: the bound scaffold record, the revision
transaction, the scaffold contract and the verification scaffold. Each digest is stored, in a
contract, a record or an edit, and compared later against the text it was taken from. So the
encoding is part of every stored identity, and it is decided here, once: UTF-8.
"""

from __future__ import annotations

import hashlib


def text_sha256(text: str) -> str:
    """The SHA-256 hex digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
