# Canonical sandbox environment image: fullstack_fastapi_react (SIP-0102 §4.2)
#
# RENDERED FROM the environment contract in
# src/squadops/sandbox/environment.py — the contract is the source of truth;
# this Dockerfile is one adapter representation, checked in and deterministic,
# never LLM-authored. Keep the toolchain versions in lockstep with the
# contract's required_tools.
#
# The image carries TOOLCHAINS ONLY (python 3.12, node 20, npm). Per-cycle
# dependencies install into the bind-mounted workspace (.sandbox-venv,
# node_modules) so they persist across disposable one-shot containers and are
# never baked as undeclared image state (§4.7).
#
# Build:  ./scripts/dev/build_sandbox_env_image.sh
# Publish pipeline: open decision 4 in the SIP-0102 plan (resolve at 102.2 review).

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
