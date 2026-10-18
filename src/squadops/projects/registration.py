"""Registering an existing product (SIP-0112 FR-02, D.2, E.4.1; the owner's R5, 2026-10-18).

A registration records where the product's authoritative repository is, which ref it develops
from, how changes reach it, and what its owner delegates: the Project Record. It is validated here,
before anything is written, and stored in one transaction keyed by its idempotency key.

**The locator rules (R5).** A registration names a repository the runtime API's side will clone
(E.4.2), so its locator is checked for what it would let a caller reach:

- ``https`` and ``ssh`` URLs and the scp form ``user@host:path`` are accepted;
- ``http`` is refused (insecure), and so is any other scheme;
- a local path or a ``file`` URL is refused unless it lies under a root the deploy configures, off
  by default: a path on the CLI's machine authorizes nothing on the server's (D.2);
- a locator that carries credentials is refused: a secret never travels in a locator, and the
  managed clone resolves one by reference (E.4.2);
- a host outside the deploy's allow-list is refused when the list names any host;
- the deploy's own hosts are refused unless the allow-list names them: loopback, link-local
  (the cloud metadata address among them), the unspecified address, ``localhost`` and any
  single-label name, as a compose service is (the owner's ruling on #2459). Private ranges stay
  allowed, since a company's own Git server usually lives in one;
- a locator, or any user, host or path segment in it, beginning with ``-`` is refused, as is a
  ref: a Git command would read it as an option, whatever its version guards itself.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from squadops.projects.models import (
    ContributionMode,
    DelegatedAction,
    ProjectOwnership,
    ProjectSource,
)

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")
_SCP = re.compile(r"^(?P<user>[A-Za-z0-9._-]+)@(?P<host>[A-Za-z0-9.-]+):(?P<path>.+)$")
_REF = re.compile(r"^[A-Za-z0-9._/-]+$")


class RegistrationRefused(ValueError):
    """A registration refused before anything is written, with its error code and details."""

    code = "REGISTRATION_INVALID"

    def __init__(self, message: str, **details: str) -> None:
        super().__init__(message)
        self.details = details


class LocatorRefused(RegistrationRefused):
    code = "LOCATOR_REFUSED"


@dataclass(frozen=True)
class LocatorPolicy:
    """The deploy's locator rules (R5): which hosts, if the list names any, and which local
    roots, none by default."""

    allowed_hosts: frozenset[str] = frozenset()
    local_roots: tuple[str, ...] = ()

    @classmethod
    def of(cls, allowed_hosts: Iterable[str], local_roots: Iterable[str]) -> LocatorPolicy:
        return cls(
            frozenset(h.lower() for h in allowed_hosts),
            tuple(str(PurePosixPath(r)) for r in local_roots),
        )


def check_locator(locator: str, policy: LocatorPolicy) -> None:
    """Refuse a locator the deploy does not allow, naming the rule (R5)."""
    if not locator or locator != locator.strip() or any(c.isspace() for c in locator):
        raise LocatorRefused("a locator is one non-blank word", reason="malformed")
    if locator.startswith("-"):
        raise LocatorRefused("a locator may not begin with '-'", reason="option_like")
    if "://" in locator:
        _check_url(locator, policy)
        return
    scp = _SCP.match(locator)
    if scp:
        _no_option(scp["user"], "user")
        _no_option(scp["host"], "host")
        _no_option_in_path(scp["path"])
        _check_host(scp["host"], policy)
        return
    _check_local(locator, policy)


def _check_url(locator: str, policy: LocatorPolicy) -> None:
    try:
        url = urlsplit(locator)
        host, _ = url.hostname, url.port
    except ValueError as e:
        raise LocatorRefused(f"not a URL: {e}", reason="malformed") from e
    scheme = url.scheme.lower()
    if scheme == "file":
        _check_local(url.path, policy)
        return
    if scheme == "http":
        raise LocatorRefused("http is not allowed: use https or ssh", reason="insecure_scheme")
    if scheme not in ("https", "ssh"):
        raise LocatorRefused(f"the {scheme!r} scheme is not allowed", reason="unsupported_scheme")
    if url.password is not None or (scheme == "https" and url.username is not None):
        raise LocatorRefused(
            "a locator may not carry credentials: name a secret reference instead",
            reason="credentials_in_locator",
        )
    if not host or url.path in ("", "/"):
        raise LocatorRefused("a locator names a host and a repository path", reason="malformed")
    if url.username is not None:
        _no_option(url.username, "user")
    _no_option(host, "host")
    _no_option_in_path(url.path)
    _check_host(host, policy)


def _check_host(host: str, policy: LocatorPolicy) -> None:
    name = host.lower().strip("[]")
    if name in policy.allowed_hosts:
        return
    if policy.allowed_hosts:
        raise LocatorRefused(f"{host} is not an allowed host", reason="host_not_allowed")
    if is_internal_host(name):
        raise LocatorRefused(
            f"{host} is one of the deploy's own hosts: name it in the allow-list to use it",
            reason="internal_host",
        )


def is_internal_host(name: str) -> bool:
    """A name or address that reaches the deploy itself (#2459): loopback, link-local, the
    unspecified address, ``localhost``, or a single-label name such as a compose service."""
    try:
        return is_internal_address(ipaddress.ip_address(name))
    except ValueError:
        return name == "localhost" or name.endswith(".localhost") or "." not in name


def is_internal_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """An address that reaches the deploy itself rather than another machine (#2459)."""
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return address.is_loopback or address.is_link_local or address.is_unspecified


def _no_option(component: str, what: str) -> None:
    if component.startswith("-"):
        raise LocatorRefused(
            f"a locator's {what} may not begin with '-': {component!r}", reason="option_like"
        )


def _no_option_in_path(path: str) -> None:
    for segment in path.split("/"):
        _no_option(segment, "path")


def _check_local(path: str, policy: LocatorPolicy) -> None:
    candidate = PurePosixPath(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise LocatorRefused(
            "a local path must be absolute, under a configured root", reason="local_path"
        )
    if not any(candidate.is_relative_to(root) for root in policy.local_roots):
        raise LocatorRefused(
            "a local path is allowed only under a root the deploy configures",
            reason="local_path",
        )


@dataclass(frozen=True)
class ProjectRegistration:
    """A validated registration of an existing product (``origin.mode: import``)."""

    project_id: str
    name: str
    description: str
    source: ProjectSource
    ownership: ProjectOwnership
    idempotency_key: str
    tags: tuple[str, ...] = field(default=())

    def request_hash(self) -> str:
        """What the idempotency key stands for: every field but the key. The same key with the
        same hash is a replay; with any other, a conflict."""
        payload = asdict(self)
        payload.pop("idempotency_key")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_project_id(name: str) -> str:
    """``prj-`` and the name's words, lowercased and joined by hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:58].rstrip("-")
    return f"prj-{slug}" if slug else ""


def prepare_registration(
    *,
    idempotency_key: str,
    name: str,
    repo_uri: str,
    base_ref: str,
    contribution_mode: str,
    owner: str,
    policy: LocatorPolicy,
    project_id: str | None = None,
    description: str = "",
    repository_root: str = ".",
    delegated_actions: Iterable[str] = (),
    acceptance_policy_ref: str | None = None,
    tags: Iterable[str] = (),
) -> ProjectRegistration:
    """Validate a registration and build its record, refusing the first rule it breaks."""
    if not idempotency_key.strip():
        raise RegistrationRefused("an idempotency key is required", field="idempotency_key")
    if not name.strip():
        raise RegistrationRefused("a Project has a name", field="name")
    if not owner.strip():
        raise RegistrationRefused("a Project names its owner (§B.5.1)", field="owner")
    resolved_id = project_id if project_id is not None else derive_project_id(name)
    if not _PROJECT_ID.match(resolved_id):
        raise RegistrationRefused(
            f"{resolved_id!r} is not a Project ID: a lowercase letter, then 2–63 of a–z, 0–9, "
            "'-' or '_'",
            field="project_id",
        )
    check_locator(repo_uri, policy)
    if base_ref.startswith("-") or ".." in base_ref or not _REF.match(base_ref):
        raise RegistrationRefused(f"{base_ref!r} is not a ref", field="base_ref")
    root = PurePosixPath(repository_root)
    if root.is_absolute() or ".." in root.parts:
        raise RegistrationRefused(
            "the repository root is a path inside the repository", field="repository_root"
        )
    try:
        mode = ContributionMode(contribution_mode)
        actions = tuple(sorted({DelegatedAction(a).value for a in delegated_actions}))
    except ValueError as e:
        raise RegistrationRefused(str(e), field="contribution_mode or delegated_actions") from e
    return ProjectRegistration(
        project_id=resolved_id,
        name=name.strip(),
        description=description,
        source=ProjectSource(
            repo_uri=repo_uri,
            base_ref=base_ref,
            contribution_mode=mode.value,
            repository_root=str(root),
        ),
        ownership=ProjectOwnership(
            owner=owner.strip(),
            delegated_actions=actions,
            acceptance_policy_ref=acceptance_policy_ref,
        ),
        idempotency_key=idempotency_key,
        tags=tuple(tags),
    )
