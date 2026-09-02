"""The emitted container's packaging, read statically (#598).

pf-38 (`cyc_32f85a56224d`) went green — verdict accepted, every criterion passed, the
application worked when reassembled by hand — and the container it emitted could not build
or run. Three defects, and no criterion read the files that carried them: every check ran
against the source tree or a directly launched process, never against the recipe. pf-39 drew
two of the three again from identical seeds, with one of them worse.

This module reproduces those three as deterministic findings over the emitted bytes — the
Dockerfile, the tree it copies from, the entry script it runs — so a per-round record can say
what the packaging would have done without building an image. It does not build or start
anything: that criterion (``package_builds``, declared unbuilt) needs a Docker-capable locus
and stays the owner's separate call.

The three, by the facts that make each one a defect rather than a style:

* ``npm_ci_without_lockfile`` — ``npm ci`` refuses to run without a lockfile, and the emitted
  frontend has none; ``npm run build`` (what ``frontend_build`` verifies) never needs one,
  which is exactly why the criterion did not see it.
* ``dist_packages_on_official_python_image`` — ``python:*`` images install to
  ``site-packages``; ``dist-packages`` is Debian's system-python layout, and a
  ``COPY --from`` of a path that does not exist fails the build.
* ``debian_nginx_default_site_unremoved`` — apt's nginx ships
  ``/etc/nginx/sites-enabled/default`` holding ``listen 80 default_server``; a server block
  copied into ``conf.d/`` loses to it, so ``/api/*`` answers with nginx's 404 page while the
  backend is healthy behind it. Alpine's ``apk`` nginx has a sibling default in ``http.d/``;
  that shape has not been observed in an emission and is not modelled here.

Pure functions over strings and a file listing; no I/O beyond the reader the caller hands in.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

FINDING_NPM_CI_WITHOUT_LOCKFILE = "npm_ci_without_lockfile"
FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE = "dist_packages_on_official_python_image"
FINDING_NGINX_DEFAULT_SITE_UNREMOVED = "debian_nginx_default_site_unremoved"

FINDING_CODES: tuple[str, ...] = (
    FINDING_NPM_CI_WITHOUT_LOCKFILE,
    FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE,
    FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
)

#: What ``npm ci`` reads. ``npm-shrinkwrap.json`` takes precedence when both exist.
NPM_LOCKFILES: frozenset[str] = frozenset({"package-lock.json", "npm-shrinkwrap.json"})
#: The official image family whose layout is ``site-packages``.
_OFFICIAL_PYTHON_IMAGE = re.compile(r"^(?:docker\.io/)?(?:library/)?python(?:[:@]|$)")
_DIST_PACKAGES = "/dist-packages"
_NGINX_CONF_DIR = "/etc/nginx/"
_NGINX_MAIN_CONF = "/etc/nginx/nginx.conf"
_NGINX_DEFAULT_SITE = "sites-enabled/default"
_NGINX_SITES_INCLUDE = "sites-enabled"

_NPM_CI = re.compile(r"(?:^|[\s;&|(])npm\s+ci(?:\s|$)")
_NPM_INSTALL_FALLBACK = re.compile(r"\|\|\s*npm\s+(?:install|i)(?:\s|$)")
_APT_INSTALL = re.compile(r"^\s*(?:sudo\s+)?apt(?:-get)?\s+(?:\S+\s+)*install\b")
_SHELL_SEGMENT = re.compile(r"&&|\|\||;")
_REMOVES_DEFAULT_SITE = re.compile(r"\b(?:rm|unlink)\b[^\n&|;]*" + re.escape(_NGINX_DEFAULT_SITE))
_GLOB_CHARS = re.compile(r"[*?\[]")


@dataclass(frozen=True)
class Instruction:
    line: int
    keyword: str
    args: str


@dataclass
class Stage:
    index: int
    line: int
    image: str
    name: str | None
    instructions: list[Instruction] = field(default_factory=list)


def parse_dockerfile(text: str) -> list[Stage]:
    """Instructions grouped by build stage, each with the line it starts on.

    Continuation lines (``\\`` at end) join their instruction; comments and blank lines are
    dropped; a ``# syntax=`` directive is a comment here. Instructions before the first
    ``FROM`` (``ARG`` only, by Docker's rules) are kept on a stage with no image.
    """
    stages: list[Stage] = []
    logical: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not pending:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            start = lineno
        if line.endswith("\\"):
            pending.append(line[:-1])
            continue
        pending.append(line)
        logical.append((start, " ".join(part.strip() for part in pending)))
        pending = []
    if pending:
        logical.append((start, " ".join(part.strip() for part in pending)))

    for lineno, statement in logical:
        keyword, _, args = statement.partition(" ")
        keyword = keyword.upper()
        args = args.strip()
        if keyword == "FROM":
            image, name = _parse_from(args)
            stages.append(Stage(index=len(stages), line=lineno, image=image, name=name))
            continue
        if not stages:
            stages.append(Stage(index=0, line=lineno, image="", name=None))
        stages[-1].instructions.append(Instruction(line=lineno, keyword=keyword, args=args))
    return stages


def _parse_from(args: str) -> tuple[str, str | None]:
    tokens = [t for t in args.split() if not t.startswith("--")]
    image = tokens[0] if tokens else ""
    name = None
    for i, tok in enumerate(tokens):
        if tok.upper() == "AS" and i + 1 < len(tokens):
            name = tokens[i + 1]
    return image, name


def _copy_parts(args: str) -> tuple[dict[str, str], list[str], str | None]:
    """``(flags, sources, dest)`` of a COPY/ADD, either exec-JSON or shell form."""
    flags: dict[str, str] = {}
    rest = args
    while rest.startswith("--"):
        flag, _, rest = rest.partition(" ")
        key, _, value = flag[2:].partition("=")
        flags[key] = value
        rest = rest.lstrip()
    if rest.startswith("["):
        try:
            tokens = [str(t) for t in json.loads(rest)]
        except ValueError:
            tokens = rest.split()
    else:
        tokens = rest.split()
    if len(tokens) < 2:
        return flags, tokens, None
    return flags, tokens[:-1], tokens[-1]


def _shell_of(args: str) -> str:
    """The shell text of a RUN/CMD/ENTRYPOINT, exec-JSON forms joined."""
    if args.startswith("["):
        try:
            return " ".join(str(t) for t in json.loads(args))
        except ValueError:
            return args
    return args


def _segments(shell: str) -> list[str]:
    return [seg.strip() for seg in _SHELL_SEGMENT.split(shell) if seg.strip()]


def _apt_installs_nginx(stage: Stage) -> Instruction | None:
    for ins in stage.instructions:
        if ins.keyword != "RUN":
            continue
        for seg in _segments(_shell_of(ins.args)):
            if _APT_INSTALL.match(seg) and "nginx" in seg.split():
                return ins
    return None


def _removes_default_site(stage: Stage) -> bool:
    return any(
        ins.keyword == "RUN" and _REMOVES_DEFAULT_SITE.search(_shell_of(ins.args))
        for ins in stage.instructions
    )


def _resolve_stage(ref: str, stages: list[Stage]) -> Stage | None:
    if ref.isdigit():
        idx = int(ref)
        return stages[idx] if 0 <= idx < len(stages) else None
    for stage in stages:
        if stage.name == ref:
            return stage
    return None


def _normalise(path: str) -> str:
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/") if path not in (".", "/") else path


def _lockfiles_reachable(sources: Iterable[str], tree: set[str]) -> list[str]:
    """Tree lockfiles a build-context COPY of ``sources`` would bring into the stage."""
    lockfiles = sorted(p for p in tree if PurePosixPath(p).name in NPM_LOCKFILES)
    if not lockfiles:
        return []
    reached: list[str] = []
    for raw in sources:
        src = _normalise(raw)
        for lock in lockfiles:
            if src in (".", "/") or lock == src or lock.startswith(src + "/"):
                reached.append(lock)
            elif _GLOB_CHARS.search(src) and fnmatch.fnmatchcase(lock, src):
                reached.append(lock)
    return sorted(set(reached))


def _npm_ci_findings(stage: Stage, tree: set[str], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    copied: list[str] = []
    tree_locks = sorted(p for p in tree if PurePosixPath(p).name in NPM_LOCKFILES)
    for ins in stage.instructions:
        if ins.keyword in ("COPY", "ADD"):
            flags, sources, _dest = _copy_parts(ins.args)
            if "from" not in flags:
                copied.extend(sources)
            continue
        if ins.keyword != "RUN":
            continue
        shell = _shell_of(ins.args)
        if not _NPM_CI.search(shell) or _NPM_INSTALL_FALLBACK.search(shell):
            continue
        if _lockfiles_reachable(copied, tree):
            continue
        if tree_locks:
            why = (
                f"the emitted tree has {', '.join(tree_locks)} but no COPY before this line "
                f"brings it into the stage (copied: {', '.join(copied) or 'nothing'})"
            )
        else:
            why = (
                "the emitted tree has no package-lock.json or npm-shrinkwrap.json "
                f"(copied: {', '.join(copied) or 'nothing'})"
            )
        findings.append(
            {
                "finding": FINDING_NPM_CI_WITHOUT_LOCKFILE,
                "file": file,
                "line": ins.line,
                "message": f"`npm ci` needs a lockfile in the build context; {why}",
            }
        )
    return findings


def _dist_packages_findings(stages: list[Stage], file: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for stage in stages:
        for ins in stage.instructions:
            if ins.keyword not in ("COPY", "ADD"):
                continue
            flags, sources, _dest = _copy_parts(ins.args)
            ref = flags.get("from")
            if ref is None or not any(_DIST_PACKAGES in s for s in sources):
                continue
            origin = _resolve_stage(ref, stages)
            image = origin.image if origin is not None else ref
            if not _OFFICIAL_PYTHON_IMAGE.match(image):
                continue
            offending = [s for s in sources if _DIST_PACKAGES in s]
            findings.append(
                {
                    "finding": FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE,
                    "file": file,
                    "line": ins.line,
                    "message": (
                        f"COPY --from={ref} copies {', '.join(offending)}, but {image} installs "
                        "to site-packages; dist-packages is Debian's system-python layout and "
                        "does not exist there, so the build fails at this COPY"
                    ),
                }
            )
    return findings


def _entry_script_removes_default_site(
    final: Stage, tree: set[str], read_file: Callable[[str], str | None]
) -> tuple[bool, str | None]:
    """Whether the script ENTRYPOINT/CMD runs (if it is in the tree) removes the default site."""
    script_tokens: list[str] = []
    for ins in final.instructions:
        if ins.keyword in ("ENTRYPOINT", "CMD"):
            try:
                tokens = shlex.split(_shell_of(ins.args))
            except ValueError:
                tokens = _shell_of(ins.args).split()
            script_tokens.extend(t for t in tokens if t.endswith(".sh"))
    for token in script_tokens:
        basename = PurePosixPath(token).name
        candidates = sorted(p for p in tree if PurePosixPath(p).name == basename)
        for path in candidates:
            content = read_file(path)
            if content is not None and _REMOVES_DEFAULT_SITE.search(content):
                return True, path
        if candidates:
            return False, candidates[0]
    return False, None


def _nginx_contributing_stages(stages: list[Stage]) -> list[Stage]:
    """The final stage plus every stage it copies ``/etc/nginx`` from — nginx's provenance
    (apt in the final stage, or a configured tree copied from a stage that apt-installed
    it: the 1.7.0 gating roll's shape)."""
    final = stages[-1]
    contributing: list[Stage] = [final]
    for ins in final.instructions:
        if ins.keyword not in ("COPY", "ADD"):
            continue
        flags, sources, _dest = _copy_parts(ins.args)
        ref = flags.get("from")
        if ref is None or not any(
            _normalise(s).startswith(_NGINX_CONF_DIR.rstrip("/")) for s in sources
        ):
            continue
        origin = _resolve_stage(ref, stages)
        if origin is not None and origin not in contributing:
            contributing.append(origin)
    return contributing


def _nginx_conf_copies(
    contributing: list[Stage],
) -> tuple[Instruction | None, tuple[Instruction, list[str]] | None]:
    """``(first COPY into conf.d, COPY onto nginx.conf with its sources)`` — the server
    block's landing and whether the main config was replaced."""
    confd_copy: Instruction | None = None
    main_conf_copy: tuple[Instruction, list[str]] | None = None
    for stage in contributing:
        for ins in stage.instructions:
            if ins.keyword not in ("COPY", "ADD"):
                continue
            flags, sources, dest = _copy_parts(ins.args)
            if "from" in flags or dest is None:
                continue
            if dest == _NGINX_MAIN_CONF:
                main_conf_copy = (ins, sources)
            elif dest.startswith(_NGINX_CONF_DIR) and confd_copy is None:
                confd_copy = ins
    return confd_copy, main_conf_copy


def _replaced_main_conf_includes_sites(
    main_conf_copy: tuple[Instruction, list[str]] | None,
    read_file: Callable[[str], str | None],
) -> bool:
    """A replaced nginx.conf shadows the default site only if it still includes
    ``sites-enabled/*``; an untouched one (Debian's) always does."""
    if main_conf_copy is None:
        return True
    _ins, sources = main_conf_copy
    for src in sources:
        content = read_file(_normalise(src))
        if content is not None and _NGINX_SITES_INCLUDE in content:
            return True
    return False


def _nginx_findings(
    stages: list[Stage], tree: set[str], read_file: Callable[[str], str | None], file: str
) -> list[dict[str, Any]]:
    if not stages:
        return []
    contributing = _nginx_contributing_stages(stages)
    apt_line = next(
        (line for line in (_apt_installs_nginx(stage) for stage in contributing) if line),
        None,
    )
    if apt_line is None:
        return []
    confd_copy, main_conf_copy = _nginx_conf_copies(contributing)
    if confd_copy is None:
        return []
    if not _replaced_main_conf_includes_sites(main_conf_copy, read_file):
        return []
    if any(_removes_default_site(stage) for stage in contributing):
        return []
    removed, script = _entry_script_removes_default_site(stages[-1], tree, read_file)
    if removed:
        return []
    inspected = f"; {script} does not remove it either" if script else ""
    return [
        {
            "finding": FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
            "file": file,
            "line": confd_copy.line,
            "message": (
                f"the server block lands under {_NGINX_CONF_DIR} here, but apt's nginx "
                f"(line {apt_line.line}) ships /etc/nginx/{_NGINX_DEFAULT_SITE} with "
                "`listen 80 default_server`, and nothing removes it — that server wins and "
                f"every proxied path answers with nginx's 404{inspected}"
            ),
        }
    ]


def packaging_findings(
    dockerfile_text: str,
    dockerfile_path: str,
    tree: Iterable[str],
    read_file: Callable[[str], str | None],
) -> list[dict[str, Any]]:
    """Every packaging finding the recipe and the emitted tree support, in recipe order.

    ``tree`` is the build context's file listing (workspace-relative posix paths);
    ``read_file`` returns a listed file's text or ``None``. Each finding names the recipe
    line it anchors to and says what the build or the running container would do.
    """
    stages = parse_dockerfile(dockerfile_text)
    files = {_normalise(p) for p in tree}
    findings: list[dict[str, Any]] = []
    for stage in stages:
        findings.extend(_npm_ci_findings(stage, files, dockerfile_path))
    findings.extend(_dist_packages_findings(stages, dockerfile_path))
    findings.extend(_nginx_findings(stages, files, read_file, dockerfile_path))
    return sorted(findings, key=lambda f: (f["line"], f["finding"]))
