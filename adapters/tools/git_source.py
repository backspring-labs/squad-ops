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
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from squadops.ports.projects.source_repository import SourceRepositoryPort
from squadops.projects.models import CheckoutTree, RefMoved, SourceUnavailable
from squadops.projects.registration import (
    LocatorPolicy,
    LocatorRefused,
    check_locator,
    is_internal_address,
)

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")
_SCP_HOST = re.compile(r"^[A-Za-z0-9._-]+@(?P<host>[A-Za-z0-9.-]+):")
#: Our namespace in the clone, which the product's remote never has, so no fetch writes or prunes
#: it: a captured candidate (``refs/squadops/<cycle>/<run>``) and a campaign's branch
#: (``refs/squadops/campaign/<campaign_id>``, SIP-0109 §24bv point 2).
_SQUADOPS_REF = re.compile(r"^refs/squadops/[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*$")
#: The object id ``update-ref`` reads as "no such ref": a compare-and-swap that creates one.
_NO_REF = "0" * 40
_IDENTITY = re.compile(r"^[^<>\n]+$")
_REVIEW_BRANCH = re.compile(r"^squadops/[A-Za-z0-9_-]+$")
_BRANCH_REF = re.compile(r"^refs/heads/[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9._-]+)*$")
#: Where a greenfield Project's first commit is made in the clone before it's pushed (E.4.6).
_INITIAL_REF = "refs/squadops/initial"


def _quoted(path: str) -> str:
    """fast-import's C-style quoted path, so no path can end its line or start a command."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _authorization(token: str) -> dict[str, str]:
    """Over https the token travels as a config value in the environment, never in an argument a
    process listing shows, and only for the one push it's given for."""
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {"http.extraHeader": f"Authorization: Basic {basic}"}


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

    async def sync(
        self, project_id: str, locator: str, ref: str, *, token: str | None = None
    ) -> str:
        try:
            check_locator(locator, self._policy)
        except LocatorRefused as e:
            raise SourceUnavailable(str(e), reason="locator_refused") from e
        if ref.startswith("-"):
            raise SourceUnavailable(f"{ref!r} is not a ref", reason="ref_refused")
        await asyncio.to_thread(self._refuse_internal_resolution, locator)
        https = urlsplit(locator).scheme == "https"
        return await asyncio.to_thread(
            self._sync, self._clone_dir(project_id), locator, ref,
            _authorization(token) if token and https else None,
        )  # fmt: skip

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
        if not _SQUADOPS_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not a capture ref", reason="ref_refused")
        return await asyncio.to_thread(
            self._commit_tree, self._clone_dir(project_id), parent, files, executable, ref, message
        )

    async def update_ref(
        self, project_id: str, ref: str, *, new_commit: str, expected_commit: str | None
    ) -> None:
        for commit in (new_commit, expected_commit or _NO_REF):
            if not _COMMIT.match(commit):
                raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        if not _SQUADOPS_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not one of our refs", reason="ref_refused")
        await asyncio.to_thread(
            self._update_ref, self._clone_dir(project_id), ref, new_commit, expected_commit
        )

    async def ref_commit(self, project_id: str, ref: str) -> str | None:
        if not _SQUADOPS_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not one of our refs", reason="ref_refused")
        clone = self._clone_dir(project_id)
        if not clone.is_dir():
            raise SourceUnavailable("the managed clone does not exist yet", reason="not_cloned")
        return await asyncio.to_thread(self._ref_commit, clone, ref)

    async def export_patch(self, project_id: str, commit: str) -> bytes:
        if not _COMMIT.match(commit):
            raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        clone = self._clone_dir(project_id)
        return await asyncio.to_thread(
            self._git, clone, "format-patch", "--stdout", "--binary", "--full-index",
            "--no-signature", "-1", commit, step="export",
        )  # fmt: skip

    async def file_at(self, project_id: str, commit: str, path: str) -> bytes:
        if not _COMMIT.match(commit):
            raise SourceUnavailable(f"{commit!r} is not a commit", reason="not_a_commit")
        parts = PurePosixPath(path).parts
        if not path or path.startswith(("/", "-")) or ".." in parts or ":" in path:
            raise SourceUnavailable(f"{path!r} is not a repository path", reason="path_refused")
        clone = self._clone_dir(project_id)
        return await asyncio.to_thread(
            self._git, clone, "cat-file", "blob", f"{commit}:{path}", step="read"
        )

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
        if not _SQUADOPS_REF.match(ref):
            raise SourceUnavailable(f"{ref!r} is not a capture ref", reason="ref_refused")
        if not _REVIEW_BRANCH.match(branch):
            raise SourceUnavailable(f"{branch!r} is not a review branch", reason="ref_refused")
        https = self._push_target(locator, "a review request's branch")
        await asyncio.to_thread(self._refuse_internal_resolution, locator)
        await asyncio.to_thread(
            self._git, self._clone_dir(project_id), "push", "--quiet", "--end-of-options",
            locator, f"{ref}:refs/heads/{branch}", step="push",
            config=_authorization(token) if https else None,
        )  # fmt: skip

    async def initialize(
        self,
        project_id: str,
        locator: str,
        *,
        ref: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        message: str,
        committed_at: int,
        token: str,
    ) -> str:
        if not _BRANCH_REF.match(ref) or ".." in ref or ref.endswith(".lock"):
            raise SourceUnavailable(f"{ref!r} is not a branch (refs/heads/…)", reason="ref_refused")
        https = self._push_target(locator, "a greenfield Project's first commit")
        await asyncio.to_thread(self._refuse_internal_resolution, locator)
        return await asyncio.to_thread(
            self._initialize, self._clone_dir(project_id), locator, ref, files, executable,
            message, committed_at, _authorization(token) if https else None,
        )  # fmt: skip

    def _push_target(self, locator: str, what: str) -> bool:
        """Whether ``locator`` is pushed to over https, with the Project's token; otherwise it's a
        local repository under a configured root, which takes none. ssh is refused."""
        try:
            check_locator(locator, self._policy)
        except LocatorRefused as e:
            raise SourceUnavailable(str(e), reason="locator_refused") from e
        https = urlsplit(locator).scheme == "https"
        if not https and ("://" in locator or _SCP_HOST.match(locator)):
            raise SourceUnavailable(
                f"{what} is pushed over https with the Project's token, and {locator} is ssh, "
                "which needs a deploy key 2.4 doesn't hold",
                reason="locator_refused",
            )
        return https

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
        return self._fast_import(clone, ref, parent, files, executable, message, int(time.time()))

    def _update_ref(self, clone: Path, ref: str, new: str, expected: str | None) -> None:
        """Git's own compare-and-swap: ``update-ref <ref> <new> <old>`` locks the ref and moves it
        only while it names ``<old>``, where all zeros means it must not exist. A refusal is read
        back: a ref somewhere else is the swap lost, and anything else is the clone's failure."""
        if not clone.is_dir():
            raise SourceUnavailable("the managed clone does not exist yet", reason="not_cloned")
        self._git(clone, "cat-file", "-e", f"{new}^{{commit}}", step="read")
        try:
            self._git(
                clone, "update-ref", "--no-deref", "--end-of-options", ref, new,
                expected or _NO_REF, step="update_ref",
            )  # fmt: skip
        except SourceUnavailable:
            held = self._ref_commit(clone, ref)
            if held != expected:
                raise RefMoved(
                    f"{ref} names {held or 'no commit'}, not "
                    f"{expected or 'nothing'} as expected: it was not moved to {new}",
                    held=held,
                ) from None
            raise

    def _ref_commit(self, clone: Path, ref: str) -> str | None:
        """The ref's commit, read by its full name: ``for-each-ref`` also lists the refs under a
        prefix, so only the line that names ``ref`` itself is read."""
        listing = self._git(
            clone, "for-each-ref", "--format=%(refname) %(objectname)", ref, step="resolve"
        )
        for line in listing.decode().splitlines():
            name, _, commit = line.partition(" ")
            if name == ref:
                return commit
        return None

    def _initialize(
        self,
        clone: Path,
        locator: str,
        ref: str,
        files: Mapping[str, bytes],
        executable: Collection[str],
        message: str,
        committed_at: int,
        config: Mapping[str, str] | None,
    ) -> str:
        self._fetch(clone, locator, config)
        commit = self._fast_import(
            clone, _INITIAL_REF, None, files, executable, message, committed_at
        )
        held = (
            self._git(clone, "for-each-ref", "--format=%(objectname)", ref, step="resolve")
            .decode()
            .strip()
        )
        if held == commit:
            return commit  # a retry of this request, whose push landed
        if held:
            raise SourceUnavailable(
                f"{ref} already holds commit {held[:12]}: a greenfield Project's first commit "
                "goes only to a branch with none",
                reason="not_empty",
            )
        # Never forced: a root commit fast-forwards no branch, so one that appeared since the
        # fetch refuses the push.
        self._git(
            clone, "push", "--quiet", "--end-of-options", locator, f"{_INITIAL_REF}:{ref}",
            step="push", config=config,
        )  # fmt: skip
        return commit

    def _fast_import(
        self,
        clone: Path,
        ref: str,
        parent: str | None,
        files: Mapping[str, bytes],
        executable: Collection[str],
        message: str,
        when: int,
    ) -> str:
        """``files``, the whole tree, as one commit set at ``ref``: on ``parent``, replacing its
        tree (``deleteall``), or with no parent, the ref reset first."""
        executable = set(executable)
        body = message.encode()
        head = [f"from {parent}\n".encode(), b"deleteall\n"] if parent else []
        stream = [
            *([] if parent else [f"reset {ref}\n".encode()]),
            f"commit {ref}\n".encode(),
            f"committer {self._committer} {when} +0000\n".encode(),
            f"data {len(body)}\n".encode() + body + b"\n",
            *head,
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

    def _sync(self, clone: Path, locator: str, ref: str, config: Mapping[str, str] | None) -> str:
        self._fetch(clone, locator, config)
        resolved = self._git(
            clone, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}",
            step="resolve",
        )  # fmt: skip
        return resolved.decode().strip()

    def _fetch(self, clone: Path, locator: str, config: Mapping[str, str] | None) -> None:
        """The clone made, or brought up to date with the product's branches and tags. A token's
        header is in ``config``, the environment of these git processes alone: the clone's own
        configuration never holds it."""
        if clone.is_dir():
            self._git(clone, "remote", "set-url", "origin", "--", locator, step="fetch")
            # Branches and tags only, named: a mirror's own refspec (+refs/*:refs/*) would prune
            # every captured ref under refs/squadops/, which the product never has.
            self._git(
                clone, "fetch", "--prune", "--quiet", "origin",
                "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", step="fetch",
                config=config,
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
                    config=config,
                )
                (staging / "clone").rename(clone)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

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
            # #2672: a working directory that isn't there raises the same error as a git binary
            # that isn't. The first is the managed clone, moved aside or lost with its container.
            if not cwd.is_dir():
                raise SourceUnavailable(
                    f"the managed clone is missing: {cwd} does not exist", reason="not_cloned"
                ) from e
            raise SourceUnavailable("git is not installed here", reason="no_git") from e
        if done.returncode != 0:
            detail = done.stderr.decode(errors="replace").strip().splitlines()
            raise SourceUnavailable(
                f"git {step} failed: {detail[-1] if detail else f'exit {done.returncode}'}",
                reason=step,
            )
        return done.stdout
