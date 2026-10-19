"""The managed clone, on Git (SIP-0112 FR-02, FR-05, FR-06; E.4.2).

Each Project's repository is mirrored into ``<cache_root>/<project_id>.git``, a bare clone the
cache owns and can recreate: the external repository stays authoritative (§B.3). Nothing is
checked out here. A commit's tree is read from the object store and handed to the sandbox, which
holds the only live tree (§8.2.2).

Every Git call runs isolated:
- the machine's Git configuration and any inherited ``GIT_*`` variables are kept out;
- prompts are refused, so a repository that asks for credentials fails at once instead of
  hanging;
- the transports are an allow-list: https and ssh, and local paths only when the deploy configures
  a local root;
- the locator is checked against the registration rules again at the point of use, and every
  argument a caller supplied follows ``--end-of-options``;
- the host's resolved addresses are checked just before Git connects (#2459): a public name that
  resolves to the deploy itself (loopback, link-local, unspecified) is refused unless the
  allow-list names it. Git resolves the name again itself, so a name that changes its answer
  between the two lookups is out of reach of this check; the allow-list is the firm control.
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Collection, Mapping
from pathlib import Path
from urllib.parse import urlsplit

from squadops.ports.projects.source_repository import SourceRepositoryPort
from squadops.projects.models import CheckoutTree, SourceUnavailable
from squadops.projects.registration import (
    LocatorPolicy,
    LocatorRefused,
    check_locator,
    is_internal_address,
)

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")
_SCP_HOST = re.compile(r"^[A-Za-z0-9._-]+@(?P<host>[A-Za-z0-9.-]+):")
#: Where a captured candidate is kept in the clone: a namespace the product's remote never has,
#: so no fetch writes or prunes it.
_CAPTURE_REF = re.compile(r"^refs/squadops/[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*$")
_IDENTITY = re.compile(r"^[^<>\n]+$")
_REVIEW_BRANCH = re.compile(r"^squadops/[A-Za-z0-9_-]+$")


def _quoted(path: str) -> str:
    """fast-import's C-style quoted path, so no path can end its line or start a command."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


class GitSourceRepository(SourceRepositoryPort):
    def __init__(
        self,
        cache_root: Path,
        policy: LocatorPolicy,
        *,
        timeout_seconds: float = 300.0,
        committer_name: str,
        committer_email: str,
    ) -> None:
        if not (_IDENTITY.match(committer_name) and _IDENTITY.match(committer_email)):
            raise ValueError("a committer's name and email carry no angle brackets or newlines")
        self._cache_root = Path(cache_root)
        self._policy = policy
        self._timeout = timeout_seconds
        self._committer = f"{committer_name} <{committer_email}>"

    async def sync(self, project_id: str, locator: str, ref: str) -> str:
        try:
            check_locator(locator, self._policy)
        except LocatorRefused as e:
            raise SourceUnavailable(str(e), reason="locator_refused") from e
        if ref.startswith("-"):
            raise SourceUnavailable(f"{ref!r} is not a ref", reason="ref_refused")
        await asyncio.to_thread(self._refuse_internal_resolution, locator)
        return await asyncio.to_thread(self._sync, self._clone_dir(project_id), locator, ref)

    def _refuse_internal_resolution(self, locator: str) -> None:
        """#2459: a remote host whose addresses reach the deploy itself, unless allow-listed."""
        if "://" in locator:
            host = urlsplit(locator).hostname
        else:
            scp = _SCP_HOST.match(locator)
            host = scp["host"] if scp else None
        if not host or host.lower() in self._policy.allowed_hosts:
            return
        try:
            infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        except OSError as e:
            raise SourceUnavailable(f"{host} does not resolve: {e}", reason="resolve_host") from e
        for info in infos:
            address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
            if is_internal_address(address):
                raise SourceUnavailable(
                    f"{host} resolves to {address}, one of the deploy's own addresses: name it "
                    "in the allow-list to use it",
                    reason="internal_host",
                )

    async def tree_at(self, project_id: str, commit: str) -> CheckoutTree:
        if not _COMMIT.match(commit):
            raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        return await asyncio.to_thread(self._tree_at, self._clone_dir(project_id), commit)

    async def commit_tree(
        self,
        project_id: str,
        *,
        parent: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        ref: str,
        message: str,
    ) -> str:
        if not _COMMIT.match(parent):
            raise SourceUnavailable(f"{parent!r} is not a commit", reason="not_a_commit")
        if not _CAPTURE_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not a capture ref", reason="ref_refused")
        return await asyncio.to_thread(
            self._commit_tree, self._clone_dir(project_id), parent, files, executable, ref, message
        )

    async def export_patch(self, project_id: str, commit: str) -> bytes:
        if not _COMMIT.match(commit):
            raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        clone = self._clone_dir(project_id)
        return await asyncio.to_thread(
            self._git, clone, "format-patch", "--stdout", "--binary", "--full-index",
            "--no-signature", "-1", commit, step="export",
        )  # fmt: skip

    async def is_ancestor(self, project_id: str, ancestor: str, descendant: str) -> bool:
        for commit in (ancestor, descendant):
            if not _COMMIT.match(commit):
                raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        return await asyncio.to_thread(
            self._is_ancestor, self._clone_dir(project_id), ancestor, descendant
        )

    def _is_ancestor(self, clone: Path, ancestor: str, descendant: str) -> bool:
        for commit in (ancestor, descendant):
            self._git(clone, "cat-file", "-e", f"{commit}^{{commit}}", step="read")
        try:
            self._git(clone, "merge-base", "--is-ancestor", ancestor, descendant, step="ancestry")
        except SourceUnavailable as e:
            # exit 1 is git's "no", an answer rather than a failure
            if "exit 1" in str(e):
                return False
            raise
        return True

    async def commit_message(self, project_id: str, commit: str) -> str:
        if not _COMMIT.match(commit):
            raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        out = await asyncio.to_thread(
            self._git, self._clone_dir(project_id), "log", "-1", "--format=%B", commit,
            step="read",
        )  # fmt: skip
        return out.decode("utf-8", errors="replace")

    async def push_capture(
        self, project_id: str, locator: str, *, ref: str, branch: str, token: str
    ) -> None:
        if not _CAPTURE_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not a capture ref", reason="ref_refused")
        if not _REVIEW_BRANCH.match(branch):
            raise SourceUnavailable(f"{branch!r} is not a review branch", reason="ref_refused")
        try:
            check_locator(locator, self._policy)
        except LocatorRefused as e:
            raise SourceUnavailable(str(e), reason="locator_refused") from e
        https = urlsplit(locator).scheme == "https"
        if not https and ("://" in locator or _SCP_HOST.match(locator)):
            raise SourceUnavailable(
                "a review request's branch is pushed over https with the Project's token, and "
                f"{locator} is ssh, which needs a deploy key 2.4 doesn't hold",
                reason="locator_refused",
            )
        await asyncio.to_thread(self._refuse_internal_resolution, locator)
        # Over https the token travels as a config value in the environment, never in an
        # argument a process listing shows, and only for this push. A local repository under a
        # configured root takes none.
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        await asyncio.to_thread(
            self._git, self._clone_dir(project_id), "push", "--quiet", "--end-of-options",
            locator, f"{ref}:refs/heads/{branch}", step="push",
            config={"http.extraHeader": f"Authorization: Basic {basic}"} if https else None,
        )  # fmt: skip

    # --- the blocking half, run off the event loop ---

    def _commit_tree(
        self,
        clone: Path,
        parent: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        ref: str,
        message: str,
    ) -> str:
        """One fast-import stream: the whole tree replaces the parent's (``deleteall``), so the
        commit holds exactly ``files``, with their modes, and no working tree is written."""
        if not clone.is_dir():
            raise SourceUnavailable("the managed clone does not exist yet", reason="not_cloned")
        self._git(clone, "cat-file", "-e", f"{parent}^{{commit}}", step="read")
        executable = set(executable)
        body = message.encode()
        stream = [
            f"commit {ref}\n".encode(),
            f"committer {self._committer} {int(time.time())} +0000\n".encode(),
            f"data {len(body)}\n".encode() + body + b"\n",
            f"from {parent}\n".encode(),
            b"deleteall\n",
        ]
        for path in sorted(files):
            content = files[path]
            mode = "100755" if path in executable else "100644"
            stream.append(f"M {mode} inline {_quoted(path)}\n".encode())
            stream.append(f"data {len(content)}\n".encode() + content + b"\n")
        stream.append(b"done\n")
        self._git(
            clone, "fast-import", "--quiet", "--force", "--done", step="capture",
            stdin=b"".join(stream),
        )  # fmt: skip
        return self._git(clone, "rev-parse", "--verify", ref, step="capture").decode().strip()

    def _clone_dir(self, project_id: str) -> Path:
        if not _PROJECT_ID.match(project_id):
            raise SourceUnavailable(f"{project_id!r} is not a Project ID", reason="bad_project")
        return self._cache_root / f"{project_id}.git"

    def _sync(self, clone: Path, locator: str, ref: str) -> str:
        if clone.is_dir():
            self._git(clone, "remote", "set-url", "origin", "--", locator, step="fetch")
            # Branches and tags only, named: a mirror's own refspec (+refs/*:refs/*) would prune
            # every captured ref under refs/squadops/, which the product never has.
            self._git(
                clone, "fetch", "--prune", "--quiet", "origin",
                "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", step="fetch",
            )  # fmt: skip
        else:
            self._cache_root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f".{clone.name}.", dir=self._cache_root))
            try:
                self._git(
                    self._cache_root,
                    "clone",
                    "--mirror",
                    "--quiet",
                    "--end-of-options",
                    locator,
                    str(staging / "clone"),
                    step="clone",
                )
                (staging / "clone").rename(clone)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        resolved = self._git(
            clone, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}",
            step="resolve",
        )  # fmt: skip
        return resolved.decode().strip()

    def _tree_at(self, clone: Path, commit: str) -> CheckoutTree:
        if not clone.is_dir():
            raise SourceUnavailable("the managed clone does not exist yet", reason="not_cloned")
        listing = self._git(clone, "ls-tree", "-r", "-z", "--full-tree", commit, step="read")
        blobs: dict[str, str] = {}
        executable, symlinks, submodules, undecodable = set(), set(), set(), set()
        for entry in listing.split(b"\0"):
            if not entry:
                continue
            meta, path_bytes = entry.split(b"\t", 1)
            mode, _kind, sha = meta.decode().split(" ")
            try:
                path = path_bytes.decode("utf-8")
            except UnicodeDecodeError:
                undecodable.add(path_bytes.decode("utf-8", errors="backslashreplace"))
                continue
            if mode == "120000":
                symlinks.add(path)
            elif mode == "160000":
                submodules.add(path)
            else:
                blobs[path] = sha
                if mode == "100755":
                    executable.add(path)
        return CheckoutTree(
            commit=commit,
            files=self._read_blobs(clone, blobs),
            executable=frozenset(executable),
            symlinks=frozenset(symlinks),
            submodules=frozenset(submodules),
            undecodable_paths=frozenset(undecodable),
        )

    def _read_blobs(self, clone: Path, blobs: dict[str, str]) -> dict[str, bytes]:
        if not blobs:
            return {}
        out = self._git(
            clone, "cat-file", "--batch", step="read", stdin="\n".join(blobs.values()) + "\n"
        )
        contents, at = {}, 0
        for path, sha in blobs.items():
            header_end = out.index(b"\n", at)
            got, _kind, size = out[at:header_end].decode().split(" ")
            if got != sha:
                raise SourceUnavailable(f"read {got} for {path}, expected {sha}", reason="read")
            start = header_end + 1
            contents[path] = out[start : start + int(size)]
            at = start + int(size) + 1
        return contents

    def _git(
        self,
        cwd: Path,
        *args: str,
        step: str,
        stdin: str | bytes | None = None,
        config: Mapping[str, str] | None = None,
    ) -> bytes:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_ASKPASS="/bin/false",
            GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
        )
        for i, (key, value) in enumerate((config or {}).items()):
            env[f"GIT_CONFIG_KEY_{i}"], env[f"GIT_CONFIG_VALUE_{i}"] = key, value
        if config:
            env["GIT_CONFIG_COUNT"] = str(len(config))
        file_transport = "always" if self._policy.local_roots else "never"
        command = [
            "git",
            "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always",
            "-c", "protocol.ssh.allow=always",
            "-c", f"protocol.file.allow={file_transport}",
            "-c", "core.hooksPath=/dev/null",
            *args,
        ]  # fmt: skip
        try:
            done = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                input=stdin.encode() if isinstance(stdin, str) else stdin,
                capture_output=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise SourceUnavailable(f"git {step} timed out", reason="timeout") from e
        except FileNotFoundError as e:
            raise SourceUnavailable("git is not installed here", reason="no_git") from e
        if done.returncode != 0:
            detail = done.stderr.decode(errors="replace").strip().splitlines()
            raise SourceUnavailable(
                f"git {step} failed: {detail[-1] if detail else f'exit {done.returncode}'}",
                reason=step,
            )
        return done.stdout
