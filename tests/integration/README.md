# Integration tests

These tests run against real services: Postgres, Redis and RabbitMQ, and for a few, LangFuse or an LLM
engine. They prove what the unit tests can't: that an adapter's SQL, queue topology or HTTP contract
holds against the service it talks to.

## The rules

1. **Use real services** - Avoid mocking external services in integration tests.
2. **Real Integration** - Tests use actual services, not mocks.

A test that needs a service it can't reach skips, and says which service. `validate_integration_tests.py`
fails a test file here that uses `unittest.mock` (`MOCK_PREVENTION.md`, `VALIDATION.md`).

## What's here

| Directory | What it exercises |
|---|---|
| `adapters/` | the RabbitMQ queue adapter, against a real broker |
| `auth/` | the Keycloak realm's hardening |
| `capabilities/` | the scaffold's walking skeleton, executed |
| `cycles/` | the Postgres registries: cycles, projects, campaigns, goal sets and their assessments, deploys, failure records and cycle ends. Also the framework smoke, the merge plan, and the pulse-check path end to end |
| `llm/` | the LLM port's conformance, live against an engine |
| `memory/` | the Postgres memory records, chat memory and cycle bindings |
| `outcomes/` | the Postgres ledger |
| `prompts/` | the filesystem prompt adapter |
| `runtime/` | the coordinator's transaction, and the embodiment store on Postgres |
| `scenarios/` | the Postgres scenario store |
| `telemetry/` | LangFuse: its contract, its integration and its resilience |

At the top level:
- `test_deployment_database_unreachable.py`: the test role can't reach the deployment database;
- `test_docker_build.py`: an agent image's build metadata;
- `test_agent_model_validation.py`: each agent's configured model is served.

`conftest.py` holds the fixtures and the service checks. `agent_manager.py` is the agent-container
helper. `check_services.py --verbose` says which services answer.

## How CI runs them

The `integration` job in `.github/workflows/ci.yml`:
1. **Starts** Postgres, Redis and RabbitMQ with `scripts/dev/ci_integration_services.sh`, which pulls each
   image from a mirror, with Docker Hub as the fallback (#2560).
2. **Provisions the test role** with `scripts/dev/ops/ensure_test_database.sh` (#1180). The suite then runs
   as `squadops_test`, which the deployment database refuses.
3. **Runs** `python -m pytest tests/integration -v --no-header -p no:cacheprovider`.
4. **Checks the count:** it fails when fewer tests ran than its floor, so a suite that executed nothing
   can't read green (#242).

It's a required check, except on a prose-only change (CLAUDE.md, "Required checks").

## Running them locally

`test_config.env` points the tests at the standard local ports as the test role, in its own database
(`squadops_test`). On a box with the deploy running, they reach its services that way and never its
deployment database.

```bash
SKIP_AGENT_CHECK=1 pytest tests/integration/cycles -v   # one directory
pytest tests/integration -v                              # the whole suite
```

`SKIP_AGENT_CHECK=1` skips the agent-container check, which the adapter tests don't need.
`SQUADOPS_REQUIRE_SERVICES=1` turns a missing service from a skip into a failure, as CI's run does.
