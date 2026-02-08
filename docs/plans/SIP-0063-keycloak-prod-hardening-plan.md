# SIP-0063: Keycloak Production Hardening — Implementation Plan

## Context

SIP-0062 (implemented, 150 tests) established the auth boundary — `AuthPort`, `AuthorizationPort`, Keycloak adapter, JWT middleware, CORS, service-to-service client credentials, and audit infrastructure. All of that works against a local-dev Keycloak instance with a basic realm export (`infra/auth/squadops-realm.json`).

SIP-0063 hardens the Keycloak server-side posture for production readiness. It does **not** change ports, adapters, or middleware. It adds:
1. A `KeycloakOperationalConfig` Pydantic schema for server-side policy knobs
2. Hardened realm exports for staging/prod (token lifetimes, MFA flows, client roles, audience mappers, redirect URI lockdown)
3. Deployment profile YAML files (local, staging, prod) with environment-appropriate defaults
4. Pydantic cross-field validators enforcing production safety invariants
5. Operational documentation (backup/restore, key rotation, upgrade strategy)
6. Unit tests for config validation; operational checks for staging

This plan covers both phases: **Phase 1** (Config Schema + Realm Hardening) and **Phase 2** (Operational Posture + Documentation).

---

## Phase 1: Config Schema + Realm Hardening

### 1.1 Pydantic Config Models — `src/squadops/config/schema.py` (MODIFY)

Add the following nested models **before** `AuthConfig` in schema.py. Follow the existing pattern (Pydantic `BaseModel`, `Field()` with defaults, `ge`/`le` validation).

**New models (in dependency order):**

```python
class KeycloakTokenPolicyConfig(BaseModel):
    access_token_minutes: int = Field(default=10, ge=1)
    refresh_token_minutes: int = Field(default=1440, ge=1)
    refresh_token_rotation: bool = True

class KeycloakSessionPolicyConfig(BaseModel):
    idle_minutes: int = Field(default=30, ge=1)
    max_minutes: int = Field(default=480, ge=1)

class KeycloakTotpPolicyConfig(BaseModel):
    algorithm: str = "HmacSHA1"
    digits: int = Field(default=6, ge=6, le=8)
    period: int = Field(default=30, ge=20, le=60)

class KeycloakSecurityConfig(BaseModel):
    mfa_required_for_admin: bool = True
    mfa_required_for_operator: bool = True
    mfa_method: str = "totp"  # "totp" | "webauthn" | "totp+webauthn"
    totp_policy: KeycloakTotpPolicyConfig = Field(default_factory=KeycloakTotpPolicyConfig)
    brute_force_protection: bool = True
    max_login_failures: int = Field(default=5, ge=1)
    wait_increment_seconds: int = Field(default=60, ge=1)
    max_wait_seconds: int = Field(default=900, ge=1)

class KeycloakLoggingConfig(BaseModel):
    admin_events_enabled: bool = True
    login_events_enabled: bool = True

class KeycloakAdminConfig(BaseModel):
    username: str = "admin"
    password: str  # Supports secret:// references
    allowed_networks: list[str] = Field(default_factory=list)

class KeycloakOperationalConfig(BaseModel):
    realm: str = "squadops-local"
    base_url: str = "http://localhost:8180"
    public_url: str | None = None
    db_dsn: str | None = None  # secret:// ref
    proxy_mode: str = "none"  # "none" | "edge" | "reencrypt" | "passthrough"
    external_tls_termination: bool = False
    hostname_strict: bool = False
    admin: KeycloakAdminConfig
    token_policy: KeycloakTokenPolicyConfig = Field(default_factory=KeycloakTokenPolicyConfig)
    session_policy: KeycloakSessionPolicyConfig = Field(default_factory=KeycloakSessionPolicyConfig)
    security: KeycloakSecurityConfig = Field(default_factory=KeycloakSecurityConfig)
    logging: KeycloakLoggingConfig = Field(default_factory=KeycloakLoggingConfig)
```

**Modify existing `AuthConfig`:**
Add `keycloak: KeycloakOperationalConfig | None = None` field. Add `model_post_init` validator: when `provider == "keycloak"` and `enabled == True`, require `keycloak` is not None.

### 1.2 Cross-Field Validators — `src/squadops/config/schema.py` (MODIFY)

Add `model_post_init` on `KeycloakOperationalConfig` enforcing staging/prod invariants. Detection: realm name contains `staging` or `prod`.

```python
def model_post_init(self, __context):
    is_staging_or_prod = "staging" in self.realm or "prod" in self.realm
    if is_staging_or_prod:
        if self.db_dsn is None:
            raise ValueError("db_dsn required for staging/prod realms")
        if self.proxy_mode == "none":
            raise ValueError("proxy_mode must not be 'none' for staging/prod")
        if not self.hostname_strict:
            raise ValueError("hostname_strict must be true for staging/prod")
    if self.external_tls_termination and not self.public_url:
        raise ValueError("public_url required when external_tls_termination is true")
```

### 1.3 Hardened Realm Export — Staging (`infra/auth/squadops-realm-staging.json`) (NEW)

Fork from existing `squadops-realm.json`. Changes:

| Area | Current (local) | Staging |
|------|----------------|---------|
| `realm` | `squadops` | `squadops-staging` |
| `sslRequired` | `none` | `external` |
| Redirect URIs | `http://localhost:*` wildcards | Explicit staging URLs (e.g., `https://staging.squadops.example/*`) — placeholder, operator fills in |
| Web origins | `http://localhost:*` | Explicit staging origins |
| Token lifetime | Keycloak defaults | `accessTokenLifespan: 600` (10 min), `ssoSessionIdleTimeout: 1800` (30 min), `ssoSessionMaxLifespan: 28800` (8h) |
| Refresh rotation | off | `"revokeRefreshToken": true` |
| Brute force | `true` (already) | `true` + `maxFailureWaitSeconds: 900`, `waitIncrementSeconds: 60`, `maxDeltaTimeSeconds: 43200` |
| Roles | Realm-level only | Add **client roles** on `squadops-runtime` client: `admin`, `operator`, `viewer` |
| Audience mapper | Present on console | Verify `runtime-api-audience` mapper present |
| MFA flow | None | Add `squadops-browser-with-mfa` authentication flow (see 1.5) |
| OTP policy | None | `otpPolicyType: "totp"`, `otpPolicyDigits: 6`, `otpPolicyPeriod: 30`, `otpPolicyAlgorithm: "HmacSHA1"` |
| Admin events | Off | `eventsEnabled: true`, `adminEventsEnabled: true`, `adminEventsDetailsEnabled: true` |

### 1.4 Hardened Realm Export — Prod (`infra/auth/squadops-realm-prod.json`) (NEW)

Same as staging with:
- `realm: "squadops-prod"`
- `sslRequired: "all"` (TLS everywhere, not just external)
- Redirect URIs: production URLs (placeholders)
- `mfa_required_for_operator: true` (staging may be `false`)
- No `directAccessGrantsEnabled` on any client (resource owner password grant disabled)

### 1.5 MFA Conditional Authentication Flow

Add to both staging and prod realm exports. Keycloak realm JSON representation:

```json
{
  "authenticationFlows": [
    {
      "alias": "squadops-browser-with-mfa",
      "description": "Browser flow with conditional MFA for admin/operator roles",
      "providerId": "basic-flow",
      "topLevel": true,
      "builtIn": false,
      "authenticationExecutions": [
        {
          "authenticator": "auth-cookie",
          "authenticatorFlow": false,
          "requirement": "ALTERNATIVE",
          "priority": 10
        },
        {
          "authenticatorFlow": true,
          "requirement": "ALTERNATIVE",
          "priority": 20,
          "flowAlias": "squadops-username-password-mfa"
        }
      ]
    },
    {
      "alias": "squadops-username-password-mfa",
      "description": "Username/password then conditional OTP",
      "providerId": "basic-flow",
      "topLevel": false,
      "builtIn": false,
      "authenticationExecutions": [
        {
          "authenticator": "auth-username-password-form",
          "authenticatorFlow": false,
          "requirement": "REQUIRED",
          "priority": 10
        },
        {
          "authenticatorFlow": true,
          "requirement": "CONDITIONAL",
          "priority": 20,
          "flowAlias": "squadops-conditional-otp"
        }
      ]
    },
    {
      "alias": "squadops-conditional-otp",
      "description": "OTP required if user has admin or operator role",
      "providerId": "basic-flow",
      "topLevel": false,
      "builtIn": false,
      "authenticationExecutions": [
        {
          "authenticator": "conditional-user-role",
          "authenticatorFlow": false,
          "requirement": "REQUIRED",
          "priority": 10,
          "authenticatorConfig": "squadops-mfa-role-condition"
        },
        {
          "authenticator": "auth-otp-form",
          "authenticatorFlow": false,
          "requirement": "REQUIRED",
          "priority": 20
        }
      ]
    }
  ]
}
```

Note: Keycloak's `conditional-user-role` authenticator only checks a single role. To cover both `admin` and `operator`, we need two conditional sub-flows OR use a composite role. **Recommended approach:** Create a composite realm role `mfa-required` that includes `admin` and `operator`, then condition on `mfa-required`. This is cleaner than duplicating flows.

Bind this flow to the `squadops-console` client via `authenticationFlowBindingOverrides.browser`.

### 1.6 Update Local Realm — `infra/auth/squadops-realm.json` (MODIFY)

Minor updates to existing local realm for consistency:
- Add client roles on `squadops-runtime` client (same `admin`, `operator`, `viewer`) so local dev can test `roles_mode: client`
- Verify audience mapper already present (it is)
- Add `eventsEnabled: true` for local testing of audit events
- Keep `sslRequired: "none"` (local only)
- No MFA flow (local dev exempted per SIP)

### 1.7 Deployment Profile YAMLs (NEW)

Create profile files that the config loader already supports:

**`config/profiles/local.yaml`:**
```yaml
auth:
  enabled: true
  provider: keycloak
  roles_mode: realm
  keycloak:
    realm: squadops
    base_url: "http://localhost:8180"
    proxy_mode: "none"
    hostname_strict: false
    admin:
      username: admin
      password: "secret://keycloak_admin_password"
    security:
      mfa_required_for_admin: false
      mfa_required_for_operator: false
```

**`config/profiles/staging.yaml`:**
```yaml
auth:
  enabled: true
  provider: keycloak
  roles_mode: client
  roles_client_id: squadops-runtime
  keycloak:
    realm: squadops-staging
    base_url: "http://keycloak:8080"
    public_url: "https://auth.staging.squadops.example"
    db_dsn: "secret://keycloak_db_dsn"
    proxy_mode: edge
    external_tls_termination: true
    hostname_strict: true
    admin:
      username: admin
      password: "secret://keycloak_admin_password"
      allowed_networks: ["10.0.0.0/8"]
    token_policy:
      access_token_minutes: 10
      refresh_token_minutes: 1440
      refresh_token_rotation: true
    session_policy:
      idle_minutes: 30
      max_minutes: 480
    security:
      mfa_required_for_admin: true
      mfa_required_for_operator: false
      brute_force_protection: true
    logging:
      admin_events_enabled: true
      login_events_enabled: true
```

**`config/profiles/prod.yaml`:**
Same as staging with:
- `realm: squadops-prod`
- `public_url: "https://auth.squadops.example"`
- `mfa_required_for_operator: true`
- `access_token_minutes: 5` (tighter in prod)

### 1.8 Unit Tests — `tests/unit/auth/test_keycloak_operational_config.py` (NEW)

Test cases:
- Valid local config (all defaults) passes validation
- Valid staging config (all required fields) passes
- Staging realm without `db_dsn` → `ValueError`
- Prod realm with `proxy_mode: none` → `ValueError`
- Staging realm with `hostname_strict: false` → `ValueError`
- `external_tls_termination: true` without `public_url` → `ValueError`
- Default `mfa_required_for_admin` is `true`
- Default `brute_force_protection` is `true`
- Token policy fields respect `ge=1` bounds
- `KeycloakOperationalConfig` nested under `AuthConfig.keycloak`
- Env var override: `SQUADOPS__AUTH__KEYCLOAK__REALM` maps correctly
- Full `AuthConfig` with `provider=keycloak` requires `keycloak` section present
- `admin.password` supports `secret://` reference format

Marker: `@pytest.mark.auth`

### 1.9 Phase 1 Exit Criteria

- [ ] All new Pydantic models importable from `squadops.config.schema`
- [ ] Cross-field validators reject invalid staging/prod configs
- [ ] 3 realm exports in `infra/auth/`: local (updated), staging (new), prod (new)
- [ ] Staging/prod realms include: client roles, audience mapper, MFA flow, token policies, audit events, brute-force protection
- [ ] 3 profile YAMLs: local, staging, prod
- [ ] Unit tests pass (target: 15-20 new tests)
- [ ] `run_new_arch_tests.sh` still passes (no regressions)

---

## Phase 2: Operational Posture + Documentation

### 2.1 Docker Compose Updates — `docker-compose.yml` (MODIFY)

Add Keycloak environment variables for operational config:
- `KC_DB=postgres` (for staging/prod profiles, not local)
- `KC_DB_URL`, `KC_DB_USERNAME`, `KC_DB_PASSWORD` (conditionally, via env file)
- `KC_PROXY_HEADERS=xforwarded` (when behind proxy)
- `KC_HOSTNAME_STRICT=true/false`
- `KC_HEALTH_ENABLED=true`
- `KC_METRICS_ENABLED=true`
- Keep existing `KC_BOOTSTRAP_ADMIN_*` vars

Add comments documenting which vars are local-only vs staging/prod.

### 2.2 Operational Docs — `docs/ops/keycloak-operations.md` (NEW)

Document:

**Backup & Restore:**
- DB backup: `pg_dump` of Keycloak DB on schedule
- Realm export: `kc.sh export --realm <realm> --file <output>`
- Restore procedure: stop Keycloak → restore DB → start → verify
- Test frequency: at least once per staging deployment

**Upgrade Strategy:**
- Pin Keycloak version in docker-compose (currently `24.0.5`)
- Upgrade path: staging first → soak 48h → prod
- Pre-upgrade: DB snapshot
- Rollback: restore snapshot, revert compose image tag

**Signing Key Rotation:**
- Routine: not required in 0.9.2 (keys auto-generated at realm creation)
- Incident: rotate key → remove compromised key → all sessions invalidated → users re-auth
- Key overlap: keep old key passive for `access_token_minutes + session_policy.max_minutes` (default 490 min)
- SIP-0062's JWKS forced-refresh handles client-side pickup

**Admin Role Separation:**
- Keycloak `master` realm admin ≠ SquadOps `admin` role
- Bootstrap admin is one-time setup; create separate operator accounts
- Document in team runbook

**MFA Enrollment Rollout:**
1. Enable MFA flow in realm (users can enroll voluntarily)
2. Communicate enrollment deadline to team
3. Set `mfa_required_for_admin/operator: true` — users without TOTP enrolled are prompted at next login

### 2.3 CI Denylist Check (Extension)

SIP-0062 already mandates a CI check for `NoOpAuthAdapter` in `adapters/auth/`. No new CI check needed for SIP-0063 (config validation covers it via Pydantic).

### 2.4 Integration Test Extensions — `tests/integration/auth/` (MODIFY or NEW)

Add or extend integration tests (require running Keycloak):
- Realm export/import roundtrip: export realm → reimport → verify clients and roles present
- Refresh token rotation: login → get tokens → refresh → verify old refresh token rejected
- Audit events: perform admin action → verify event in Keycloak event log
- MFA flow (manual/staging check — hard to automate in CI without TOTP seed)

Marker: `@pytest.mark.auth`, `@pytest.mark.integration`

### 2.5 Phase 2 Exit Criteria

- [ ] `docs/ops/keycloak-operations.md` covers backup, restore, upgrade, key rotation, MFA rollout
- [ ] Docker Compose has operational config comments
- [ ] Integration tests cover refresh token rotation and realm export/import
- [ ] All existing tests still pass (`run_new_arch_tests.sh`)

---

## Files Modified/Created Summary

| File | Action | Phase |
|------|--------|-------|
| `src/squadops/config/schema.py` | MODIFY — add 8 new Pydantic models + AuthConfig.keycloak field + validators | 1 |
| `infra/auth/squadops-realm.json` | MODIFY — add client roles on squadops-runtime, enable events | 1 |
| `infra/auth/squadops-realm-staging.json` | NEW — hardened staging realm | 1 |
| `infra/auth/squadops-realm-prod.json` | NEW — hardened prod realm | 1 |
| `config/profiles/local.yaml` | NEW — local dev auth profile | 1 |
| `config/profiles/staging.yaml` | NEW — staging auth profile | 1 |
| `config/profiles/prod.yaml` | NEW — prod auth profile | 1 |
| `tests/unit/auth/test_keycloak_operational_config.py` | NEW — config validation tests | 1 |
| `docker-compose.yml` | MODIFY — add operational env var comments | 2 |
| `docs/ops/keycloak-operations.md` | NEW — operational runbook | 2 |
| `tests/integration/auth/test_realm_hardening.py` | NEW — integration tests for hardening behaviors | 2 |

---

## Verification

### Phase 1
```bash
# Unit tests for new config models
pytest tests/unit/auth/test_keycloak_operational_config.py -v

# Regression — all existing auth tests still pass
pytest tests/unit/auth/ -v

# Full regression suite
./scripts/dev/run_new_arch_tests.sh -v

# Validate realm JSON is valid
python -c "import json; json.load(open('infra/auth/squadops-realm-staging.json'))"
python -c "import json; json.load(open('infra/auth/squadops-realm-prod.json'))"

# Validate profile YAML loads
python -c "
from squadops.config.loader import load_config
load_config(profile='local')
"
```

### Phase 2
```bash
# Integration tests (requires Docker + Keycloak)
docker-compose --profile auth up -d keycloak
pytest tests/integration/auth/ -v -m auth

# Operational check — realm import works
docker-compose exec squadops-keycloak /opt/keycloak/bin/kc.sh export --realm squadops --file /tmp/test-export.json
```
