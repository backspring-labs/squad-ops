# Rotating a deploy's credentials

A deploy's credentials are its own (#2006). `infra/deploy_credentials.json` names every one, `.env`
holds each, and the `secrets/` files are derived from `.env`. A new deploy generates them at
bootstrap. A deploy that predates #2006 **adopted the values it already ran with**, which are the
values the repository commits. `squadops doctor <profile> --check credentials` names each one still
holding a committed value. This runbook replaces them on a running deploy.

**This is the owner's to run or approve** (the 2.1.0 plan's ruling on #2006: a backup first, and
the exact commands brought to the owner). Every command below is read before it runs.

Each service learns a credential in its own way, so a new value in `.env` reaches it by a different
step. The order matters: a database role's password changes before the services that use it
restart, and the Keycloak admin password changes before the realm sync signs in with it.

| credential | how the running service learns the new value |
|---|---|
| `POSTGRES_PASSWORD` | `ALTER ROLE squadops` (step 3), then every service recreated (step 8) |
| `POSTGRES_TEST_PASSWORD`, `KEYCLOAK_DB_PASSWORD`, `LANGFUSE_DB_PASSWORD` | `ensure_test_database.sh` sets each role from `.env` (step 3) |
| `RABBITMQ_PASSWORD` | `rabbitmqctl change_password` (step 4) |
| `KEYCLOAK_ADMIN_PASSWORD` | `kcadm.sh set-password`, signed in with the old one (step 5) |
| `SQUADOPS_AGENT_CLIENT_SECRET`, `SQUADOPS_RUNTIME_CLIENT_SECRET` | the realm sync sets each client's secret from `.env` (step 6) |
| `SQUADOPS_ADMIN_PASSWORD` | the realm sync sets `squadops-admin`'s password from `.env` in every synced realm (step 6, #2079). **It is how the owner and the scripts sign in:** after rotating it, `squadops login` takes the new value |
| `GRAFANA_ADMIN_PASSWORD` | `grafana cli admin reset-admin-password` (step 7) |
| `LANGFUSE_NEXTAUTH_SECRET`, `LANGFUSE_SALT` | compose recreates Langfuse with them (step 8). **A new `SALT` invalidates every Langfuse API key**: step 9 mints new ones |
| `LANGFUSE_ADMIN_PASSWORD` | the Langfuse UI user's password, changed in the UI (step 9) |
| `SQUADOPS_SANDBOX_SERVICE_TOKEN` | compose recreates the sandbox service with it (step 8) |

All commands run from the repository root.

## 0. Preconditions

- The box is idle: no run `running`, `queued` or `paused` in `cycle_runs`, and no campaign live.
- Main is green, and the deploy carries the #2006 change (`rebuild_and_deploy.sh` ran on it).

## 1. Write a backup

```bash
B=~/squadops-backups/pre-credential-rotation-$(date -u +%Y%m%dT%H%M%SZ); mkdir -m 700 -p "$B"
docker exec squadops-postgres pg_dumpall -U squadops > "$B/postgres.sql"    # squadops, keycloak, langfuse, the test DB
cp -p .env "$B/env" && cp -rp secrets "$B/secrets"
docker exec squadops-rabbitmq rabbitmqctl export_definitions /tmp/rabbitmq-definitions.json \
  && docker cp squadops-rabbitmq:/tmp/rabbitmq-definitions.json "$B/"
docker cp squadops-grafana:/var/lib/grafana/grafana.db "$B/"
ls -la "$B" && head -c 300 "$B/postgres.sql"
```

Read it back before going on: the dump is non-empty and starts with a `pg_dumpall` header, and the
`env` copy, the `secrets` folder, the RabbitMQ definitions and Grafana's database are there.
Keycloak's and Langfuse's data are in the same Postgres cluster, so the dump holds them.

## 2. New values into `.env`

```bash
python3 scripts/dev/ops/deploy_credentials.py rotate --dry-run          # names, never values
python3 scripts/dev/ops/deploy_credentials.py rotate                    # copies .env to .env.pre-rotation-<UTC> first
# or: rotate --keep LANGFUSE_SALT   (keep the salt and its API keys), rotate --only NAME …
OLD=$(ls -t .env.pre-rotation-* | head -1)
val() { grep "^$1=" "${2:-.env}" | tail -1 | cut -d= -f2-; }
python3 scripts/dev/ops/deploy_credentials.py ensure                    # secrets/ from the new .env
```

`rotate` changes `.env` only. Nothing running has the new values yet.

## 3. Postgres roles

```bash
printf "ALTER ROLE squadops PASSWORD :'pw';\n" \
  | docker exec -i squadops-postgres psql -U squadops -d squadops -v pw="$(val POSTGRES_PASSWORD)"
bash scripts/dev/ops/ensure_test_database.sh                            # squadops_test, keycloak, langfuse from .env
```

## 4. RabbitMQ

```bash
docker exec squadops-rabbitmq rabbitmqctl change_password squadops "$(val RABBITMQ_PASSWORD)"
```

## 5. Keycloak's admin

```bash
docker exec squadops-keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 \
  --realm master --user admin --password "$(val KEYCLOAK_ADMIN_PASSWORD "$OLD")"
docker exec squadops-keycloak /opt/keycloak/bin/kcadm.sh set-password -r master --username admin \
  --new-password "$(val KEYCLOAK_ADMIN_PASSWORD)"
```

## 6. The clients' secrets

```bash
python3 scripts/dev/ops/keycloak_realm_sync.py infra/auth/squadops-realm.json infra/auth/squadops-realm-local.json
```

Each client prints `secret set from .env`, and `squadops-admin` prints `password set from .env`
(#2079). It signs in with the new admin password from `secrets/keycloak_admin_password.txt`, which
step 2's `ensure` wrote. Then sign the CLI in with the new realm password:
`.venv/bin/squadops login -u squadops-admin -p "$(val SQUADOPS_ADMIN_PASSWORD)"`. The
verification-set driver and the release capture read it from `.env` themselves.

## 7. Grafana's admin

```bash
docker exec squadops-grafana grafana cli admin reset-admin-password "$(val GRAFANA_ADMIN_PASSWORD)"
```

## 8. Recreate every service that reads one

```bash
docker compose up -d                                                    # recreates what the new .env changes
docker compose up -d --force-recreate runtime-api max neo nat bob eve data han joi   # secrets are read at start
docker compose --profile sandbox up -d sandbox-service                  # when the sandbox profile is in use
```

## 9. Langfuse (if `LANGFUSE_SALT` was rotated)

The old API keys no longer verify. Sign in to the Langfuse UI (`http://localhost:3001`) as
`admin@squadops.local` with the old `LANGFUSE_ADMIN_PASSWORD` from `$OLD`, and:
- change the user's password to the new `LANGFUSE_ADMIN_PASSWORD`;
- create a new API key pair in the `squadops` project, and put it in `.env` as
  `SQUADOPS__LANGFUSE__PUBLIC_KEY` and `SQUADOPS__LANGFUSE__SECRET_KEY`;
- then `docker compose up -d --force-recreate runtime-api max neo nat bob eve data han joi` again.

## 10. Verify

```bash
.venv/bin/squadops doctor local-spark --check credentials               # every credential the deploy's own
.venv/bin/squadops doctor local-spark                                   # the rest of the deploy
```

Then one smoke cycle, read to its end. Agents that cannot authenticate show as `unhealthy` within a
minute, and the runtime API's log names a refused client-credentials grant.

## Undo

Each step's inverse reads the old value from `$OLD` (steps 3–7 with `$OLD` in place of `.env`), or
restore from `$B`: `cp "$B/env" .env && cp -rp "$B/secrets/." secrets/`, apply steps 3–8 with the
old values, and as a last resort `psql` the dump into a fresh volume.
