#!/usr/bin/env bash
# The deploy's inference engine, as its bootstrap profile declares it (SIP-0111, G4; #2229).
# Sourced by bootstrap.sh — not executed directly.
#
# A profile with no `inference_engine`, or `engine: ollama`, runs on Ollama as before and nothing here
# acts. `engine: tensorfold` installs the frozen recipe's image, checkpoint and drafter before the
# services start, and switches the deploy to it once they are up: the engine, then every model
# client, recorded in .env's COMPOSE_FILE. Ollama stays installed, stopped, as the rollback.

# Print "ollama", or "tensorfold <recipe>", for a bootstrap profile.
inference_engine_of() {
    local profile_yaml="$1"
    .venv/bin/python - "$profile_yaml" <<'PY'
import sys

import yaml

block = (yaml.safe_load(open(sys.argv[1])) or {}).get("inference_engine") or {}
engine = block.get("engine") or "ollama"
print(engine if engine == "ollama" else f"{engine} {block.get('recipe') or ''}".strip())
PY
}

install_inference_engine() {
    local profile_yaml="$1" engine recipe
    read -r engine recipe < <(inference_engine_of "$profile_yaml")
    [[ "$engine" == "tensorfold" ]] || return 0
    info "=== TensorFold (${recipe}) ==="
    run_or_dry .venv/bin/python scripts/dev/ops/tensorfold_install.py "$recipe"
}

select_inference_engine() {
    local profile_yaml="$1" engine recipe
    read -r engine recipe < <(inference_engine_of "$profile_yaml")
    [[ "$engine" == "tensorfold" ]] || return 0
    info "Switching the deploy to TensorFold: the engine, then every model client"
    run_or_dry .venv/bin/python scripts/dev/ops/engine_switch.py to-tensorfold "$recipe"
}
