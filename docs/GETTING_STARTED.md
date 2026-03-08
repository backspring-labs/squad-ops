# Getting Started with SquadOps

This guide walks you through bootstrapping a fresh machine from `git clone` to a fully operational SquadOps environment.

## Quick Start

### macOS (dev-mac)

```bash
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops
./scripts/bootstrap/bootstrap.sh dev-mac
```

### Windows / WSL2 (dev-pc)

```bash
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops
./scripts/bootstrap/bootstrap.sh dev-pc
```

### DGX Spark (local-spark)

```bash
git clone https://github.com/backspring-labs/squad-ops.git
cd squad-ops
./scripts/bootstrap/bootstrap.sh local-spark
```

## Verify Your Environment

After bootstrap completes, verify everything is working:

```bash
squadops doctor <profile>
```

For example: `squadops doctor dev-mac`

Doctor checks Python version, venv, system tools, Docker services, Ollama models, and auth token. Fix any failures using the guidance it provides.

### Targeted checks

```bash
squadops doctor dev-mac --check python    # Python + venv only
squadops doctor dev-mac --check tools     # System dependencies only
squadops doctor dev-mac --check docker    # Docker services only
squadops doctor dev-mac --check models    # Ollama models only
squadops doctor dev-mac --json            # Machine-readable output
```

## What's Next

1. **Login** (Keycloak auth required for API access):
   ```bash
   squadops login
   ```

2. **Run a cycle**:
   ```bash
   squadops cycles create play_game --squad-profile full-squad --request-profile selftest
   squadops cycles show <cycle-id>
   ```

3. **Monitor**: Check Prefect UI at `http://localhost:4200` and LangFuse at `http://localhost:3001`

## Profiles

| Profile | Target | Python | Models | Notes |
|---------|--------|--------|--------|-------|
| `dev-mac` | macOS workstation | pyenv 3.11 | qwen2.5:7b, llama3.1:8b, qwen2.5:3b-instruct | Homebrew, Docker Desktop |
| `dev-pc` | WSL2 / Ubuntu | pyenv 3.11 | qwen2.5:7b, llama3.1:8b, qwen2.5:3b-instruct | APT, Docker Engine |
| `local-spark` | NVIDIA DGX Spark | system 3.11 | qwen2.5:72b, llama3:70b, qwen2.5:7b, llama3.1:8b | GPU required, large models |

## Bootstrap Options

```bash
./scripts/bootstrap/bootstrap.sh <profile> [options]

Options:
  --skip-docker   Skip Docker service startup
  --skip-models   Skip Ollama model pulls
  --dry-run       Print commands without executing
  --yes / -y      Skip confirmation prompts
```

Or via the CLI wrapper (validates profile schema first):

```bash
squadops bootstrap <profile> [--skip-docker] [--skip-models] [--dry-run] [--yes]
```

## Troubleshooting

### Doctor shows failures

Run `squadops doctor <profile> --json` to get machine-readable output. Each failed check includes a `fix_command` you can run directly.

### Docker services not starting

```bash
docker-compose up -d          # Start all services
docker-compose ps             # Check service status
docker-compose logs postgres  # Check specific service logs
```

### Ollama models missing

```bash
ollama list                   # See what's installed
ollama pull qwen2.5:7b        # Pull a specific model
```

### Python environment issues

```bash
python --version              # Check Python version
ls .venv/                     # Check venv exists
pip install -e .              # Re-install in editable mode
```

### Bootstrap script not found (CLI)

If `squadops bootstrap` reports the script is missing, you're likely running from an installed package without the repo checkout. Use `./scripts/bootstrap/bootstrap.sh` directly instead.
