#!/usr/bin/env python3
"""Attach a line's verification-set records to its GitHub Release, after a credential scan.

1.8.2 plan §3.2 item 16, decision 7 (ruled 2026-09-24). A line's records (every roll,
shakeout, diagnostic and window record under ``var/verification_sets/``) are write-once
evidence, and until now their only copy lived on one box. The 1.7.4 and 1.7.5 records survived
only because someone checked two worktrees before removing them.

    attach_release_records.py 1.8.1                  # build, scan, preview; nothing leaves
    attach_release_records.py 1.8.1 --upload --expect-sha256 <the preview's>
                                                     # rebuild; upload only the approved bytes

It does three things:

1. **Tar the line's records.** Every entry in the main checkout's ``var/verification_sets/``
   named for the line (``1-8-1`` or ``1-8-1-*``, never ``1-8-10``). With ``--archive-root``, it
   also takes the line's records preserved there by the worktree sweep (cut step 8).

   **And its campaigns' outputs** (#1941 item 6): ``var/campaigns/<campaign>/`` (the log
   windows, the recovery diagnostics' records, the live-lease proofs) and the campaign's
   ``<campaign>.archive.log``. A campaign's id names no line, so the line's campaigns are the
   ones a tracked ``examples/*/campaigns/provenance.yaml`` names (the campaigns SquadOps runs to
   verify itself) created after the previous tag and up to this one. A campaign directory that
   no provenance names is an operator's, or provenance is stale: it is named, never carried.
2. **Scan every line of every file** before anything leaves the box, for:
   - the values of the deploy's secrets: ``secrets/*``, which is what ``secret://`` expands to
   - secret-named values in the repo's ``.env``
   - secret-named ``SQUADOPS__*`` values in the running containers' environment
   - Langfuse and API key prefixes (``pk-lf-``, ``sk-lf-``, ``sk-``), JWTs, and private keys

   A hit refuses the upload and names the file, the line and the kind of secret, never the
   value. A secret too short to search for without false hits is named as unscanned.
3. **Upload** (``--upload`` only) with ``gh release upload``, then write the asset's name,
   sha256, file count and size into the release package, so the page names what the Release
   carries. The upload requires ``--expect-sha256``, the checksum the preview printed and the
   owner approved, and refuses a rebuild that differs: the tarball is byte-stable (#1732), so
   a difference means the records changed since the preview.

The repository is public, so the Release is too. The package pages already publish each
cycle's id, verdict and checks; the tarball adds the log-derived texture and the deploy
identities, and must never add a secret.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))
from checkouts import main_checkout  # noqa: E402

RECORDS = Path("var") / "verification_sets"
CAMPAIGNS = Path("var") / "campaigns"
PROVENANCE = "examples/*/campaigns/provenance.yaml"
RELEASES = Path("site") / "content" / "releases"
#: A variable whose NAME says it holds a secret. The value of anything else (a model name, a
#: URL) appears in records legitimately and would bury a real hit.
SECRET_NAME = re.compile(r"PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE|CREDENTIAL|DSN|SALT|_KEY$", re.I)
#: Shorter literals are named as unscanned rather than searched for: "admin" or a 4-digit pin
#: would match every record and hide the real finding.
MIN_SECRET_LEN = 6
PATTERNS: dict[str, re.Pattern[str]] = {
    "langfuse key": re.compile(r"\b[ps]k-lf-[0-9A-Za-z-]{8,}"),
    "api key (sk-)": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Secret:
    source: str  # where it came from, e.g. "secrets/db_password.txt" or ".env DB_PASSWORD"
    value: str


@dataclass(frozen=True)
class Hit:
    member: str
    line: int
    kind: str


def line_of(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"{version!r} is not MAJOR.MINOR.PATCH")
    return version.replace(".", "-")


def _named_for(name: str, line: str) -> bool:
    return name == line or name.startswith(f"{line}-")


def collect_records(main: Path, line: str, archive_root: Path | None) -> list[tuple[str, Path]]:
    """``(name in the tarball, source file)`` for every record of the line, sorted."""
    out: list[tuple[str, Path]] = []
    records = main / RECORDS
    roots = [(RECORDS, records)] if records.is_dir() else []
    if archive_root is not None:
        for kept in sorted(p for p in archive_root.expanduser().iterdir() if p.is_dir()):
            roots.append(
                (Path("archive") / kept.name / "verification_sets", kept / "verification_sets")
            )
    for prefix, root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not _named_for(entry.name, line):
                continue
            files = (
                [entry] if entry.is_file() else sorted(p for p in entry.rglob("*") if p.is_file())
            )
            out += [((prefix / f.relative_to(root)).as_posix(), f) for f in files]
    return out


@dataclass(frozen=True)
class CampaignRecords:
    members: list[tuple[str, Path]]
    carried: list[str]  # the line's campaigns whose outputs the tarball carries, by id
    no_outputs: list[str]  # named by provenance for the line, with nothing on this box
    unnamed: list[str]  # outputs on this box that no provenance names: never carried


def tag_window(main: Path, tag: str) -> tuple[datetime | None, datetime]:
    """The line's window: after the previous tag's commit, up to and including this tag's. A
    campaign belongs to the line whose window holds its creation, as a verification set belongs
    to the line it is named for. The records attach after the tag (cut step 6), so a missing
    tag is refused."""

    def git(*args: str) -> str:
        done = subprocess.run(["git", "-C", str(main), *args], capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout.strip()

    tags = git("tag", "--sort=-v:refname").split()
    if tag not in tags:
        raise SystemExit(f"tag {tag} not found: the records attach after the tag (cut step 6)")
    index = tags.index(tag)
    previous = tags[index + 1] if index + 1 < len(tags) else None

    def date(t: str) -> datetime:
        return datetime.fromisoformat(git("log", "-1", "--format=%cI", t))

    return (date(previous) if previous else None), date(tag)


def collect_campaigns(main: Path, tag: str) -> CampaignRecords:
    """The line's campaigns' outputs, ``(name in the tarball, source file)``, sorted."""
    named: dict[str, datetime] = {}
    for prov in sorted(main.glob(PROVENANCE)):
        for c in (yaml.safe_load(prov.read_text(encoding="utf-8")) or {}).get("campaigns") or []:
            named[str(c["campaign_id"])] = datetime.fromisoformat(str(c["created"]))
    root = main / CAMPAIGNS
    on_box = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    unnamed = [cid for cid in on_box if cid not in named]
    if not named:
        return CampaignRecords([], [], [], unnamed)
    since, until = tag_window(main, tag)
    members: list[tuple[str, Path]] = []
    carried: list[str] = []
    no_outputs: list[str] = []
    for cid in sorted(
        c for c, at in named.items() if (since is None or at > since) and at <= until
    ):
        files = sorted(p for p in (root / cid).rglob("*") if p.is_file())
        log = root / f"{cid}.archive.log"
        files += [log] if log.is_file() else []
        (carried if files else no_outputs).append(cid)
        members += [((CAMPAIGNS / f.relative_to(root)).as_posix(), f) for f in files]
    return CampaignRecords(members, carried, no_outputs, unnamed)


def _env_secrets(pairs: Iterable[tuple[str, str]], source: str) -> list[Secret]:
    return [
        Secret(f"{source} {key}", value)
        for key, value in pairs
        if SECRET_NAME.search(key) and value and not value.startswith("secret://")
    ]


def dotenv_pairs(path: Path) -> list[tuple[str, str]]:
    pairs = []
    for raw in path.read_text().splitlines() if path.is_file() else []:
        key, sep, value = raw.strip().partition("=")
        if sep and not key.startswith("#"):
            pairs.append((key.strip().removeprefix("export "), value.strip().strip("'\"")))
    return pairs


def deploy_env_pairs() -> list[tuple[str, str]]:
    """``(name, value)`` from every running ``squadops-*`` container's environment. A deploy
    that cannot be read refuses the scan: the attach runs at the cut, with the deploy up."""
    names = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    )
    if names.returncode != 0:
        raise SystemExit(f"cannot read the running deploy: {names.stderr.strip()}")
    pairs: list[tuple[str, str]] = []
    for name in (n for n in names.stdout.split() if n.startswith("squadops-")):
        env = subprocess.run(
            ["docker", "inspect", "-f", "{{json .Config.Env}}", name],
            capture_output=True,
            text=True,
        )
        for item in json.loads(env.stdout or "[]") if env.returncode == 0 else []:
            key, _, value = item.partition("=")
            if key.startswith("SQUADOPS__") or SECRET_NAME.search(key):
                pairs.append((key, value))
    return pairs


def known_secrets(main: Path, deploy_pairs: Sequence[tuple[str, str]]) -> list[Secret]:
    secrets = [
        Secret(f"secrets/{p.name}", p.read_text().strip())
        for p in sorted((main / "secrets").glob("*"))
        if p.is_file()
    ]
    secrets += _env_secrets(dotenv_pairs(main / ".env"), ".env")
    secrets += _env_secrets(deploy_pairs, "deploy env")
    return secrets


def tracked_files_with(main: Path, value: str) -> list[str]:
    """The repository's tracked files whose text holds ``value`` (``git grep -F``). A value
    committed there is public already, so the tarball cannot leak it. An untracked file (the
    deploy's ``.env``) never counts: only what the public repository already carries is public."""
    done = subprocess.run(
        ["git", "-C", str(main), "grep", "-F", "-l", "-z", "-e", value, "--"],
        capture_output=True,
        text=True,
    )
    return [path for path in done.stdout.split("\0") if path] if done.returncode == 0 else []


def split_public(
    secrets: Sequence[Secret], find: Callable[[str], list[str]]
) -> tuple[list[Secret], dict[str, str]]:
    """The secrets to scan, and those whose value the public repository already carries, each
    with the tracked file that carries it. The 2.0.0 cut's scan refused every campaign log: the
    Keycloak database password, committed in docker-compose.yml, is also the auth provider's name
    the runtime logs print. A public value cannot leak through the tarball; it is named, never
    silently dropped."""
    public = {s.source: paths[0] for s in secrets if (paths := find(s.value))}
    return [s for s in secrets if s.source not in public], public


def scan(members: Sequence[tuple[str, Path]], secrets: Sequence[Secret]) -> list[Hit]:
    literals = [s for s in secrets if len(s.value) >= MIN_SECRET_LEN]
    hits: list[Hit] = []
    for name, path in members:
        text = path.read_bytes().decode("utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), start=1):
            hits += [Hit(name, n, f"the value of {s.source}") for s in literals if s.value in line]
            hits += [Hit(name, n, kind) for kind, rx in PATTERNS.items() if rx.search(line)]
    return hits


def build_tarball(members: Sequence[tuple[str, Path]], out: Path, top: str) -> str:
    """Write the tarball; return its sha256. Owners are normalised, the members' mtimes kept
    (they are evidence of when each record was written), and the gzip header's own time pinned
    to 0 (#1732): it stamped the build time, so the preview the owner approved and the upload's
    rebuild were never the same bytes. The same records now build the same file."""
    buf = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for name, path in members:
            info = tar.gettarinfo(str(path), arcname=f"{top}/{name}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    out.write_bytes(buf.getvalue())
    return hashlib.sha256(buf.getvalue()).hexdigest()


def record_in_package(package: Path, block: dict) -> None:
    data = yaml.safe_load(package.read_text(encoding="utf-8")) or {}
    data["records"] = block
    # The builder's own dump settings, so the rest of the file is unchanged.
    package.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main(
    argv: Sequence[str] | None = None,
    *,
    deploy_pairs: Sequence | None = None,
    public_in: Callable[[str], list[str]] | None = None,
) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("version", help="the released version, e.g. 1.8.1")
    ap.add_argument(
        "--archive-root",
        type=Path,
        help="also take the line's records the worktree sweep archived there (cut step 8)",
    )
    ap.add_argument("--out-dir", type=Path, help="where the tarball is written (default: /tmp)")
    ap.add_argument("--upload", action="store_true", help="upload to the Release and record it")
    ap.add_argument(
        "--expect-sha256",
        help="required with --upload: the preview's checksum, which the rebuild must match",
    )
    args = ap.parse_args(argv)
    if args.upload and not args.expect_sha256:
        ap.error(
            "--upload requires --expect-sha256: run the preview, read it, and pass the sha256 it "
            "printed, so what is uploaded is what was approved (#1732)"
        )

    line = line_of(args.version)
    tag = f"v{args.version}"
    main_path = main_checkout(REPO_ROOT)
    package = main_path / RELEASES / tag / "package.yaml"
    campaigns = collect_campaigns(main_path, tag)
    members = collect_records(main_path, line, args.archive_root) + campaigns.members
    if not members:
        print(
            f"no records named for {line} under {main_path / RECORDS}, and no campaign of the "
            "line; nothing to attach"
        )
        return 1
    secrets, public = split_public(
        known_secrets(main_path, deploy_env_pairs() if deploy_pairs is None else deploy_pairs),
        public_in or (lambda value: tracked_files_with(main_path, value)),
    )
    short = [s.source for s in secrets if len(s.value) < MIN_SECRET_LEN]
    unscanned = [f"unscanned (shorter than {MIN_SECRET_LEN} chars): {source}" for source in short]
    unscanned += [
        f"not scanned, already public: the value of {source} is committed in {path}"
        for source, path in public.items()
    ]
    hits = scan(members, secrets)

    top = f"squadops-{args.version}-records"
    out = (args.out_dir or Path("/tmp")) / f"{top}.tar.gz"
    digest = build_tarball(members, out, top)
    size = out.stat().st_size
    print(f"{len(members)} files from {line} → {out} ({size:,} bytes, sha256 {digest})")
    print(f"campaigns carried: {len(campaigns.carried)} ({', '.join(campaigns.carried) or 'none'})")
    for cid in campaigns.no_outputs:
        print(f"  named by provenance for {line}, but no outputs on this box: {cid}")
    for cid in campaigns.unnamed:
        print(f"  not carried, named by no provenance.yaml: {cid}")
    print(
        f"scanned against {len(secrets) - len(short)} known secret values + {len(PATTERNS)} patterns"
    )
    for note in unscanned:
        print(f"  {note}")
    if hits:
        print(f"\nREFUSED — {len(hits)} credential hit(s); nothing uploaded:")
        for h in hits:
            print(f"  ✗ {h.member}:{h.line}  {h.kind}")
        return 1
    print("clean: no credential found")
    if not args.upload:
        print(f"\npreview only; --upload attaches it to {tag} and records it in {package}")
        return 0
    if digest != args.expect_sha256:
        print(
            f"\nREFUSED — the rebuild is sha256 {digest}, not the approved {args.expect_sha256}; "
            "the records changed since the preview. Nothing uploaded: preview again and re-read."
        )
        return 1
    if not package.is_file():
        raise SystemExit(
            f"{package} does not exist; capture the release package first (cut step 7)"
        )
    up = subprocess.run(
        ["gh", "release", "upload", tag, str(out)], capture_output=True, text=True, cwd=main_path
    )
    if up.returncode != 0:
        print(f"upload failed: {up.stderr.strip()}")
        return 1
    record_in_package(
        package,
        {
            "asset": out.name,
            "sha256": digest,
            "files": len(members),
            "campaigns": campaigns.carried,
            "bytes": size,
            "attached_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scanned": {"secret_values": len(secrets) - len(short), "patterns": list(PATTERNS)},
        },
    )
    print(f"attached to {tag}; recorded in {package}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
