# Secrets Management

SquadOps framework version 0.8.2 includes centralized secrets management with support for multiple providers and name mapping for cloud portability.

## Secret Reference Format

Secrets are referenced using the `secret://<logical_name>` format anywhere inside string values:

```yaml
db:
  url: "postgresql://user:secret://db_password@host:5432/db"

comms:
  rabbitmq:
    url: "amqp://user:secret://rabbitmq_password@host:5672/"
```

### Logical Name Rules

- Logical names MUST match the pattern: `[A-Za-z][A-Za-z0-9_]*`
- Must start with a letter
- Followed by letters, digits, or underscores
- Examples: `db_password`, `my_secret`, `Secret123`, `a`, `A1`
- Invalid: `123invalid`, `_invalid`, `invalid-name`, `invalid.name`

## Providers

Exactly one secrets provider per runtime. Supported providers:

- `env`: Environment variables
- `file`: Local files
- `docker_secret`: Docker secrets (reads from `/run/secrets`)

### Environment Variable Provider (`env`)

Reads secrets from environment variables.

**Configuration:**
```yaml
secrets:
  provider: env
  env_prefix: SQUADOPS_  # Optional, defaults to SQUADOPS_, normalized to end with _
  name_map:  # Optional, maps logical names to env var names
    db_password: DB_PASSWORD
    rabbitmq_password: RABBITMQ_PASSWORD
```

**Rules:**
- If `env_prefix` is not provided, defaults to `"SQUADOPS_"`
- `env_prefix` is always normalized to end with `"_"` (added if missing)
- Provider key is uppercased before lookup
- Final env var name = `env_prefix + PROVIDER_KEY`
- Example: `db_password` → `SQUADOPS_DB_PASSWORD`

### File Provider (`file`)

Reads secrets from local files.

**Configuration:**
```yaml
secrets:
  provider: file
  file_dir: ./secrets  # Required when provider=file
  name_map:  # Optional, maps logical names to filenames
    db_password: db_pass.txt
```

**Rules:**
- `file_dir` is required when `provider=file`
- Provider key is used exactly as-is as the filename (no casing or normalization)
- Example: `db_password` → `./secrets/db_password`

### Docker Secrets Provider (`docker_secret`)

Reads secrets from Docker's `/run/secrets` directory.

**Configuration:**
```yaml
secrets:
  provider: docker_secret
  name_map:  # Optional, maps logical names to secret keys
    db_password: db_pass
```

**Rules:**
- Provider key is used exactly as-is as `/run/secrets/<provider_key>` (no casing or normalization)
- Example: `db_password` → `/run/secrets/db_password`

## Name Mapping

Name mapping allows you to use logical names in your configuration while mapping them to provider-specific keys for cloud portability.

**Example:**
```yaml
secrets:
  provider: env
  name_map:
    db_password: DB_PASSWORD  # Logical name → Provider key
    rabbitmq_password: RABBITMQ_PASSWORD
```

**Rules:**
- `logical_name` is the canonical identifier
- If `name_map[logical_name]` exists, use it as the provider key
- Otherwise `provider_key == logical_name`
- `name_map` is normalized to `{}` if `None` (never `None` in resolution logic)

## Configuration Loader Integration

Secret resolution follows this strict sequence:

1. Load and merge all config layers into a raw dict
2. Validate `SecretsConfig` ONLY from `merged["secrets"]` (fail fast if invalid)
3. **MANDATORY:** Scan the `secrets` section itself for `secret://` references and raise hard error if found
4. Scan for `secret://` references in the merged dict (excluding the `secrets` section)
5. If any `secret://` references found and no secrets configuration present, raise hard error
6. Resolve all `secret://...` references across the entire config dict (excluding `secrets` section)
7. Run full Pydantic validation into `AppConfig`

**Critical rules:**
- `SecretsConfig` validation MUST occur before any secret resolution
- The `secrets` section MUST NOT be traversed or modified during resolution
- If `secret://` references are found inside the `secrets` section itself, raise an error
- If any `secret://` references are found but no secrets configuration exists, raise hard error (no silent skipping)
- No validation of `AppConfig` may occur before secret resolution

## Inline String Replacement

Secret references are replaced inline within strings. No URL parsing or special-case handling is needed:

```yaml
# Before resolution
db:
  url: "postgresql://user:secret://db_password@host:5432/db"

# After resolution (if SQUADOPS_DB_PASSWORD=secret123)
db:
  url: "postgresql://user:secret123@host:5432/db"
```

## Error Handling

All secret resolution failures cause hard errors:

- Missing secrets → `SecretNotFoundError`
- Invalid `secret://` formats → `InvalidSecretReferenceError`
- Invalid logical name patterns → `InvalidSecretReferenceError`
- Recursive/chained secret references → `SecretResolutionError`
- Provider access failures → `SecretResolutionError`

No silent fallbacks or warnings.

## Recursive Reference Detection

If a resolved secret value still contains `"secret://"`, this is treated as an error (no chained or recursive references allowed).

**Example (forbidden):**
```yaml
# If SQUADOPS_SECRET1 resolves to "secret://secret2", this will raise SecretResolutionError
value: "secret://secret1"
```

## Logging and Redaction

- Resolved secret values MUST NEVER be logged
- Any config logging MUST pass through a redaction layer
- Exception messages MUST NOT include secret values (only logical names)

## Examples

### Environment Variable Provider

```yaml
secrets:
  provider: env
  env_prefix: SQUADOPS_

db:
  url: "postgresql://squadops:secret://db_password@postgres:5432/squadops"
```

Set environment variable:
```bash
export SQUADOPS_DB_PASSWORD=my_secret_password
```

### File Provider

```yaml
secrets:
  provider: file
  file_dir: ./secrets

db:
  url: "postgresql://squadops:secret://db_password@postgres:5432/squadops"
```

Create secret file:
```bash
echo "my_secret_password" > secrets/db_password
```

### Docker Secrets Provider

```yaml
secrets:
  provider: docker_secret

db:
  url: "postgresql://squadops:secret://db_password@postgres:5432/squadops"
```

Configure Docker secrets in `docker-compose.yml`:
```yaml
services:
  my_service:
    secrets:
      - db_password
    environment:
      SQUADOPS__SECRETS__PROVIDER: docker_secret

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

The service will read from `/run/secrets/db_password`.

## Enforcement

CI tests enforce that:
- No plaintext secrets in `config/**/*.yaml`, `docker-compose*.yml`, or committed `.env*` templates
- Secret-bearing keys (`password`, `passwd`, `token`, `api_key`, `secret`, `client_secret`, `access_key`) must use `secret://` references
- URLs with embedded credentials must use `secret://` references in the password component

