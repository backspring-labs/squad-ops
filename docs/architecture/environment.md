# Environment variables read outside the config loader

Configuration arrives as `SQUADOPS__*` variables through the config loader
(`src/squadops/config/`), double underscores for nesting, and through its secrets provider for any
`secret://` value. Every other environment read in `src/` and `adapters/` is listed here, with its
reader and the reason it cannot come through config. `tests/unit/architecture/test_environment_inventory.py`
holds this list and the code equal in both directions (#1991): a read of a variable not listed
fails, and so does a row nobody reads.

## Named variables

| variable | read by | why not through config |
|---|---|---|
| `SQUADOPS_BASE_PATH` | `src/squadops/config/path_resolver.py` | where the config files are: the loader needs it before it can load them. `PathResolver` is its one reader |
| `SQUADOPS_PROFILE` | `src/squadops/config/loader.py` | which config profile to load |
| `SQUADOPS_STRICT_CONFIG` | `src/squadops/api/runtime/main.py` | how strictly the loader loads; read once, by the process entry point |
| `SQUADOPS__AGENT__ID` | `src/squadops/agents/entrypoint.py` | the agent's identity, which selects its instance configuration before the rest loads |
| `SQUADOPS_AGENT_ROLE` | `src/squadops/agents/entrypoint.py` | the process's role, read before config to build its prompt layers |
| `SQUADOPS_AGENT_SERVES_ROLES` | `src/squadops/agents/entrypoint.py` | the roles a generalist agent serves, beside its role |
| `LOG_LEVEL` | `src/squadops/agents/entrypoint.py` | the agent's logging, configured at import, before config loads |
| `MEMORY_DB_PATH` | `src/squadops/agents/entrypoint.py` | an operational default for the memory store's file (#333 names it intentional) |
| `HEARTBEAT_INTERVAL` | `src/squadops/agents/readiness.py` | the heartbeat period, read by the readiness probe outside the agent's config |
| `SQUADOPS_LOG_LEVEL` | `src/squadops/api/runtime/logging_setup.py` | the runtime API's logging, configured before config loads |
| `SQUADOPS_AUDIT_LOG_PATH` | `src/squadops/api/runtime/logging_setup.py` | the audit log's file, opened with the logging |
| `SQUADOPS_GIT_SHA` | `src/squadops/_version.py` | the build's commit, stamped into the image at build time |
| `SQUADOPS_RUN_ROOT` | `adapters/cycles/dispatched_flow_executor.py` | where a run's working tree is made; a temporary directory when unset |
| `SQUADOPS_RUNTIME_API_URL` | `adapters/observability/healthcheck_http.py` | where an agent finds the runtime API: service discovery, with the compose name as its default |
| `SQUADOPS_HOST` | `src/squadops/cli/commands/auth.py` | the CLI's server, on the operator's machine, which has no server config |
| `SQUADOPS_REALM` | `src/squadops/cli/commands/auth.py` | the CLI's identity realm, likewise |
| `XDG_CONFIG_HOME` | `src/squadops/cli/config.py`, `src/squadops/cli/auth.py` | where the CLI keeps its own files, by the operating system's convention |
| `PYTHONPATH` | `src/squadops/capabilities/handlers/test_runner.py` | extended for the generated suite's subprocess, not read as configuration |
| `POSTGRES_TEST_PASSWORD` | `src/squadops/bootstrap/setup/checks.py` | the doctor's check that the integration tests' database is isolated, run before any deploy config exists |

## Dynamic reads

A read whose variable name is computed. Each file is listed with what decides the name.

| file | the name read |
|---|---|
| `adapters/secrets/env.py` | the variable a `secret://` reference names: the environment secrets provider |
| `src/squadops/cli/config.py` | the CLI's token variable, `auth.token_env` in its config (`SQUADOPS_TOKEN` by default) |

## Removed by #1991

- **`LLM_MODEL`**: an agent's model was the instance's, then `LLM_MODEL`, then the config's. Nothing
  in the repository set it, and the deploy record cannot see it. The model is now the instance's,
  then `SQUADOPS__LLM__MODEL`.
- **`SQUADOPS__AUTH__KEYCLOAK__ADMIN__*` in the health checker**: a fallback to the raw
  environment when config held no admin credentials. It bypassed the secrets provider, so a
  `secret://` value would have been sent as the password. Without credentials in config, the
  Keycloak version reads "Unknown", as it already did.
- **`SQUADOPS_BASE_PATH` around `PathResolver`**: the agent's instance lookup and the check-tooling
  resolver read it directly. Both now ask `PathResolver`.
