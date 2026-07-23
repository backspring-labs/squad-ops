---
template_id: request.qa_test.test_validate
version: "2"
required_variables:
  - prd
  - test_supplement
optional_variables:
  - validation_plan
  - source_files
  - prior_outputs
---
## Product Requirements Document

{{prd}}
{{validation_plan}}
{{source_files}}

## Test boundary — consume the scaffold-provided harness

If the scaffold provides a test harness (a root `conftest.py` exposing an application
fixture such as `client`), your tests MUST consume it. Do **NOT** import the application
entry module (e.g. `from backend.main import app`, `from app.main import app`, or
`importlib.import_module("backend.main")`) or construct the application test client
(e.g. `TestClient(app)`) yourself — the scaffold owns the application boundary, and a
suite that re-derives it is rejected by the `harness_boundary` check. Request the fixture
as a test argument (`def test_x(client): ...`); a pure unit test that needs no application
access needs no fixture.

{{test_supplement}}
{{prior_outputs}}
