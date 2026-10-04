"""What an artifact's filename may be: a relative path inside its artifact's directory.

The filesystem vault writes an artifact to ``<artifact dir> / filename``, and a filename that is
absolute, or that climbs out with ``..``, would resolve outside the vault. Agents' emitted names
already pass the fenced parser's rule (``_path_is_safe``), but the ingest route takes a client's
filename directly. So the rule lives here, once, and both the route and the vault apply it: the
route to refuse the request, the vault so that no caller can write outside it.
"""

from __future__ import annotations

from pathlib import PurePosixPath


def artifact_filename_refusal(filename: str) -> str | None:
    """Why ``filename`` cannot name an artifact's file, or ``None`` when it can.

    A name may be nested (``backend/routes.py``). It may not be blank, absolute, contain a ``..``
    segment, or carry a NUL byte.
    """
    if not filename or not filename.strip():
        return "the filename is blank"
    if "\x00" in filename:
        return "the filename contains a NUL byte"
    path = PurePosixPath(filename)
    if path.is_absolute():
        return "the filename is an absolute path; it must be relative to the artifact"
    if ".." in path.parts:
        return "the filename climbs out of the artifact with a '..' segment"
    return None
