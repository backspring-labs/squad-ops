# SquadOps Console — Multi-stage build
# Fetches Continuum shell at pinned ref, builds SvelteKit shell + plugin UIs,
# then assembles a Python runtime image serving everything.

# ── Stage 0: Fetch Continuum source ──────────────────────────────────────────
FROM alpine/git:latest AS continuum-source

ARG CONTINUUM_GIT_URL
ARG CONTINUUM_REF

RUN set -e && \
    git init /continuum && \
    cd /continuum && \
    git remote add origin "${CONTINUUM_GIT_URL}" && \
    # Determine ref type and fetch accordingly
    if echo "${CONTINUUM_REF}" | grep -qE '^[0-9a-f]{40}$'; then \
        echo "Fetching SHA: ${CONTINUUM_REF}" && \
        git fetch --depth 1 origin "${CONTINUUM_REF}" && \
        git checkout FETCH_HEAD; \
    elif echo "${CONTINUUM_REF}" | grep -q 'refs/tags/'; then \
        TAG_REF="${CONTINUUM_REF#refs/tags/}" && \
        echo "Fetching tag: ${TAG_REF}" && \
        git fetch --depth 1 origin "refs/tags/${TAG_REF}" && \
        git checkout FETCH_HEAD; \
    else \
        echo "Fetching branch: ${CONTINUUM_REF}" && \
        git fetch --depth 1 origin "${CONTINUUM_REF}" && \
        git checkout "origin/${CONTINUUM_REF}" && \
        echo "Resolved ${CONTINUUM_REF} → $(git rev-parse HEAD)"; \
    fi && \
    git rev-parse HEAD > /continuum/.resolved_sha

# ── Stage 1: Build SvelteKit shell ───────────────────────────────────────────
FROM node:20-slim AS shell-builder

COPY --from=continuum-source /continuum/web /build/web
WORKDIR /build/web
RUN npm ci && npm run build

# ── Stage 2: Build plugin UIs ────────────────────────────────────────────────
FROM node:20-slim AS plugin-builder

# Copy all plugin UI directories
COPY continuum-plugins/ /plugins-src/

WORKDIR /plugins-src
RUN set -e && \
    for plugin_dir in squadops.*/ui; do \
        if [ -d "${plugin_dir}" ]; then \
            echo "Building plugin UI: ${plugin_dir}" && \
            cd "/plugins-src/${plugin_dir}" && \
            npm ci && \
            npm run build && \
            cd /plugins-src; \
        fi; \
    done

# ── Stage 3: Python runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install Continuum Python package (pinned, immutable)
COPY --from=continuum-source /continuum /tmp/continuum
RUN pip install --no-cache-dir /tmp/continuum && rm -rf /tmp/continuum

# Install console application dependencies
COPY docker/console/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy console application code
COPY docker/console/main.py ./main.py
COPY docker/console/auth_bff.py ./auth_bff.py

# Copy built SvelteKit shell and inject config.js loader
COPY --from=shell-builder /build/web/build ./web/build/
RUN sed -i 's|</head>|<script src="/config.js"></script></head>|' ./web/build/index.html

# Copy plugin Python code + built UIs
# Each plugin gets: __init__.py, plugin.toml, and dist/ (built JS)
COPY continuum-plugins/ /tmp/plugins-src/
COPY --from=plugin-builder /plugins-src/ /tmp/plugins-built/

RUN set -e && \
    mkdir -p ./plugins && \
    for plugin_dir in /tmp/plugins-src/squadops.*/; do \
        plugin_name=$(basename "${plugin_dir}") && \
        mkdir -p "./plugins/${plugin_name}" && \
        # Copy Python code and manifest
        cp -r "${plugin_dir}__init__.py" "./plugins/${plugin_name}/" 2>/dev/null || true && \
        cp -r "${plugin_dir}plugin.toml" "./plugins/${plugin_name}/" 2>/dev/null || true && \
        # Copy built dist from plugin-builder stage
        if [ -d "/tmp/plugins-built/${plugin_name}/dist" ]; then \
            cp -r "/tmp/plugins-built/${plugin_name}/dist" "./plugins/${plugin_name}/"; \
        fi; \
    done && \
    rm -rf /tmp/plugins-src /tmp/plugins-built

EXPOSE 4040

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4040/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4040"]
