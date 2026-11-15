"""The harness's fixed programs (SIP-0117 R3.6, D5, D10; #3039).

``execute_luau`` runs only these. Each is a file beside this module, read once and named by its
digest. A program that takes input has one ``{{PAYLOAD}}`` token, and a call puts the input in its
place as hex-encoded JSON. So the code sent is the program's text with digits and the letters a–f
where the token was, and nothing a caller hands it is ever run as Luau.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any

PAYLOAD_TOKEN = "{{PAYLOAD}}"

#: The programs, by name: their files are ``harness/<name>.luau``.
PROGRAMS = ("baseline", "identity", "script_marks", "sync")

_HEX = re.compile(r"[0-9a-f]*")


@dataclass(frozen=True)
class Program:
    name: str
    text: str
    digest: str

    @property
    def takes_payload(self) -> bool:
        return PAYLOAD_TOKEN in self.text

    def code(self, payload: Any = None) -> str:
        """The code sent for one call: the text, with ``payload`` in place of the token.
        Raises for a payload given to a program that takes none, or none given to one that
        does."""
        if not self.takes_payload:
            if payload is not None:
                raise ValueError(f"the {self.name} program takes no input")
            return self.text
        if payload is None:
            raise ValueError(f"the {self.name} program needs its input")
        hexed = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode().hex()
        if not _HEX.fullmatch(hexed):  # bytes.hex() is always this; the check is the contract
            raise ValueError("a payload encoded to something other than hex")
        return self.text.replace(PAYLOAD_TOKEN, hexed, 1)


@functools.cache
def program(name: str) -> Program:
    """The fixed program ``name``, or :class:`KeyError` for one the harness doesn't hold. A
    program file with the token more than once is refused: one call puts in one input."""
    if name not in PROGRAMS:
        raise KeyError(f"the harness holds no {name!r} program; it holds {', '.join(PROGRAMS)}")
    text = (
        resources.files(__package__).joinpath("harness", f"{name}.luau").read_text(encoding="utf-8")
    )
    if text.count(PAYLOAD_TOKEN) > 1:
        raise ValueError(f"harness/{name}.luau holds {PAYLOAD_TOKEN} more than once")
    return Program(name, text, hashlib.sha256(text.encode()).hexdigest())


def digests() -> dict[str, str]:
    """Every program's digest, by name: what a worker registers, so an operation can say which
    harness it ran (R4.6)."""
    return {name: program(name).digest for name in PROGRAMS}
