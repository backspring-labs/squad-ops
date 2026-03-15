# Keycloak Operations Runbook (SIP-0063)

Operational procedures for the SquadOps Keycloak deployment.

## Deployment Profiles

| Profile | Realm | Display Name | Environment | MFA | Token TTL | Proxy | TLS |
|---------|-------|-------------|-------------|-----|-----------|-------|-----|
| `dev` | `squadops-dev` | SquadOps Dev | Laptop | Off | Defaults | none | none |
| `local` | `squadops-local` | SquadOps Local | DGX Spark | Admin only | 10 min | edge | external |
| `lab` | `squadops-lab` | SquadOps Lab | Home lab | Admin only | 10 min | edge | external |
| `cloud` | `squadops-cloud` | SquadOps Cloud | AWS/GCP/Azure | Admin + operator | 5 min | edge | external |

Config profiles: `config/profiles/{dev,local,lab,cloud}.yaml`
Realm exports: `infra/auth/squadops-realm{,-staging,-lab,-prod}.json`

## Starting Keycloak (Local Dev)

```bash
# Start core services + Keycloak
docker compose up -d postgres squadops-keycloak

# Verify realm imported
curl -s http://localhost:8180/realms/squadops-dev | jq .realm
# Expected: "squadops-dev"
```

## Backup & Restore

### Export Realm

```bash
# Export from running instance
docker compose exec squadops-keycloak \
  /opt/keycloak/bin/kc.sh export --realm squadops-dev --file /tmp/realm-export.json

# Copy to host
docker cp squadops-keycloak:/tmp/realm-export.json ./backups/realm-$(date +%Y%m%d).json
```

### Import Realm

```bash
# Import to fresh instance (use --override flag to replace existing)
docker compose exec squadops-keycloak \
  /opt/keycloak/bin/kc.sh import --file /opt/keycloak/data/import/squadops-realm.json
```

### Database Backup (Staging/Prod)

```bash
# PostgreSQL dump of Keycloak database
pg_dump -h <db-host> -U keycloak -d keycloak > keycloak-db-$(date +%Y%m%d).sql

# Restore
psql -h <db-host> -U keycloak -d keycloak < keycloak-db-20250101.sql
```

## Upgrade Strategy

**Pin version**: `quay.io/keycloak/keycloak:24.0.5` (current)

### Upgrade Process

1. **Read release notes** for the target version
2. **Test in staging first** — deploy new version to staging, soak for 48h minimum
3. **Verify realm export/import roundtrip** — export from old version, import to new
4. **Check breaking changes** in authentication flows and token formats
5. **Update image tag** in `docker-compose.yml` (squadops-keycloak service) and deployment configs
6. **Deploy to prod** after staging soak period passes

### Version Compatibility

- Keycloak 24.x realm exports are forward-compatible within the 24.x line
- Major version upgrades (24 -> 25) may require realm export migration
- Always test with `--import-realm` on a fresh instance before upgrading prod

## Signing Key Rotation

Keycloak automatically rotates RSA signing keys. The overlap period must exceed the maximum token lifetime to avoid validation failures.

**Overlap calculation:**
```
overlap >= access_token_minutes + session_policy.max_minutes
staging: >= 10 + 480 = 490 minutes (~8.2 hours)
prod:    >= 5 + 480 = 485 minutes (~8.1 hours)
```

### Manual Key Rotation

1. Navigate to **Realm Settings > Keys** in the Keycloak admin console
2. Click **Add Keystore > rsa-generated**
3. Set priority higher than the existing key
4. Wait for the overlap period to elapse
5. Disable the old key (do NOT delete until all tokens signed with it have expired)

## Admin Role Separation

### Keycloak Admin vs Realm Admin

| Role | Access | Credentials |
|------|--------|-------------|
| Keycloak Admin | Full server admin, all realms | `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` |
| Realm Admin | `admin` realm role in squadops-{local,lab,cloud} | Per-user credentials + MFA |

**Best practice**: The Keycloak server admin account should only be used for:
- Initial setup and realm creation
- Keycloak version upgrades
- Emergency recovery

Day-to-day operations should use realm-level admin accounts with MFA enabled.

### Admin Network Restrictions

The `allowed_networks` field in `KeycloakAdminConfig` restricts admin API access by source IP:

```yaml
admin:
  allowed_networks: ["10.0.0.0/8"]  # Internal network only
```

## MFA Enrollment Rollout

### Phase 1: Admin accounts (staging first)
1. Deploy staging realm with `squadops-browser-with-mfa` flow
2. Notify admin users to enroll TOTP via **Account Console > Security > Signing In**
3. Monitor for enrollment issues over 1-2 weeks
4. Deploy to prod

### Phase 2: Operator accounts
1. Update prod profile: `mfa_required_for_operator: true`
2. Notify operator users with enrollment instructions
3. Set a grace period if needed (Keycloak supports conditional OTP setup)

### TOTP Enrollment Steps (for users)
1. Log in to Keycloak Account Console: `https://auth.squadops.example/realms/squadops-cloud/account`
2. Navigate to **Security > Signing In > Two-Factor Authentication**
3. Click **Set up Authenticator Application**
4. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
5. Enter verification code to confirm

## Realm Export Linting

Run the lint script before deploying realm changes:

```bash
python scripts/dev/lint_realm_exports.py
```

The linter checks staging/prod realm exports for:
- No localhost in redirect URIs or web origins
- Correct `sslRequired` (`external` for staging, `all` for prod)
- Refresh token rotation enabled (`revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`)
- Event logging enabled
- Brute force protection enabled
- MFA authentication flow present
- Custom login theme set to `squadops`

## Custom Login Theme

The `squadops` login theme applies a dark slate/indigo design that matches the SquadOps console. It uses CSS-only overrides extending the built-in `keycloak` theme — no FreeMarker templates are modified.

### File Layout

```
infra/auth/keycloak-theme/squadops/login/
  theme.properties                      # parent=keycloak, imports CSS
  resources/css/squadops-login.css      # Dark theme overrides
```

### Design Tokens

| Token | Hex | Usage |
|-------|-----|-------|
| Page bg | `#0f172a` | Body background |
| Card bg | `#1e293b` | Login card |
| Border | `#334155` | Card/input borders |
| Primary text | `#e2e8f0` | Header, form text |
| Muted text | `#94a3b8` | Placeholders, hints |
| Accent | `#6366f1` | Button, links, focus ring |
| Accent hover | `#4f46e5` | Button hover |
| Danger | `#ef4444` | Error alerts |
| Font | `system-ui, sans-serif` | Matches console |

### How It Works

- `theme.properties` sets `parent=keycloak` so all base templates and CSS load first.
- `squadops-login.css` is appended after the base styles and overrides selectors with `!important`.
- The theme directory is mounted read-only into the Keycloak container via `docker-compose.yml`.
- Each realm export sets `"loginTheme": "squadops"` to activate the theme.

### Upgrading Keycloak

Since the theme only uses CSS overrides (no template changes), it is safe across Keycloak 24.x minor upgrades. If upgrading to a new major version, verify that the PatternFly CSS class names used in `squadops-login.css` still exist.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` after Keycloak restart | JWKS cache stale | Wait for `jwks_cache_ttl_seconds` (default 3600s) or restart Runtime API |
| MFA prompt not appearing | User missing `mfa-required` composite role | Assign `admin` or `operator` realm role (composites auto-assign `mfa-required`) |
| Token audience mismatch | Missing `runtime-api-audience` mapper | Verify mapper exists on `squadops-console` client |
| `Invalid redirect_uri` | Redirect URI not in client allowlist | Update `redirectUris` in realm export |
| Realm import fails | Realm already exists | Use `--override` flag or delete existing realm first |
| Connection refused to Keycloak | Service not ready or wrong port | Check `8180:8080` port mapping, verify health endpoint |
