# Cutting a deploy over to the writable Project registry

SIP-0112 FR-03 (#2408). Before the cutover, `config/projects.yaml`, baked into the runtime API's
image, is the only Project authority. After it, the writable registry in Postgres is. Every reader
moves at once, because one setting selects the registry for all of them:
`SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER`, set in each deploy's `.env`. `docker-compose.yml`
passes it to the runtime API and the agents, and refuses to start without it.

| value | what it means |
|---|---|
| `config` | `config/projects.yaml` is the authority. Nothing can be registered. |
| `postgres` | The writable registry is the authority. Products can be registered. |
| `postgres_read_only` | The writable registry is still the authority, and every Project stays readable. Registration is refused. This is the rollback. |

## When

On the Spark, the 2.4 plan's D12 sets the timing: before the measurement window's deploy freezes,
only if IR-1 has passed on a deploy carrying both lanes; otherwise after the window. Never inside it
(G7). A deploy that has never set the key runs as before once it sets `config`.

## The cutover

1. **Before:** record what the deploy serves, to compare against afterwards.

   ```bash
   squadops --json projects list > before.json
   ```

2. **Set the key and restart the runtime API.** The agents carry the key too, but never read the
   registry.

   ```bash
   sed -i 's/^SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER=.*/SQUADOPS__CYCLES__PROJECT_REGISTRY_PROVIDER=postgres/' .env
   docker compose up -d --no-build --no-deps --wait runtime-api
   ```

   At start the runtime API seeds each project in `config/projects.yaml` that it hasn't seeded
   before, in the file's order, as `READY`. It logs `Seeded 5 project(s) from
   config/projects.yaml`. Then it checks:
   - **It refuses to start, naming the project,** if any config project is missing from the
     registry, or is held by a registered Project of the same ID. The alternative is serving that
     project as 404.
   - **It refuses to start, naming the migration,** if `project_records` doesn't exist because
     migration 1800 failed. The migration runner only logs a failure.
   - **It logs, and keeps,** any Project IDs that cycles or campaigns hold and the registry
     doesn't.

3. **After:** the list matches `before.json` field for field and in order, except `created_at`.
   That is now fixed at the seed time, where it used to be the process's start time. The added
   fields are `lifecycle_status`, `record_version`, `source`, `ownership` and
   `development_configuration_revision`. Each PRD's content (`GET /api/v1/projects/{id}/prd-content`)
   is unchanged.

A restart seeds nothing more. An edit to `config/projects.yaml` after the cutover is not applied:
the writable registry is the authority from then on.

## Rolling back

- **The normal rollback is the write gate:** set the key to `postgres_read_only` and restart the
  runtime API. Every Project, registered ones included, stays readable. A registration is refused
  with 409 `PROJECT_REGISTRY_READ_ONLY`.
- **Back to `config`** is allowed only while the registry holds no registered Project. If it holds
  one, the runtime API refuses to start and names every Project the config file would hide. Before
  any product is registered, going back to `config` is safe, and the seeded rows are simply not
  read.

Rolling the image back below the cutover's PR is a `config` rollback with extra steps: the old
image reads only `config/projects.yaml`. Don't do it once a product is registered.
