#!/usr/bin/env bash
# LangFuse provisioning for bootstrap (SIP-0081, SIP-0084).
# Sourced by bootstrap.sh — not executed directly.
#
# Creates a LangFuse user, organization, project, and API keys,
# then writes the keys to .env and uploads prompt fragments.

LANGFUSE_HOST="${SQUADOPS_HOST:-localhost}"
LANGFUSE_PORT="3001"
LANGFUSE_URL="http://${LANGFUSE_HOST}:${LANGFUSE_PORT}"
LANGFUSE_INTERNAL_URL="http://localhost:${LANGFUSE_PORT}"
LANGFUSE_EMAIL="admin@squadops.local"
LANGFUSE_PASSWORD="admin123"
LANGFUSE_USER_NAME="SquadOps Admin"
LANGFUSE_ORG_NAME="SquadOps"
LANGFUSE_PROJECT_NAME="squadops"

# Wait for LangFuse to become healthy (up to 60s).
_wait_for_langfuse() {
    local timeout="${1:-60}"
    local elapsed=0
    local interval=3

    info "Waiting for LangFuse at ${LANGFUSE_INTERNAL_URL}..."
    while [[ $elapsed -lt $timeout ]]; do
        if curl -sf "${LANGFUSE_INTERNAL_URL}/api/public/health" >/dev/null 2>&1; then
            success "LangFuse is healthy"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    warn "LangFuse not healthy after ${timeout}s"
    return 1
}

# Create a LangFuse user account. Idempotent — skips if user exists.
_create_langfuse_user() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] Create LangFuse user ${LANGFUSE_EMAIL}"
        return 0
    fi

    local response
    response=$(curl -sf -X POST "${LANGFUSE_INTERNAL_URL}/api/auth/signup" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${LANGFUSE_USER_NAME}\",\"email\":\"${LANGFUSE_EMAIL}\",\"password\":\"${LANGFUSE_PASSWORD}\"}" 2>&1) || true

    if echo "$response" | grep -q '"User created"' 2>/dev/null; then
        success "LangFuse user created: ${LANGFUSE_EMAIL}"
    elif echo "$response" | grep -qi 'already exists\|duplicate\|email' 2>/dev/null; then
        success "LangFuse user already exists: ${LANGFUSE_EMAIL}"
    else
        success "LangFuse user ready: ${LANGFUSE_EMAIL}"
    fi
}

# Login to LangFuse via NextAuth and store session cookies.
# Sets LANGFUSE_COOKIES to the cookie jar path.
_login_langfuse() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] Login to LangFuse as ${LANGFUSE_EMAIL}"
        return 0
    fi

    LANGFUSE_COOKIES=$(mktemp)

    # Get CSRF token
    local csrf
    csrf=$(curl -sf -c "$LANGFUSE_COOKIES" "${LANGFUSE_INTERNAL_URL}/api/auth/csrf" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['csrfToken'])" 2>/dev/null) || {
        error "Failed to get CSRF token from LangFuse"
        return 1
    }

    # Login with credentials (follow redirects to capture session cookie)
    local http_code
    http_code=$(curl -s -L -b "$LANGFUSE_COOKIES" -c "$LANGFUSE_COOKIES" \
        -X POST "${LANGFUSE_INTERNAL_URL}/api/auth/callback/credentials" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "csrfToken=${csrf}&email=${LANGFUSE_EMAIL}&password=${LANGFUSE_PASSWORD}&callbackUrl=${LANGFUSE_INTERNAL_URL}" \
        -o /dev/null -w "%{http_code}" 2>&1)

    if [[ "$http_code" == "302" || "$http_code" == "200" ]]; then
        success "Logged in to LangFuse"
    else
        error "LangFuse login failed (HTTP ${http_code})"
        return 1
    fi
}

# Helper: call a LangFuse tRPC mutation via curl.
# Usage: _trpc <procedure> <json_data> [org_id]
_trpc() {
    local procedure="$1"
    local json_data="$2"
    local org_id="${3:-}"

    local extra_headers=()
    if [[ -n "$org_id" ]]; then
        extra_headers=(-H "x-langfuse-org-id: ${org_id}")
    fi

    curl -sf -b "$LANGFUSE_COOKIES" \
        "${LANGFUSE_INTERNAL_URL}/api/trpc/${procedure}" \
        -X POST \
        -H "Content-Type: application/json" \
        "${extra_headers[@]}" \
        -d "{\"json\":${json_data}}"
}

# Create organization and project, then generate API keys.
# Sets LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.
_create_langfuse_project_and_keys() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] Create LangFuse org/project/API keys"
        LANGFUSE_PUBLIC_KEY="pk-lf-dry-run"
        LANGFUSE_SECRET_KEY="sk-lf-dry-run"
        return 0
    fi

    # Step 1: Check for existing orgs in session
    local session_orgs
    session_orgs=$(curl -sf -b "$LANGFUSE_COOKIES" "${LANGFUSE_INTERNAL_URL}/api/auth/session" \
        | python3 -c "import sys,json; orgs=json.load(sys.stdin).get('user',{}).get('organizations',[]); print(orgs[0]['id'] if orgs else '')" 2>/dev/null) || true

    local org_id="$session_orgs"

    # Step 2: Create org if none exists
    if [[ -z "$org_id" ]]; then
        local org_result
        org_result=$(_trpc "organizations.create" "{\"name\":\"${LANGFUSE_ORG_NAME}\"}") || {
            error "Failed to create LangFuse organization"
            return 1
        }
        org_id=$(echo "$org_result" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['data']['json']['id'])" 2>/dev/null)
        if [[ -z "$org_id" ]]; then
            error "Failed to parse organization ID from response"
            return 1
        fi
        success "Created LangFuse organization: ${org_id}"
    else
        success "Using existing LangFuse organization: ${org_id}"
    fi

    # Step 3: Create project
    local project_result
    project_result=$(_trpc "projects.create" "{\"name\":\"${LANGFUSE_PROJECT_NAME}\",\"orgId\":\"${org_id}\"}" "$org_id") || {
        error "Failed to create LangFuse project"
        return 1
    }
    local project_id
    project_id=$(echo "$project_result" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['data']['json']['id'])" 2>/dev/null)
    if [[ -z "$project_id" ]]; then
        error "Failed to parse project ID from response"
        return 1
    fi
    success "Created LangFuse project: ${project_id}"

    # Step 4: Create API keys
    local keys_result
    keys_result=$(_trpc "apiKeys.create" "{\"projectId\":\"${project_id}\",\"note\":\"bootstrap-generated\"}" "$org_id") || {
        error "Failed to create LangFuse API keys"
        return 1
    }

    LANGFUSE_PUBLIC_KEY=$(echo "$keys_result" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['data']['json']['publicKey'])" 2>/dev/null)
    LANGFUSE_SECRET_KEY=$(echo "$keys_result" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['data']['json']['secretKey'])" 2>/dev/null)

    if [[ -z "$LANGFUSE_PUBLIC_KEY" || -z "$LANGFUSE_SECRET_KEY" ]]; then
        error "Failed to extract API keys from response"
        return 1
    fi

    success "LangFuse API keys generated"
}

# Write LangFuse keys to .env file.
_write_langfuse_env() {
    local env_file=".env"

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] Write LangFuse keys to ${env_file}"
        return 0
    fi

    if [[ ! -f "$env_file" ]]; then
        warn "No .env file — cannot write LangFuse keys"
        return 1
    fi

    # Update public key
    if grep -q '^SQUADOPS__LANGFUSE__PUBLIC_KEY=' "$env_file"; then
        sed -i "s|^SQUADOPS__LANGFUSE__PUBLIC_KEY=.*|SQUADOPS__LANGFUSE__PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}|" "$env_file"
    else
        echo "SQUADOPS__LANGFUSE__PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}" >> "$env_file"
    fi

    # Update secret key
    if grep -q '^SQUADOPS__LANGFUSE__SECRET_KEY=' "$env_file"; then
        sed -i "s|^SQUADOPS__LANGFUSE__SECRET_KEY=.*|SQUADOPS__LANGFUSE__SECRET_KEY=${LANGFUSE_SECRET_KEY}|" "$env_file"
    else
        echo "SQUADOPS__LANGFUSE__SECRET_KEY=${LANGFUSE_SECRET_KEY}" >> "$env_file"
    fi

    # Set prompt asset source to langfuse
    if grep -q '^SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=' "$env_file"; then
        sed -i "s|^SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=.*|SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=langfuse|" "$env_file"
    elif grep -q '^# *SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=' "$env_file"; then
        sed -i "s|^# *SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=.*|SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=langfuse|" "$env_file"
    else
        echo "SQUADOPS__PROMPTS__ASSET_SOURCE_PROVIDER=langfuse" >> "$env_file"
    fi

    success "LangFuse keys and prompt source written to .env"
}

# Upload prompt fragments and templates to LangFuse.
_upload_prompts() {
    local upload_script="${PROJECT_ROOT}/scripts/maintainer/upload_prompts_to_langfuse.py"

    if [[ ! -f "$upload_script" ]]; then
        warn "Prompt upload script not found at ${upload_script}"
        return 1
    fi

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        info "[dry-run] Upload prompts to LangFuse"
        SQUADOPS_MAINTAINER=1 .venv/bin/python "$upload_script" --dry-run
        return 0
    fi

    local environment="${DEPLOYMENT_PROFILE:-dev}"
    info "Uploading prompt fragments to LangFuse (environment: ${environment})..."
    SQUADOPS_MAINTAINER=1 .venv/bin/python "$upload_script" \
        --host "${LANGFUSE_INTERNAL_URL}" \
        --public-key "${LANGFUSE_PUBLIC_KEY}" \
        --secret-key "${LANGFUSE_SECRET_KEY}" \
        --environment "${environment}" || {
        warn "Prompt upload had errors — agents will fall back to filesystem"
        return 0
    }

    success "Prompts uploaded to LangFuse"
}

# Main entry point: provision LangFuse end-to-end.
provision_langfuse() {
    info "=== LangFuse Provisioning ==="

    # Check if keys already exist in .env
    if [[ "${DRY_RUN:-0}" != "1" ]] && [[ -f ".env" ]]; then
        local existing_pk
        existing_pk=$(grep '^SQUADOPS__LANGFUSE__PUBLIC_KEY=' .env | cut -d= -f2-)
        if [[ -n "$existing_pk" ]] && [[ "$existing_pk" != "" ]]; then
            success "LangFuse keys already configured in .env"
            LANGFUSE_PUBLIC_KEY="$existing_pk"
            LANGFUSE_SECRET_KEY=$(grep '^SQUADOPS__LANGFUSE__SECRET_KEY=' .env | cut -d= -f2-)
            _upload_prompts
            return 0
        fi
    fi

    _wait_for_langfuse 60 || return 1
    _create_langfuse_user
    _login_langfuse || return 1
    _create_langfuse_project_and_keys || return 1
    _write_langfuse_env
    _upload_prompts

    # Cleanup
    [[ -n "${LANGFUSE_COOKIES:-}" ]] && rm -f "$LANGFUSE_COOKIES"
}
