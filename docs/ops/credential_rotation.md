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
| `SQUADOPS_SUPERVISOR_PASSWORD` | the realm sync creates `squadops-supervisor` in a realm that lacks it, with only `campaign-supervisor`, and sets its password from `.env` (step 6, #2464). It is how the supervisor signs in to draft a held-out suite, which it can never approve |
| `GRAFANA_ADMIN_PASSWORD` | `grafana cli admin reset-admin-password` (step 7) |
| `LANGFUSE_NEXTAUTH_SECRET`, `LANGFUSE_SALT` | compose recreates Langfuse with them (step 8). **A new `SALT` invalidates every Langfuse API key**: step 9 mints new ones |
| `LANGFUSE_ADMIN_PASSWORD` | the Langfuse UI user's password, changed in the UI (step 9) |
| `SQUADOPS_SANDBOX_SERVICE_TOKEN` | compose recreates the sandbox service with it (step 8) |
| `SQUADOPS_TENSORFOLD_API_KEY` | while TensorFold serves, `engine_switch.py to-tensorfold` (after `to-ollama`) restarts it with the rewritten key file and recreates the model clients with the new value. While Ollama serves, nothing reads it until the next switch. Only the `squadops` line is rewritten: an operator's key on the same file is kept (see "Operator keys on TensorFold") |

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
`SQUADOPS_PASSWORD="$(val SQUADOPS_ADMIN_PASSWORD)" .venv/bin/squadops login -u squadops-admin`,
the password in the environment rather than an argument `ps` shows (#2291). The
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

## Operator keys on TensorFold (#2286)

`secrets/tensorfold_api_key.txt` is the file TensorFold reads at `--api-key-file`. It takes one
`label: key` per line, and this deploy owns the `squadops` line alone. A second client on the box, such
as an operator's local-model client, gets a line of its own. That makes its key revocable on its own,
attributable by its label on TensorFold's side, and untouched by the deploy key's rotation.

**What SquadOps already does with the other lines:**
- **It reads only its own.** `engine_switch.api_key()` and the bootstrap's credential reader
  (`value_from_secret_file`) take the `squadops` line by its label. A file with more lines works. A
  second `squadops` line is refused, with no value printed.
- **Rotation keeps the other lines.** `rotate` and `ensure` rewrite the `squadops` line in place
  (`merge_key_file`), so `rotate --only SQUADOPS_TENSORFOLD_API_KEY` changes that line and nothing
  else (`e4a3d20d`).

**Adding, rotating or removing an operator key** is done by hand, with the file kept at mode 0600 and
no key on a command line, in a log or in a commit. This writes `LABEL`'s line, new or replaced, and
prints nothing. The client reads its key from the file:

```bash
python3 - LABEL <<'PY'
import os, secrets, sys, tempfile
from pathlib import Path

label, path = sys.argv[1], Path("secrets/tensorfold_api_key.txt")
assert label and label == label.strip() and label != "squadops" and ":" not in label
lines = [l for l in path.read_text().splitlines() if l.partition(":")[0].strip() != label]
lines.append(f"{label}: {secrets.token_urlsafe(32)}")
fd, tmp = tempfile.mkstemp(dir=path.parent)  # created 0600
with os.fdopen(fd, "w") as f:
    f.write("\n".join(lines) + "\n")
os.replace(tmp, path)
PY
```

To remove a key, run the same program without its `lines.append` line.

**TensorFold reads the file only when it starts,** so a change takes effect at a restart. Make it
when the box is idle, with no cycle in flight (`engine_switch.py status`), through the switch, as the
deploy key's rotation does: `engine_switch.py to-ollama`, then `engine_switch.py to-tensorfold`.

**The launch gate reads an operator's request as busy, as intended** (SIP-0111 §5.5). A request on
an operator key is still one the launch didn't start. So while the operator's client is generating,
a Campaign's next run waits (`run_start_waiting_for_box … refusal=box_not_quiet`) and starts once
the engine is free.

A managed form of these keys, listed in `.env` and written by `rotate`, isn't built. Nothing on the
box needed more than the hand path above.

## Undo

Each step's inverse reads the old value from `$OLD` (steps 3–7 with `$OLD` in place of `.env`), or
restore from `$B`: `cp "$B/env" .env && cp -rp "$B/secrets/." secrets/`, apply steps 3–8 with the
old values, and as a last resort `psql` the dump into a fresh volume.
