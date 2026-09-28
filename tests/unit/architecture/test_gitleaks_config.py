"""The secret scan's own rules (.gitleaks.toml, run by .github/workflows/secret-scan.yml).

The CI job proves the rules fire inside gitleaks; these tests catch the cheaper failure first, at unit
time: a custom rule whose pattern no longer matches the shape it exists for, or an allowlist entry
added without saying why.
"""

from __future__ import annotations

import re
import tomllib
import uuid
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parents[3] / ".gitleaks.toml"


def _rules() -> dict[str, dict]:
    return {r["id"]: r for r in tomllib.loads(CONFIG.read_text())["rules"]}


@pytest.mark.parametrize(
    ("rule", "text", "caught"),
    [
        # The deploy's LangFuse keys are `sk-lf-` / `pk-lf-` plus a UUID.
        ("langfuse-key", f"sk-lf-{uuid.uuid4()}", True),
        ("langfuse-key", f'KEY = "pk-lf-{uuid.uuid4()}"', True),
        # A 20-character suffix, like SIP-0061's redaction fixture: not the deploy's UUID shape.
        # Every key-shaped value here is built at run time; a literal one in this file is exactly
        # what the scan exists to refuse.
        ("langfuse-key", f"pk-lf-{uuid.uuid4().hex[:20]}", False),
        ("squadops-secret-setting", f"SQUADOPS__DB__PASSWORD: {uuid.uuid4().hex[:16]}", True),
        ("squadops-secret-setting", f"SQUADOPS__LANGFUSE__SECRET_KEY=sk-lf-{uuid.uuid4()}", True),
        # Pointers to a secret, never one: a reference, a provider name, an interpolation.
        ("squadops-secret-setting", "SQUADOPS__DB__PASSWORD: secret://db_password", False),
        ("squadops-secret-setting", "SQUADOPS__SECRETS__PROVIDER: docker_secret", False),
        ("squadops-secret-setting", "SQUADOPS__DB__PASSWORD=${POSTGRES_PASSWORD}", False),
    ],
    ids=[
        "langfuse secret key",
        "langfuse public key in code",
        "the old 20-char fixture is not the deploy shape",
        "a literal password",
        "a pasted .env line",
        "a secret:// reference",
        "a provider name",
        "an interpolation",
    ],
)
def test_each_custom_rule_matches_the_shape_it_exists_for(rule, text, caught):
    """Bug caught: a rule pattern that silently matches nothing (the scan then passes every change)
    or one that flags a pointer to a secret on every compose file. gitleaks is Go RE2; these
    patterns use only syntax RE2 and Python share."""
    assert (re.search(_rules()[rule]["regex"], text) is not None) is caught


def test_every_allowlist_entry_says_why():
    """Bug caught: an allowlist entry added to silence a finding without recording what it is — the
    way a real secret gets waved through as a false positive."""
    config = tomllib.loads(CONFIG.read_text())
    entries = list(config.get("allowlists", []))
    for rule in config["rules"]:
        entries.extend(rule.get("allowlists", []))

    assert entries, "the baseline's false positives are allowlisted explicitly"
    assert [e for e in entries if len(e.get("description", "").split()) < 5] == []
