"""Registering an existing product: the locator rules and the record (SIP-0112 E.4.1, R5)."""

import dataclasses

import pytest

from squadops.projects.registration import (
    LocatorPolicy,
    LocatorRefused,
    RegistrationRefused,
    check_locator,
    derive_project_id,
    prepare_registration,
)

ANY_HOST = LocatorPolicy()


@pytest.mark.parametrize(
    "locator",
    [
        "https://github.com/owner/tally.git",
        "https://code.example.org:8443/products/tally",
        "ssh://git@code.example.org/products/tally.git",
        "ssh://code.example.org:2222/products/tally.git",
        "git@github.com:owner/tally.git",
        "https://10.1.2.3/products/tally.git",
        "https://git.corp.example/products/tally.git",
    ],
)
def test_a_remote_locator_is_accepted(locator):
    check_locator(locator, ANY_HOST)


@pytest.mark.parametrize(
    ("locator", "reason"),
    [
        ("http://code.example.org/tally.git", "insecure_scheme"),
        ("ftp://code.example.org/tally.git", "unsupported_scheme"),
        ("https://user:hunter2@github.com/owner/tally.git", "credentials_in_locator"),
        ("https://ghp_token@github.com/owner/tally.git", "credentials_in_locator"),
        ("ssh://git:pw@code.example.org/tally.git", "credentials_in_locator"),
        ("https://github.com", "malformed"),
        ("https://github.com:notaport/owner/tally", "malformed"),
        ("/srv/repos/tally.git", "local_path"),
        ("file:///srv/repos/tally.git", "local_path"),
        ("../tally", "local_path"),
        ("C:\\repos\\tally", "local_path"),
        ("--upload-pack=/tmp/payload", "option_like"),
        ("ssh://-oProxyCommand=touch%20x@github.com/o/r.git", "option_like"),
        ("ssh://user@-oProxyCommand=x/o/r.git", "option_like"),
        ("git@-evil.example:o/r.git", "option_like"),
        ("git@github.com:-upload-pack=x", "option_like"),
        ("ssh://github.com/-x", "option_like"),
        ("https://localhost/o/r.git", "internal_host"),
        ("https://127.0.0.1:8001/o/r.git", "internal_host"),
        ("https://[::1]/o/r.git", "internal_host"),
        ("https://169.254.169.254/latest/meta-data", "internal_host"),
        ("ssh://postgres:5432/o/r.git", "internal_host"),
        ("git@runtime-api:o/r.git", "internal_host"),
        ("https://0.0.0.0/o/r.git", "internal_host"),
        ("https://[::ffff:127.0.0.1]/o/r.git", "internal_host"),
        (" https://github.com/owner/tally.git", "malformed"),
        ("", "malformed"),
    ],
)
def test_a_locator_the_rules_refuse_names_the_rule(locator, reason):
    """Bugs caught: a credential stored in the Project Record and every log that prints it; a
    path on the caller's machine taken as authority on the server's; a locator Git reads as an
    option when E.4.2 clones it."""
    with pytest.raises(LocatorRefused) as refused:
        check_locator(locator, ANY_HOST)
    assert refused.value.details == {"reason": reason}


def test_the_allow_list_and_the_local_roots_widen_nothing_else():
    policy = LocatorPolicy.of(["Code.Example.org"], ["/srv/repos"])

    check_locator("https://code.example.org/tally.git", policy)
    check_locator("git@code.example.org:tally.git", policy)
    check_locator("/srv/repos/tally.git", policy)
    check_locator("file:///srv/repos/team/tally.git", policy)
    for locator, reason in [
        ("https://github.com/owner/tally.git", "host_not_allowed"),
        ("/srv/repos-other/tally.git", "local_path"),
        ("/srv/repos/../etc/tally.git", "local_path"),
    ]:
        with pytest.raises(LocatorRefused) as refused:
            check_locator(locator, policy)
        assert refused.value.details == {"reason": reason}


def _register(**overrides):
    fields = {
        "idempotency_key": "import-1",
        "name": "Tally",
        "repo_uri": "https://code.example.org/tally.git",
        "base_ref": "refs/heads/main",
        "contribution_mode": "review_request",
        "owner": "Tally Maintainer",
        "policy": ANY_HOST,
        **overrides,
    }
    return prepare_registration(**fields)


def test_a_registration_is_built_with_a_derived_id_and_its_delegation_in_order():
    registration = _register(delegated_actions=["integration", "contribution", "contribution"])

    assert registration.project_id == "prj-tally"
    assert registration.source.repository_root == "."
    assert registration.ownership.delegated_actions == ("contribution", "integration")


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"base_ref": "-orphan"}, "base_ref"),
        ({"base_ref": "refs/heads/../main"}, "base_ref"),
        ({"base_ref": "refs/heads/feature x"}, "base_ref"),
        ({"repository_root": "../outside"}, "repository_root"),
        ({"repository_root": "/abs"}, "repository_root"),
        ({"project_id": "Tally"}, "project_id"),
        ({"project_id": "x"}, "project_id"),
        ({"name": "!!!"}, "project_id"),
        ({"owner": "  "}, "owner"),
        ({"idempotency_key": " "}, "idempotency_key"),
        ({"contribution_mode": "force_push"}, "contribution_mode or delegated_actions"),
        ({"delegated_actions": ["everything"]}, "contribution_mode or delegated_actions"),
    ],
)
def test_a_registration_that_breaks_a_rule_is_refused_naming_its_field(override, field):
    with pytest.raises(RegistrationRefused) as refused:
        _register(**override)
    assert refused.value.code == "REGISTRATION_INVALID"
    assert refused.value.details == {"field": field}


def test_the_request_hash_covers_every_field_but_the_key():
    """Bug caught: a field the hash leaves out, so a retry that changes it under the same key
    replays the first registration instead of being refused as a conflict."""
    base = _register()

    assert _register(idempotency_key="import-2").request_hash() == base.request_hash()
    for changed in (
        dataclasses.replace(base, name="Tally II"),
        dataclasses.replace(base, description="d"),
        dataclasses.replace(base, tags=("t",)),
        dataclasses.replace(base, source=dataclasses.replace(base.source, base_ref="refs/heads/x")),
        dataclasses.replace(base, ownership=dataclasses.replace(base.ownership, owner="Other")),
    ):
        assert changed.request_hash() != base.request_hash()


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Tally", "prj-tally"), ("Space Adventure 2!", "prj-space-adventure-2"), ("—", "")],
)
def test_a_derived_id_is_prj_and_the_names_words(name, expected):
    assert derive_project_id(name) == expected


def test_an_internal_host_the_allow_list_names_is_accepted():
    """#2459: the deploy's own hosts are refused by default, never forbidden outright."""
    policy = LocatorPolicy.of(["gitea", "127.0.0.1"], [])

    check_locator("ssh://gitea/products/tally.git", policy)
    check_locator("https://127.0.0.1:3000/products/tally.git", policy)
    with pytest.raises(LocatorRefused) as refused:
        check_locator("https://localhost/products/tally.git", policy)
    assert refused.value.details == {"reason": "host_not_allowed"}
