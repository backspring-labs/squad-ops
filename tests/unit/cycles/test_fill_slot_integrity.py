"""Fill-slot decorator integrity (pf-40).

The scaffold seeded ``@router.post("/runs", response_model=RunEvent, status_code=201)``
and the dev agent's emission replaced it with ``@router.post("/runs")``. POST /runs then
answered 200 against a contract pinning 201 — the same failure that rejected pf-39, on the
deploy that had just fixed the scaffold to emit 201. Emitting the right skeleton is not
enough; something has to hold it there.

These cases are written against the shapes actually observed in that roll.
"""

from __future__ import annotations

import ast

import pytest

from squadops.cycles.fill_slot_integrity import (
    divergence_summary,
    restore_declared_status_codes,
)

pytestmark = [pytest.mark.domain_cycles]

# The scaffold's seed, as expand() emits it.
SEED = '''"""API route stubs — scaffold-owned signatures, fill-only bodies."""

from fastapi import APIRouter, HTTPException

from .models import RunEvent, RunEventCreate

router = APIRouter()


@router.get("/runs", response_model=list[RunEvent])
def list_runs():
    """list runs — TODO: implement (scaffold stub)."""
    raise HTTPException(status_code=501, detail="not implemented")


@router.post("/runs", response_model=RunEvent, status_code=201)
def create_run(payload: RunEventCreate):
    """create run — TODO: implement (scaffold stub)."""
    raise HTTPException(status_code=501, detail="not implemented")


@router.post("/runs/{run_id}/join", response_model=RunEvent)
def join_run(run_id: str, payload: ParticipantName):
    """join run — TODO: implement (scaffold stub)."""
    raise HTTPException(status_code=501, detail="not implemented")
'''

# pf-40's actual emission: status_code gone, response_model gone, handler and parameter
# renamed.
PF40_EMISSION = '''from fastapi import APIRouter

from .models import RunEventCreate
from .store import create_run

router = APIRouter()


@router.get("/runs")
def list_runs_endpoint():
    return list_all()


@router.post("/runs")
def create_run_endpoint(data: RunEventCreate):
    """Create a new run event."""
    return create_run(title=data.title, datetime=data.datetime, location=data.location)


@router.post("/runs/{id}/join")
def join_run_endpoint(id: str, body: ParticipantName):
    return join(id, body.name)
'''


class TestStatusCodeRestoration:
    def test_dropped_status_code_is_put_back(self):
        """The pf-40 defect itself. Without this the app answers 200 and vc-probe-runs
        rejects the run."""
        corrected, divergences = restore_declared_status_codes(SEED, PF40_EMISSION)

        assert '@router.post("/runs", status_code=201)' in corrected
        restored = [d for d in divergences if d.restored]
        assert len(restored) == 1
        assert restored[0].path == "/runs"
        assert "status_code=201" in restored[0].detail

    def test_restoration_preserves_the_producer_body(self):
        """Enforcement must not cost the implementation — the body, its renamed parameter,
        and the producer's imports all survive untouched."""
        corrected, _ = restore_declared_status_codes(SEED, PF40_EMISSION)

        assert "def create_run_endpoint(data: RunEventCreate):" in corrected
        assert "title=data.title, datetime=data.datetime, location=data.location" in corrected
        assert "from .store import create_run" in corrected

    def test_corrected_source_still_parses(self):
        import ast

        corrected, _ = restore_declared_status_codes(SEED, PF40_EMISSION)
        ast.parse(corrected)  # a splice landing in the wrong column would raise here

    def test_renamed_path_parameter_still_matches(self):
        """The producer wrote ``{id}`` where the scaffold declared ``{run_id}`` — the
        pf-31 class. Matching is by normalized path, so the status code is still enforced
        rather than silently skipped because the key did not match."""
        seed = '@router.post("/runs/{run_id}/x", status_code=201)\ndef f(run_id: str):\n    pass\n'
        emitted = '@router.post("/runs/{id}/x")\ndef f(id: str):\n    pass\n'

        corrected, divergences = restore_declared_status_codes(seed, emitted)

        assert "status_code=201" in corrected
        assert any(d.restored for d in divergences)

    def test_compliant_emission_is_byte_identical(self):
        """A producer that kept the decorator must pass through untouched — otherwise
        enforcement would rewrite every compliant roll and mask its own no-op."""
        emitted = (
            '@router.post("/runs", response_model=RunEvent, status_code=201)\n'
            "def create_run(payload: RunEventCreate):\n    return {}\n"
        )
        corrected, divergences = restore_declared_status_codes(SEED, emitted)

        assert corrected == emitted
        assert [d for d in divergences if d.restored] == []

    def test_wrong_status_code_is_corrected_not_only_absent_one(self):
        """A producer that declared 200 explicitly is as broken as one that declared
        nothing; only checking for absence would let this through."""
        emitted = (
            '@router.post("/runs", status_code=200)\ndef create_run(payload):\n    return {}\n'
        )
        corrected, divergences = restore_declared_status_codes(SEED, emitted)

        assert "status_code=201" in corrected
        assert any("emitted as 200" in d.detail for d in divergences)


class TestReportedButNotRewritten:
    def test_response_model_and_renames_are_reported_unrestored(self):
        """These are real divergences but unsafe to rewrite — restoring the signature would
        leave the body referencing a parameter that no longer exists. They must surface as
        evidence rather than silently vanish."""
        _, divergences = restore_declared_status_codes(SEED, PF40_EMISSION)
        observed = {d.detail for d in divergences if not d.restored}

        assert any("response_model" in d for d in observed)
        assert any("create_run" in d and "create_run_endpoint" in d for d in observed)
        assert any("payload" in d and "data" in d for d in observed)

    def test_reported_divergences_do_not_alter_the_source(self):
        emitted = '@router.get("/runs")\ndef list_runs_endpoint():\n    return []\n'
        corrected, divergences = restore_declared_status_codes(SEED, emitted)

        # GET /runs declares response_model but no status_code — nothing to restore.
        assert corrected == emitted
        assert divergences and all(not d.restored for d in divergences)


class TestEdgeCases:
    def test_unparseable_emission_passes_through(self):
        """A syntax error is the test runner's failure to report. Raising here would turn a
        visible test failure into an opaque enforcement crash."""
        broken = '@router.post("/runs")\ndef create_run(  # truncated mid-signature\n'
        corrected, divergences = restore_declared_status_codes(SEED, broken)

        assert corrected == broken
        assert divergences == []

    def test_route_absent_from_the_scaffold_is_left_alone(self):
        """An endpoint the scaffold never declared is endpoint_defined's problem, not this
        module's — inventing a status code for it would be enforcement without a referent."""
        emitted = '@router.post("/invented")\ndef invented():\n    return {}\n'
        corrected, divergences = restore_declared_status_codes(SEED, emitted)

        assert corrected == emitted
        assert divergences == []

    def test_empty_seed_disables_enforcement(self):
        emitted = '@router.post("/runs")\ndef create_run(payload):\n    return {}\n'
        assert restore_declared_status_codes("", emitted) == (emitted, [])

    def test_summary_leads_with_restorations(self):
        _, divergences = restore_declared_status_codes(SEED, PF40_EMISSION)
        summary = divergence_summary(divergences)

        assert summary.startswith("restored POST /runs")
        assert "observed" in summary

    def test_summary_of_nothing_is_empty(self):
        assert divergence_summary([]) == ""


class TestEnforcementWiring:
    """The pure function is useless unless the enforcement seam actually calls it — pf-40's
    lesson is precisely that a correct component wired to nothing changes no outcome."""

    @staticmethod
    def _record_and_envelope(tmp_seed: str):
        from types import SimpleNamespace

        from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord, FrozenArtifact

        record = BoundScaffoldRecord(
            run_id="run_x",
            attempt_id="run_x",
            stack="fullstack_fastapi_react",
            manifest_hash="m",
            contract_hash="c",
            expander_id="fullstack_fastapi_react",
            created_at="2026-01-01T00:00:00+00:00",
            frozen=(),
            fill_slots=("backend/routes.py",),
            fill_seeds=(FrozenArtifact(path="backend/routes.py", sha256="s", content=tmp_seed),),
        )
        envelope = SimpleNamespace(task_id="t1", task_type="development.develop")
        return record, envelope

    def test_enforcement_restores_through_the_seam(self):
        from squadops.cycles.scaffold_enforcement import enforce_frozen_ownership

        record, envelope = self._record_and_envelope(SEED)
        artifacts = [{"name": "backend/routes.py", "content": PF40_EMISSION}]

        enforced, _ = enforce_frozen_ownership(artifacts, record, envelope)

        assert '@router.post("/runs", status_code=201)' in enforced[0]["content"]

    def test_non_slot_artifacts_are_untouched(self):
        from squadops.cycles.scaffold_enforcement import enforce_frozen_ownership

        record, envelope = self._record_and_envelope(SEED)
        artifacts = [{"name": "backend/tests/test_x.py", "content": PF40_EMISSION}]

        enforced, _ = enforce_frozen_ownership(artifacts, record, envelope)

        assert enforced[0]["content"] == PF40_EMISSION

    def test_record_without_seeds_enforces_nothing(self):
        """Records bound before ``fill_seeds`` existed must degrade to today's behaviour
        rather than crashing an in-flight run."""
        from squadops.cycles.scaffold_enforcement import enforce_frozen_ownership

        record, envelope = self._record_and_envelope(SEED)
        record = type(record)(**{**record.__dict__, "fill_seeds": ()})
        artifacts = [{"name": "backend/routes.py", "content": PF40_EMISSION}]

        enforced, _ = enforce_frozen_ownership(artifacts, record, envelope)

        assert enforced[0]["content"] == PF40_EMISSION

    def test_bound_record_round_trips_fill_seeds(self):
        from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord

        record, _ = self._record_and_envelope(SEED)
        back = BoundScaffoldRecord.from_dict(record.to_dict())

        assert back.fill_seed_bytes("backend/routes.py") == SEED
        assert back.fill_seed_bytes("./backend/routes.py") == SEED  # normalized lookup
        assert back.fill_seed_bytes("backend/models.py") is None

    def test_build_bound_record_seeds_every_fill_slot(self):
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest, fill_slot_paths
        from squadops.cycles.bound_scaffold_record import build_bound_record

        path = (
            Path(__file__).resolve().parents[3]
            / "examples"
            / "03_group_run"
            / "interface_manifest.yaml"
        )
        manifest = InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))
        record = build_bound_record(
            manifest, run_id="r", attempt_id="r", created_at="2026-01-01T00:00:00+00:00"
        )

        for slot in fill_slot_paths(manifest):
            assert record.fill_seed_bytes(slot), f"no seed pinned for fill slot {slot}"
        # the seed is the real scaffold stub, carrying the status code the producer must keep
        assert "status_code=201" in record.fill_seed_bytes("backend/routes.py")


class TestRouterPrefixRestoration:
    """pf-41's actual 404. The scaffold seeded `router = APIRouter()`; the dev agent
    emitted `router = APIRouter(prefix="/api")`. Every route re-homed under a second
    /api, so a perfectly healthy app answered 404 to `POST /runs` — its own contract.

    The agent's reasoning was sound: the scaffold's frontend calls /api/... so it made
    the backend match. It could not see that the proxy strips that prefix, because the
    rewrite lives in vite.config.js, a frozen file it never reads.
    """

    SEED = (
        '"""stub."""\n\nfrom fastapi import APIRouter\n\nrouter = APIRouter()\n\n\n'
        '@router.post("/runs", status_code=201)\ndef create_run(payload):\n    return {}\n'
    )

    def test_prefix_is_stripped_back_to_the_scaffold_router(self):
        emitted = self.SEED.replace("APIRouter()", 'APIRouter(prefix="/api")')

        corrected, divergences = restore_declared_status_codes(self.SEED, emitted)

        assert "router = APIRouter()" in corrected
        assert 'prefix="/api"' not in corrected
        assert any(d.restored and d.path == "(router)" for d in divergences)

    def test_any_invented_prefix_is_stripped_not_just_api(self):
        """A repair tried `prefix="/runs"`, which would have doubled the path segment."""
        emitted = self.SEED.replace("APIRouter()", 'APIRouter(prefix="/runs", tags=["runs"])')

        corrected, _ = restore_declared_status_codes(self.SEED, emitted)

        assert "router = APIRouter()" in corrected

    def test_handler_bodies_survive(self):
        """Restoring the router must not disturb the implementation — the prefix decides
        where routes register, never what a body references."""
        emitted = self.SEED.replace("APIRouter()", 'APIRouter(prefix="/api")').replace(
            "return {}", "return {'id': 'x'}"
        )

        corrected, _ = restore_declared_status_codes(self.SEED, emitted)

        assert "return {'id': 'x'}" in corrected
        import ast

        ast.parse(corrected)

    def test_matching_router_is_untouched(self):
        """A compliant emission passes through byte-identical, so enforcement cannot mask
        its own no-op."""
        corrected, divergences = restore_declared_status_codes(self.SEED, self.SEED)

        assert corrected == self.SEED
        assert [d for d in divergences if d.path == "(router)"] == []

    def test_seed_without_a_router_enforces_nothing(self):
        emitted = 'router = APIRouter(prefix="/api")\n'
        assert restore_declared_status_codes("x = 1\n", emitted) == (emitted, [])

    def test_replays_the_real_pf41_emission(self):
        """The load-bearing case: the actual stored artifacts from the roll that failed."""
        from pathlib import Path

        base = (
            Path(__file__).resolve().parents[3]
            / "data/artifacts/group_run/cyc_bff6a0abfa32/run_861f68199132"
        )
        seed_f = base / "art_acc468c1494c/backend/routes.py"
        emitted_f = base / "art_dfb9d9bc6f5d/backend/routes.py"
        if not (seed_f.exists() and emitted_f.exists()):
            import pytest

            pytest.skip("pf-41 artifacts not present in this checkout")

        corrected, _ = restore_declared_status_codes(seed_f.read_text(), emitted_f.read_text())

        assert "router = APIRouter()" in corrected
        assert "prefix=" not in corrected.split("@router")[0]
        assert "status_code=201" in corrected  # the #602 restoration still holds


class TestRouterPrefixRestorationKeepsTheRegisteredRoutes:
    """#1351: the prefix and the decorated paths are one statement of where the routes
    live. ``cyc_375bdea6e140``'s dev emitted ``APIRouter(prefix="/runs")`` with
    ``post("")`` and ``post("/{run_id}/join")`` — a coherent encoding of the scaffold's
    own routes. Putting back the router line alone produced ``APIRouter()`` +
    ``post("")``, which FastAPI refuses at ``include_router`` (``Prefix and path cannot
    be both empty``): the app could not import, the qa suite failed at collection, the
    boot audit failed, and the repair — the same idiom — was restored the same way. A
    restore must never hand back a file that does not boot; the claim here is checked by
    booting the file."""

    SEED = (
        '"""stub."""\n\nfrom fastapi import APIRouter\n\nrouter = APIRouter()\n\n\n'
        '@router.post("/runs", status_code=201)\ndef create_run(payload: dict):\n    return {}\n\n\n'
        '@router.post("/runs/{run_id}/join")\ndef join_run(run_id: str, payload: dict):\n'
        "    return {}\n"
    )
    EMITTED = (
        '"""impl."""\n\nfrom fastapi import APIRouter\n\n'
        'router = APIRouter(prefix="/runs", tags=["runs"])\n\n\n'
        '@router.post("", status_code=201)\ndef create_run(payload: dict):\n'
        '    return {"id": 1}\n\n\n'
        '@router.post("/{run_id}/join")\ndef join_run(run_id: str, payload: dict):\n'
        '    return {"id": run_id}\n'
    )

    @staticmethod
    def _registered_paths(source: str, stubs: dict | None = None) -> set[str]:
        """What FastAPI registers when the file is imported — the boot itself."""
        from fastapi import FastAPI

        namespace: dict = dict(stubs or {})
        exec(compile(source, "<routes>", "exec"), namespace)  # noqa: S102
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.include_router(namespace["router"])
        return {r.path for r in app.routes if getattr(r, "methods", None)}

    def test_the_prefixed_paths_are_re_homed_and_the_file_boots_with_the_same_routes(self):
        corrected, divergences = restore_declared_status_codes(self.SEED, self.EMITTED)

        assert "router = APIRouter()" in corrected
        assert '@router.post("/runs", status_code=201)' in corrected
        assert '@router.post("/runs/{run_id}/join")' in corrected
        assert 'return {"id": 1}' in corrected  # bodies untouched
        assert (
            self._registered_paths(corrected)
            == self._registered_paths(self.EMITTED)
            == {"/runs", "/runs/{run_id}/join"}
        )
        (router_div,) = [d for d in divergences if d.path == "(router)"]
        assert router_div.restored
        assert "2 route path(s) re-homed" in router_div.detail

    def test_the_amputated_shape_is_what_fastapi_refuses(self):
        """The paired control: the file the old restore produced does not boot."""
        from fastapi.exceptions import FastAPIError

        amputated = self.EMITTED.replace('APIRouter(prefix="/runs", tags=["runs"])', "APIRouter()")
        with pytest.raises(FastAPIError, match="Prefix and path cannot be both empty"):
            self._registered_paths(amputated)

    def test_full_paths_under_a_spurious_prefix_are_still_stripped_not_doubled(self):
        """pf-41's shape is unchanged: the bare paths already match the scaffold, so the
        prefix alone is the mistake and goes; nothing is re-homed."""
        emitted = self.SEED.replace("APIRouter()", 'APIRouter(prefix="/api")')

        corrected, divergences = restore_declared_status_codes(self.SEED, emitted)

        assert "/api/runs" not in corrected
        assert self._registered_paths(corrected) == {"/runs", "/runs/{run_id}/join"}
        (router_div,) = [d for d in divergences if d.path == "(router)"]
        assert router_div.restored
        assert "re-homed" not in router_div.detail

    def test_an_empty_path_under_a_prefix_that_matches_nothing_abandons_the_restore(self):
        """Neither reading matches the scaffold and stripping would leave ``post("")`` on
        a bare router: the producer's bytes boot, ours would not, so nothing is rewritten
        and the record says why (the wrong routes are ``endpoint_defined``'s finding)."""
        emitted = self.EMITTED.replace('prefix="/runs"', 'prefix="/api/v9"')

        corrected, divergences = restore_declared_status_codes(self.SEED, emitted)

        assert corrected == emitted
        (router_div,) = [d for d in divergences if d.path == "(router)"]
        assert not router_div.restored
        assert "restore abandoned" in router_div.detail
        assert self._registered_paths(corrected) == {"/api/v9", "/api/v9/{run_id}/join"}

    def test_replays_the_real_1351_emission(self):
        """The load-bearing case: the dev's actual repair emission from
        ``cyc_375bdea6e140`` against the seeded ``routes.py``, pinned as fixtures. The
        app's own modules are stubbed so the file can be booted here."""
        import re
        from pathlib import Path

        from pydantic import BaseModel

        fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
        seed = (fixtures / "1-7-3-chain-diagnostic-routes-seed.py.txt").read_text()
        emitted = (fixtures / "1-7-3-chain-diagnostic-routes-prefixed.py.txt").read_text()

        corrected, divergences = restore_declared_status_codes(seed, emitted)

        assert "router = APIRouter()" in corrected
        assert '("")' not in corrected
        assert "status_code=201" in corrected

        class _Model(BaseModel):
            pass

        stubs = {name: _Model for name in ("Run", "RunSummary", "RunCreate", "ParticipantAction")}
        stubs.update({"ApiError": Exception, "run_store": {}, "run_summary_store": {}})
        without_app_imports = re.compile(r"^from \.\w+ import .*\n", re.M)
        booted = self._registered_paths(without_app_imports.sub("", corrected), stubs)
        declared = self._registered_paths(without_app_imports.sub("", seed), stubs)
        assert (
            booted
            == declared
            == {
                "/runs",
                "/runs/{run_id}",
                "/runs/{run_id}/join",
                "/runs/{run_id}/leave",
            }
        )
        (router_div,) = [d for d in divergences if d.path == "(router)"]
        assert "5 route path(s) re-homed" in router_div.detail


class TestStatusCodeKeywordAlreadyPresent:
    """pf-44: the restorer must never append a keyword the decorator already carries.

    The dev agent wrote ``status_code=status.HTTP_201_CREATED`` — correct, idiomatic, and
    exactly what the scaffold asked for, just not spelled as an int literal. The restorer
    read "no literal" as "absent", appended its own, and produced a duplicate keyword
    argument: a SyntaxError, so routes.py would not import, so pytest aborted at collection
    with exit 4, so nothing was tested and every repair regenerated the same corruption.
    """

    SEED = (
        '@router.post("/runs", response_model=RunEvent, status_code=201)\n'
        "def create_run(payload: RunEventCreate):\n"
        "    ...\n"
    )

    def _emitted(self, decorator: str) -> str:
        return f"{decorator}\ndef create_run(payload):\n    return None\n"

    def test_symbolic_status_code_is_left_alone_and_stays_parseable(self):
        emitted = self._emitted('@router.post("/runs", status_code=status.HTTP_201_CREATED)')

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)  # the actual regression: this used to raise
        assert out.count("status_code=") == 1
        assert "status.HTTP_201_CREATED" in out
        # HTTP_201_CREATED names the declared code — correct code, no "problem" row.
        # Divergence evidence feeds repair context; reporting right code invites churn.
        assert not [d for d in divs if "status_code" in d.detail]

    def test_symbolic_status_code_naming_a_different_code_is_reported(self):
        emitted = self._emitted('@router.post("/runs", status_code=status.HTTP_200_OK)')

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)
        assert "status.HTTP_200_OK" in out  # left as written, never rewritten
        status_divs = [d for d in divs if "status_code" in d.detail]
        assert len(status_divs) == 1
        assert status_divs[0].restored is False

    def test_wrong_literal_is_replaced_not_appended(self):
        emitted = self._emitted('@router.post("/runs", status_code=200)')

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)
        assert out.count("status_code=") == 1
        assert "status_code=201" in out
        assert "status_code=200" not in out
        assert [d.restored for d in divs if "status_code" in d.detail] == [True]

    def test_correct_literal_is_untouched(self):
        emitted = self._emitted('@router.post("/runs", status_code=201)')

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        assert out == emitted
        assert not [d for d in divs if "status_code" in d.detail]

    def test_absent_status_code_is_still_restored(self):
        """The original pf-40 behaviour must survive the fix."""
        emitted = self._emitted('@router.post("/runs")')

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)
        assert out.count("status_code=") == 1
        assert "status_code=201" in out
        assert [d.restored for d in divs if "status_code" in d.detail] == [True]

    def test_every_reconciled_form_stays_importable(self):
        """The invariant that actually matters: never emit unparseable source."""
        for decorator in (
            '@router.post("/runs")',
            '@router.post("/runs", status_code=201)',
            '@router.post("/runs", status_code=200)',
            '@router.post("/runs", status_code=status.HTTP_201_CREATED)',
            '@router.post("/runs", response_model=RunEvent, status_code=HTTPStatus.CREATED)',
            '@router.post("/runs", status_code=int("201"))',
        ):
            out, _ = restore_declared_status_codes(self.SEED, self._emitted(decorator))
            ast.parse(out)
            assert out.count("status_code=") <= 1, decorator


class TestMultiLineDecorators:
    """The insertion must survive real-world formatting, not only the single-line shape.

    Black formats a long decorator with one argument per line and a trailing comma. The
    comma-prefixed insertion landed right after that trailing comma — double comma,
    SyntaxError, unimportable module: the exact corruption class this module exists to
    never emit, through a shape the original tests never swept.
    """

    SEED = (
        '@router.post("/runs", response_model=RunEvent, status_code=201)\n'
        "def create_run(payload: RunEventCreate):\n"
        "    ...\n"
    )

    def test_trailing_comma_black_style(self):
        emitted = (
            "@router.post(\n"
            '    "/runs",\n'
            "    response_model=RunEvent,\n"
            ")\n"
            "def create_run(payload):\n"
            "    return None\n"
        )

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)  # the regression: double comma used to make this raise
        assert out.count("status_code=201") == 1
        assert [d.restored for d in divs if "status_code" in d.detail] == [True]

    def test_multi_line_without_trailing_comma(self):
        emitted = (
            "@router.post(\n"
            '    "/runs",\n'
            "    response_model=RunEvent\n"
            ")\n"
            "def create_run(payload):\n"
            "    return None\n"
        )

        out, _ = restore_declared_status_codes(self.SEED, emitted)

        ast.parse(out)
        assert out.count("status_code=201") == 1


class TestParseBackstop:
    """The invariant by construction: never hand back source that parses worse than
    what was received. If a splice ever produces unparseable output through a shape not
    yet enumerated, the whole restore is abandoned and the evidence says so."""

    SEED = '@router.post("/runs", status_code=201)\ndef create_run(payload):\n    ...\n'

    def test_unparseable_result_returns_producer_bytes_and_downgrades_evidence(self, monkeypatch):
        import squadops.cycles.fill_slot_integrity as fsi

        emitted = '@router.post("/runs")\ndef create_run(payload):\n    return None\n'
        monkeypatch.setattr(fsi, "_apply_splices", lambda source, splices: source + "\ndef (:")

        out, divs = restore_declared_status_codes(self.SEED, emitted)

        assert out == emitted  # producer bytes untouched
        status_divs = [d for d in divs if "status_code" in d.detail]
        assert len(status_divs) == 1
        assert status_divs[0].restored is False  # the evidence never claims a dead restore
        assert "restore abandoned" in status_divs[0].detail


# ---------------------------------------------------------------------------
# #730 D1 / #504: the reported surface as self-contained check params
# ---------------------------------------------------------------------------

from squadops.cycles.fill_slot_integrity import (  # noqa: E402
    declared_route_signatures,
    signature_divergences,
)

_SEED = """
from fastapi import APIRouter
router = APIRouter(prefix="/api/v1")

@router.post("/runs", response_model=RunEvent, status_code=201)
def create_run(payload):
    ...

@router.get("/runs/{run_id}")
def get_run(run_id):
    ...
"""


class TestDeclaredRouteSignatures:
    def test_extracts_the_reported_surface_only(self):
        """The params must carry exactly the reported-not-restored elements —
        status_code appearing here would fail emissions the SIP-0100 restore
        silently fixes (a check fighting its own enforcement layer)."""
        sigs = declared_route_signatures(_SEED)
        assert sigs == [
            {
                "route": "POST /runs",
                "function": "create_run",
                "params": ["payload"],
                "response_model": "RunEvent",
            },
            {"route": "GET /runs/{run_id}", "function": "get_run", "params": ["run_id"]},
        ]

    def test_routeless_or_unparseable_seed_declares_nothing(self):
        assert declared_route_signatures("x = 1\n") == []
        assert declared_route_signatures("def broken(:\n") == []


class TestSignatureDivergences:
    def test_compliant_emission_diverges_nowhere(self):
        assert signature_divergences(declared_route_signatures(_SEED), _SEED) == []

    def test_each_reported_element_produces_its_divergence(self):
        """The pf-40 drift classes, now costed: renamed handler, renamed
        params, dropped response_model — each named individually so the
        repair evidence says exactly what to put back."""
        emitted = _SEED.replace("create_run(payload)", "make_run(data)").replace(
            ", response_model=RunEvent", ""
        )
        details = signature_divergences(declared_route_signatures(_SEED), emitted)
        assert len(details) == 3
        assert any("response_model=RunEvent" in d and "absent" in d for d in details)
        assert any("'create_run'" in d and "'make_run'" in d for d in details)
        assert any("['payload']" in d and "['data']" in d for d in details)

    def test_renamed_path_parameter_still_matches_its_route(self):
        """The pf-31 rename class: `{run_id}` → `{id}` must still match the
        scaffold counterpart (normalized key) — and the path-param rename
        surfaces as a PARAMETER divergence, not a silent non-match."""
        emitted = _SEED.replace("{run_id}", "{id}").replace("get_run(run_id)", "get_run(id)")
        details = signature_divergences(declared_route_signatures(_SEED), emitted)
        assert len(details) == 1
        assert "['run_id']" in details[0] and "['id']" in details[0]

    def test_dropped_route_is_not_this_checks_failure(self):
        """A route absent from the emission is endpoint_defined's job —
        reporting it here would make one defect look like two."""
        emitted = "\n".join(
            line for line in _SEED.splitlines() if "get_run" not in line and "{run_id}" not in line
        )
        details = signature_divergences(declared_route_signatures(_SEED), emitted)
        assert details == []

    def test_unparseable_emission_diverges_nowhere(self):
        # The syntax gate owns broken emissions; the caller owns the skip.
        assert signature_divergences(declared_route_signatures(_SEED), "def broken(:\n") == []
