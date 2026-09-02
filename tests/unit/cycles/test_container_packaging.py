"""#598 — the emitted container's packaging, read statically and reported only.

pf-38 was accepted with 10/10 checks and shipped a container that could not build or run;
pf-39 drew two of the same three defects from identical seeds. The replays here are those
two rolls' stored recipes, and the controls are the shapes that fix each defect. The second
half pins what "reporting-only" means in this loop: a warning-severity row never missions
a correction, never enters the verdict ledger, never keys a correction signature, and never
makes a task's failure category read executed-and-failed on its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.handlers.cycle.base import _framework_injected_criteria
from squadops.cycles.acceptance_check_spec import (
    CHECK_CONTAINER_PACKAGING,
    CHECK_SPECS,
    CHECK_UNDEFINED_NAMES,
    framework_file_scoped_checks,
    framework_recipe_scoped_checks,
    is_container_recipe,
)
from squadops.cycles.acceptance_checks import get_check
from squadops.cycles.container_packaging import (
    FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE,
    FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
    FINDING_NPM_CI_WITHOUT_LOCKFILE,
    packaging_findings,
    parse_dockerfile,
)
from squadops.cycles.correction_signature import failure_signature
from squadops.cycles.failure_evidence import FailureEvidenceCategory, derive_failure_category
from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.verification_integrity import (
    ResultStatus,
    RunVerdict,
    aggregate_verification,
)
from squadops.cycles.verification_normalize import normalize_task_checks, row_is_blocking_failure

pytestmark = [pytest.mark.domain_contracts]

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _roll(name: str):
    """A stored roll's recipe, its emitted file list, and a reader over its stored files."""
    tree = [
        line.strip()
        for line in (FIXTURES / f"{name}-emitted-files.txt").read_text().splitlines()
        if line.strip()
    ]

    def read(rel: str) -> str | None:
        stored = FIXTURES / f"{name}-{Path(rel).name}"
        return stored.read_text() if stored.exists() else None

    return (FIXTURES / f"{name}-Dockerfile").read_text(), tree, read


def _codes(findings) -> list[tuple[int, str]]:
    return [(f["line"], f["finding"]) for f in findings]


# ---------------------------------------------------------------------------
# The replays
# ---------------------------------------------------------------------------


def test_pf38_yields_exactly_the_three_defects_the_issue_reproduced():
    """The roll #598 was filed from: `npm ci` behind a lockfile glob nothing matches (line 8),
    dist-packages copied off python:3.11-slim (line 39), the server block in conf.d under
    apt's default site (line 49). Bug caught: any of the three going unread, or a fourth
    invented from a correct line."""
    text, tree, read = _roll("pf-38")
    findings = packaging_findings(text, "Dockerfile", tree, read)
    assert _codes(findings) == [
        (8, FINDING_NPM_CI_WITHOUT_LOCKFILE),
        (39, FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE),
        (49, FINDING_NGINX_DEFAULT_SITE_UNREMOVED),
    ]
    by_code = {f["finding"]: f["message"] for f in findings}
    assert "no package-lock.json" in by_code[FINDING_NPM_CI_WITHOUT_LOCKFILE]
    assert (
        "python:3.11-slim installs to site-packages"
        in by_code[FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE]
    )
    assert "(line 31)" in by_code[FINDING_NGINX_DEFAULT_SITE_UNREMOVED]
    assert "start.sh does not remove it" in by_code[FINDING_NGINX_DEFAULT_SITE_UNREMOVED]


def test_pf39_is_told_apart_from_pf38():
    """The owner's second sample: identical seeds, the lockfile defect worse (no glob at all,
    line 5), site-packages correct this time, the nginx default still unremoved (line 33).
    Bug caught: a check that pattern-matches "a React Dockerfile" and reports the same three
    every time — the defects move per roll, and the record must say which were drawn."""
    text, tree, read = _roll("pf-39")
    findings = packaging_findings(text, "Dockerfile", tree, read)
    assert _codes(findings) == [
        (5, FINDING_NPM_CI_WITHOUT_LOCKFILE),
        (33, FINDING_NGINX_DEFAULT_SITE_UNREMOVED),
    ]


# ---------------------------------------------------------------------------
# The controls — each defect's remedy clears exactly that finding
# ---------------------------------------------------------------------------


def _pf38_with(replacements: dict[str, str], extra_files: tuple[str, ...] = ()):
    text, tree, read = _roll("pf-38")
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new)
    return packaging_findings(text, "Dockerfile", [*tree, *extra_files], read)


@pytest.mark.parametrize(
    "replacements, extra_files, cleared",
    [
        # the glob matches an emitted lockfile
        ({}, ("frontend/package-lock.json",), FINDING_NPM_CI_WITHOUT_LOCKFILE),
        # a fallback the 1.7.0 gating roll wrote: `npm ci || npm install`
        ({"RUN npm ci": "RUN npm ci || npm install"}, (), FINDING_NPM_CI_WITHOUT_LOCKFILE),
        # `npm install` never needs the lockfile
        ({"RUN npm ci": "RUN npm install"}, (), FINDING_NPM_CI_WITHOUT_LOCKFILE),
        # the official image's real layout
        (
            {"/usr/local/lib/python3.11/dist-packages": "/usr/local/lib/python3.11/site-packages"},
            (),
            FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE,
        ),
        # the default site removed in the recipe
        (
            {
                "COPY nginx.conf /etc/nginx/conf.d/default.conf": (
                    "COPY nginx.conf /etc/nginx/conf.d/default.conf\n"
                    "RUN rm -f /etc/nginx/sites-enabled/default"
                )
            },
            (),
            FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
        ),
        # the main config replaced by one that includes no sites-enabled (pf-38's nginx.conf
        # is a bare server block — read as the replacement here, it has no such include)
        (
            {
                "COPY nginx.conf /etc/nginx/conf.d/default.conf": "COPY nginx.conf /etc/nginx/nginx.conf"
            },
            (),
            FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
        ),
    ],
    ids=[
        "lockfile-emitted",
        "ci-or-install",
        "npm-install",
        "site-packages",
        "rm-default",
        "main-conf",
    ],
)
def test_each_remedy_clears_its_own_finding_and_no_other(replacements, extra_files, cleared):
    """Bug caught: a remedy clearing a finding it did not address (a check keyed on the
    wrong fact), or leaving its own in place (a remedy the check cannot recognise)."""
    findings = _pf38_with(replacements, extra_files)
    codes = {f["finding"] for f in findings}
    assert cleared not in codes
    assert codes == {
        FINDING_NPM_CI_WITHOUT_LOCKFILE,
        FINDING_DIST_PACKAGES_ON_PYTHON_IMAGE,
        FINDING_NGINX_DEFAULT_SITE_UNREMOVED,
    } - {cleared}


def test_lockfile_in_the_tree_that_no_copy_brings_is_named_as_such():
    """Two different repairs: emit the lockfile, or copy the one that exists. The message
    must say which — pf-39's recipe copies only package.json, so a lockfile beside it would
    still not reach `npm ci`."""
    text, tree, read = _roll("pf-39")
    findings = packaging_findings(text, "Dockerfile", [*tree, "frontend/package-lock.json"], read)
    lock = [f for f in findings if f["finding"] == FINDING_NPM_CI_WITHOUT_LOCKFILE]
    assert len(lock) == 1
    assert "has frontend/package-lock.json but no COPY before this line" in lock[0]["message"]


def test_entry_script_removing_the_default_site_counts():
    """The remedy the issue applied by hand (`rm ... && nginx -s reload`) lives naturally in
    start.sh, which the recipe runs; the check reads the script it resolves from ENTRYPOINT."""
    text, tree, _read = _roll("pf-38")

    def read(rel: str) -> str | None:
        if Path(rel).name == "start.sh":
            return "#!/bin/sh\nrm -f /etc/nginx/sites-enabled/default\nnginx -g 'daemon off;'\n"
        return _read(rel)

    codes = {f["finding"] for f in packaging_findings(text, "Dockerfile", tree, read)}
    assert FINDING_NGINX_DEFAULT_SITE_UNREMOVED not in codes


def test_nginx_provenance_follows_a_copy_of_etc_nginx_from_the_installing_stage():
    """The 1.7.0 gating roll's shape (`cyc_cb49b16c2fa6`): nginx apt-installed and configured
    in a middle stage, `/etc/nginx` copied whole into the final one. The default site travels
    with the copy, so the finding must follow the provenance, not only the final stage."""
    recipe = (
        "FROM python:3.11-slim AS backend\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends nginx\n"
        "COPY nginx.conf /etc/nginx/conf.d/default.conf\n"
        "FROM python:3.11-slim AS final\n"
        "COPY --from=backend /etc/nginx /etc/nginx\n"
        'CMD ["./start.sh"]\n'
    )
    findings = packaging_findings(recipe, "Dockerfile", ["nginx.conf", "start.sh"], lambda _p: "")
    assert _codes(findings) == [(3, FINDING_NGINX_DEFAULT_SITE_UNREMOVED)]


def test_dist_packages_off_a_non_python_stage_is_not_flagged():
    """The fact is the official image's layout, not the path: a Debian-based stage that
    installed system python really does have dist-packages."""
    recipe = (
        "FROM debian:bookworm AS deps\n"
        "RUN apt-get install -y python3-fastapi\n"
        "FROM debian:bookworm\n"
        "COPY --from=deps /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages\n"
    )
    assert packaging_findings(recipe, "Dockerfile", [], lambda _p: None) == []


def test_continuation_lines_keep_the_instructions_first_line():
    """pf-38's apt-get spans four lines; the finding names line 31, where it starts."""
    text, _tree, _read = _roll("pf-38")
    stages = parse_dockerfile(text)
    run_lines = [ins.line for s in stages for ins in s.instructions if ins.keyword == "RUN"]
    assert 31 in run_lines
    final = stages[-1]
    apt = next(ins for ins in final.instructions if ins.line == 31)
    assert "nginx" in apt.args and "curl" in apt.args


# ---------------------------------------------------------------------------
# The evaluator and the injection
# ---------------------------------------------------------------------------


async def test_evaluator_banks_the_findings_on_the_outcome(tmp_path: Path):
    """The check row's `actual` is what the per-round record reads; the findings ride it
    whole, with file and line, and the reason names the codes."""
    text, tree, read = _roll("pf-38")
    (tmp_path / "Dockerfile").write_text(text)
    for rel in tree:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(read(rel) or "")
    outcome = await get_check(CHECK_CONTAINER_PACKAGING).evaluate(
        {"file": "Dockerfile"}, tmp_path, stack="fastapi"
    )
    assert outcome.status == ResultStatus.FAILED
    assert outcome.reason == (
        "3 packaging finding(s): debian_nginx_default_site_unremoved, "
        "dist_packages_on_official_python_image, npm_ci_without_lockfile"
    )
    assert [(f["file"], f["line"]) for f in outcome.actual["findings"]] == [
        ("Dockerfile", 8),
        ("Dockerfile", 39),
        ("Dockerfile", 49),
    ]


async def test_evaluator_passes_a_clean_recipe_with_an_empty_findings_list(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM node:20-alpine\nCOPY . .\nRUN npm install\n")
    outcome = await get_check(CHECK_CONTAINER_PACKAGING).evaluate(
        {"file": "Dockerfile"}, tmp_path, stack=None
    )
    assert outcome.status == ResultStatus.PASSED
    assert outcome.actual == {"file": "Dockerfile", "findings": []}


async def test_evaluator_fails_on_a_missing_recipe_rather_than_passing(tmp_path: Path):
    outcome = await get_check(CHECK_CONTAINER_PACKAGING).evaluate(
        {"file": "Dockerfile"}, tmp_path, stack=None
    )
    assert outcome.status == ResultStatus.FAILED
    assert outcome.reason == "file_not_found"


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Dockerfile", True),
        ("deploy/Dockerfile", True),
        ("Dockerfile.frontend", True),
        ("Dockerfile.md", True),
        ("docker-compose.yaml", False),
        ("backend/main.py", False),
        ("DockerfileNotes", False),
    ],
)
def test_the_recipe_predicate(name, expected):
    assert is_container_recipe(name) is expected


def test_injection_is_recipe_scoped_and_warning_severity():
    """Bug caught (and hit while building this): the seam's local copy of the file-scoped
    rule injected the check on every artifact of every emission, and twice on the recipe.
    The check reaches only the recipe, once, at the spec's warning severity; the language
    checks still reach the Python file and nothing else."""
    artifacts = [
        {"name": "Dockerfile", "content": "FROM x"},
        {"name": "backend/main.py", "content": ""},
        {"name": "nginx.conf", "content": ""},
    ]
    injected = _framework_injected_criteria(artifacts, ())
    rows = sorted((c.check, c.params["file"], c.severity) for c in injected)
    assert (CHECK_CONTAINER_PACKAGING, "Dockerfile", "warning") in rows
    assert [r for r in rows if r[0] == CHECK_CONTAINER_PACKAGING] == [
        (CHECK_CONTAINER_PACKAGING, "Dockerfile", "warning")
    ]
    assert (CHECK_UNDEFINED_NAMES, "backend/main.py", "error") in rows
    assert not [r for r in rows if r[1] == "nginx.conf"]


def test_an_authored_row_for_the_recipe_wins_over_the_injection():
    authored = (TypedCheck(check=CHECK_CONTAINER_PACKAGING, params={"file": "Dockerfile"}),)
    injected = _framework_injected_criteria([{"name": "Dockerfile", "content": ""}], authored)
    assert [c.check for c in injected] == []


def test_the_two_scoping_predicates_partition_the_injected_file_checks():
    """One module answers both questions. Bug caught: a check landing in both sets (double
    injection) or in neither (silently never applied)."""
    recipe = set(framework_recipe_scoped_checks())
    by_suffix = set(framework_file_scoped_checks())
    assert recipe == {CHECK_CONTAINER_PACKAGING}
    assert recipe.isdisjoint(by_suffix)
    file_parametrised = {
        n
        for n, s in CHECK_SPECS.items()
        if s.framework_injected and s.required_params == frozenset({"file"})
    }
    assert recipe | by_suffix == file_parametrised


# ---------------------------------------------------------------------------
# Reporting-only, as the loop reads it
# ---------------------------------------------------------------------------


def _advisory_row(status: str = "failed") -> dict:
    """The row the typed-acceptance seam writes for a warning-severity failure: RC-9
    derives `passed` from severity × status, so this reads `passed: True`."""
    return {
        "check": f"acceptance:{CHECK_CONTAINER_PACKAGING}",
        "severity": "warning",
        "params": {"file": "Dockerfile"},
        "status": status,
        "actual": {"findings": [{"finding": FINDING_NPM_CI_WITHOUT_LOCKFILE, "line": 8}]},
        "reason": "1 packaging finding(s): npm_ci_without_lockfile",
        "passed": True,
        "evidence_gap": False,
        "task_index": 3,
        "check_index": 0,
        "criterion_id": None,
    }


def _blocking_row(status: str = "failed") -> dict:
    return {
        "check": f"acceptance:{CHECK_UNDEFINED_NAMES}",
        "severity": "error",
        "params": {"file": "backend/routes.py"},
        "status": status,
        "actual": {},
        "reason": "undefined name 'x'",
        "passed": False,
        "evidence_gap": False,
        "task_index": 3,
        "check_index": 1,
        "criterion_id": None,
    }


@pytest.mark.parametrize(
    "row, expected",
    [
        (_advisory_row("failed"), False),
        (_advisory_row("error"), False),
        (_blocking_row("failed"), True),
        (_blocking_row("error"), True),
        ({"check": "x", "passed": True, "status": "passed"}, False),
        # rows with no `passed` at all keep the status reading they always had
        ({"check": "x", "status": "failed"}, True),
        ({"check": "x", "status": "error"}, True),
        ({"check": "x", "status": "skipped"}, False),
    ],
    ids=[
        "adv-failed",
        "adv-error",
        "blk-failed",
        "blk-error",
        "passed",
        "bare-failed",
        "bare-error",
        "bare-skipped",
    ],
)
def test_the_one_predicate_the_three_readers_share(row, expected):
    assert row_is_blocking_failure(row) is expected


def test_an_advisory_failure_never_reaches_the_verdict_ledger():
    """The bug this guards: the ledger read a typed row's status verbatim and §6.2 rejects on
    any executed-and-failed — the first warning-severity row ever produced would have
    rejected an otherwise accepted run. The advisory row is not a ledger input; the blocking
    one beside it still is."""
    outputs = {"validation_result": {"checks": [_advisory_row(), _blocking_row("passed")]}}
    results = normalize_task_checks(outputs, subject="task-3")
    assert [(r.check_id, r.status) for r in results] == [
        (f"acceptance:{CHECK_UNDEFINED_NAMES}", ResultStatus.PASSED)
    ]
    assert aggregate_verification(results).verdict == RunVerdict.ACCEPTED


def test_an_advisory_failure_does_not_key_the_correction_signature():
    """A chain's identity is the failure it is correcting; the reporting-only row is not it.
    Bug caught: two rounds with the same real failure and a different packaging finding
    reading as movement, or a plan-defect termination keyed on packaging."""
    evidence = {"validation_result": {"checks": [_advisory_row(), _blocking_row()]}}
    signature = failure_signature(evidence)
    assert signature is not None
    assert {check for check, _subject, _reason in signature} == {
        f"acceptance:{CHECK_UNDEFINED_NAMES}"
    }
    advisory_only = {"validation_result": {"checks": [_advisory_row()]}}
    assert failure_signature(advisory_only) is None


def test_an_advisory_failure_alone_is_not_executed_and_failed():
    """The category routes the repair; a task whose only failed-status row is advisory
    has no executed failure to repair."""
    advisory_only = {"validation_result": {"checks": [_advisory_row()]}}
    assert derive_failure_category(advisory_only) == FailureEvidenceCategory.EVIDENCE_UNAVAILABLE
    with_blocking = {"validation_result": {"checks": [_advisory_row(), _blocking_row()]}}
    assert derive_failure_category(with_blocking) == FailureEvidenceCategory.EXECUTED_AND_FAILED


def test_the_spec_declares_the_reporting_only_governance():
    """Pins the four facts the readers rely on. Bug caught: promotion to blocking by a
    one-field edit that forgets the signature and outcome axes (plan §6 makes promotion a
    deliberate call, not a default)."""
    spec = CHECK_SPECS[CHECK_CONTAINER_PACKAGING]
    assert spec.blocking_default == "warning"
    assert spec.signature_participation is False
    assert spec.outcome_contribution is False
    assert spec.replayable is True
    assert spec.applicable_extensions == frozenset()
