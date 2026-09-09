"""The frozen API client a stack's suites mock beneath — the stack's declaration (#668).

A leaf module, like ``app_invocation``: a stack module declares a :class:`ClientSurface`
from the bytes it freezes, the registry carries it, and the suite-side check
(``client_mock_surface``) reads it. Nothing here names a stack or a file — the path, the
module specifier, the exports, the prefix and the envelope key all arrive as data.

Why a declaration and not the file: the check runs in four environments (the emitting
role's container, the repairing role's container, the verifier in runtime-api, the
retest) and the tree it sees differs in each; the client is frozen, so what the suite
must honour is known at plan time and travels as self-contained params, the way the
DOM anchor inventory does. A tree that lacks the client file changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KIND_FUNCTION = "function"
KIND_CLASS = "class"


@dataclass(frozen=True)
class ClientExport:
    """One name the client exports: a call (``function``) or an error type (``class``)."""

    name: str
    kind: str
    #: The declared parameters as written (``options = {}`` keeps its default).
    params: tuple[str, ...] = ()

    @property
    def param_names(self) -> tuple[str, ...]:
        return tuple(p.split("=", 1)[0].strip() for p in self.params)

    @property
    def signature(self) -> str:
        return f"{self.name}({', '.join(self.params)})"


@dataclass(frozen=True)
class ClientSurface:
    """What a suite's mock of the client, or its stub beneath it, has to honour."""

    #: The client's path in the emitted tree, for the finding a suite is handed back.
    path: str
    #: Regex source matching the specifier a suite names the module by in an import or a
    #: module mock — relative to where the stack's suites live.
    module_specifier: str
    exports: tuple[ClientExport, ...]
    #: The path prefix the client adds to every call — a view never passes it, and a
    #: stub beneath the client always sees it.
    path_prefix: str = ""
    #: The key a non-2xx body carries for the client to read code and message from.
    error_envelope_key: str = ""
    #: The default export, if the client has one. ``None`` means an ``import x from``
    #: resolves to nothing.
    default_export: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(e.name for e in self.exports)

    @property
    def call_exports(self) -> tuple[ClientExport, ...]:
        return tuple(e for e in self.exports if e.kind == KIND_FUNCTION)

    def export(self, name: str) -> ClientExport | None:
        for e in self.exports:
            if e.name == name:
                return e
        return None

    def as_params(self) -> dict[str, Any]:
        """The JSON-safe form the planner binds as a check param."""
        return {
            "path": self.path,
            "module_specifier": self.module_specifier,
            "exports": [
                {"name": e.name, "kind": e.kind, "params": list(e.params)} for e in self.exports
            ],
            "path_prefix": self.path_prefix,
            "error_envelope_key": self.error_envelope_key,
            "default_export": self.default_export,
        }

    @classmethod
    def from_params(cls, raw: Any) -> ClientSurface | None:
        """The declaration back from a check param; ``None`` for anything that is not one."""
        if not isinstance(raw, dict):
            return None
        path = str(raw.get("path") or "")
        spec = str(raw.get("module_specifier") or "")
        exports: list[ClientExport] = []
        for e in raw.get("exports") or []:
            if not isinstance(e, dict) or not e.get("name"):
                continue
            exports.append(
                ClientExport(
                    name=str(e["name"]),
                    kind=str(e.get("kind") or KIND_FUNCTION),
                    params=tuple(str(p) for p in e.get("params") or []),
                )
            )
        if not path or not spec or not exports:
            return None
        default = raw.get("default_export")
        return cls(
            path=path,
            module_specifier=spec,
            exports=tuple(exports),
            path_prefix=str(raw.get("path_prefix") or ""),
            error_envelope_key=str(raw.get("error_envelope_key") or ""),
            default_export=str(default) if default else None,
        )
