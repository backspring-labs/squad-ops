---
title: Externalized Build Sandbox
status: proposed
author: jladd
created_at: '2026-07-08T00:00:00Z'
---
# SIP: Externalized Build Sandbox

## Status
Proposed

**Targets:** vision item — no committed release. Candidate for the 2.0 capability-backed-agents arc (see [[capability-backed-agents-2-0]]), or an earlier stabilization minor if the toolchain-bundling cost grows. This is the principled long-term home for build/test execution; it is **not** a near-term blocker.
**Builds on:** `ContainerPort` (`src/squadops/ports/tools/container.py`, `ContainerSpec`/`ContainerResult`, SIP-0.8.7) and the `CapabilityExecutor` port (`src/squadops/ports/capabilities/executor.py`). Extends the build lineage: SIP-0068 (Enhanced Agent Build Capabilities), SIP-0071 (Builder Role), SIP-0086 (Build Convergence Loop).
**Motivating case:** #306 — the QA agent image had to bundle Node.js so the frontend build check (#290/#296/#303) could run at all. That fix ships Node in the qa image alone; this SIP removes the need to bundle *any* build toolchain in *any* agent image.
**Coordinates with:** SIP-Edge-Deployment-Profile (a remote/edge sandbox is the natural adapter target) and SIP-Capability-Backed-Agents (build toolchains become a provisioned capability of the sandbox, not baked into the agent).

## 1. Abstract

Build and test execution currently runs **in-process, inside the agent container**. `run_tests` / `run_node_tests` / `run_frontend_build` (`src/squadops/capabilities/handlers/test_runner.py`) materialize generated files to a tempdir and `asyncio.create_subprocess_exec` the toolchain (`pytest`, `npm install`, `npx vitest`, `vite build`) in the agent's own process space. Two consequences follow, both structural:

1. **The agent image must carry every toolchain any capability might invoke.** Python test deps live in the QA image (`agents/instances/qa/requirements.txt`); Node had to be added there too (#306). Each new build target (Go, Rust, a different Node major, a native compiler) is another apt/pip line in an agent image — and the image that carries it is the same long-lived container that holds the agent's DB credentials, queue connection, and LLM keys.
2. **Untrusted generated code executes in the agent runtime.** `npm install` on an LLM-generated `package.json` runs arbitrary install scripts; a generated test can `import os; os.system(...)`. Today that runs as the agent process, with the agent's filesystem and secrets in reach.

This SIP proposes a **build sandbox**: a first-class port through which agents delegate a build/test job — materialized files + a toolchain profile + a command — to an ephemeral, isolated, toolchain-provisioned environment, and receive a structured result. Agent images become lean and uniform (no per-role toolchain divergence, retiring #306's QA-Node special case); untrusted execution is isolated from the agent runtime; and the toolchain becomes a pinned, reproducible property of the sandbox image rather than a drifting accretion in six agent Dockerfiles.

## 2. Problem Statement

**P1 — Toolchain bundling couples image size to build breadth.** Every buildable stack an agent must validate forces a dependency into that agent's image. Node is ~150 MB; the #306 issue explicitly weighed "bloat all six images" against "a per-role variant" and settled on qa-only as the least-bad *bundling* option. Bundling itself is the ceiling: the more stacks the squad can build, the heavier and more divergent the agent images, and the more the "what can this agent build" question is answered by a Dockerfile rather than by configuration.

**P2 — In-process execution of generated code is a security boundary violation.** The agent container is a trust boundary: it holds `secret://`-resolved credentials, an authenticated queue connection, and (post-#326) a service identity. Running `npm install` / arbitrary generated tests in that same process means a hostile or accidentally-destructive generated artifact runs with the agent's privileges. The current mitigation is "we mostly trust our own LLM output" — not a boundary.

**P3 — No reproducibility or pinning of the build environment.** The toolchain version is whatever the agent's base image happened to install (Debian's `nodejs` 18.19 for #306). A build that passes on one image and fails on another — the exact class of bug #306 was found chasing — has no single pinned source of truth for "the environment this was built in."

**P4 — Per-role image divergence is accreting.** `agents/instances/<role>/requirements.txt` (pip) plus the #306 `AGENT_ROLE=qa` apt branch means the shared Dockerfile now has role-conditional logic in two dimensions. Each addition is individually reasonable and collectively a drift surface.

## 3. Goals / Non-Goals

**Goals**
- A `BuildSandboxPort` on the ports bundle: submit a build job, get a structured result, with isolation and a pinned toolchain.
- Agent images carry **no** build toolchain — only the agent runtime. Retire the #306 QA-Node branch and the pip role-extras-as-toolchain pattern.
- Untrusted generated code runs isolated from the agent process (separate FS, no ambient secrets, resource limits, non-root, network egress off by default with an explicit allowance for dependency fetch).
- Toolchain profiles are declared configuration (`node20`, `python312`, `fullstack`), each pinned to a sandbox image digest.
- `test_runner.py` executes through the port instead of `create_subprocess_exec`, with behavior parity (the same `RunTestsResult` / `BuildCheckResult` shapes, the same non-blocking-on-missing-tooling semantics).

**Non-Goals**
- Not a general remote-code-execution service or a user-facing build API.
- Not a replacement for the `CapabilityExecutor` (task dispatch) — this is *command* execution within a task, one layer down.
- Not committing a specific sandbox runtime (Docker / gVisor / Firecracker / a cloud ACI). The port abstracts it; adapters choose.
- Not addressing dependency-supply-chain trust (malicious npm packages) beyond isolation — that is a separate hardening concern.

## 4. Design

### 4.1 Port

A new domain port beside the existing tool ports (`ports/tools/`), built on the same `ContainerSpec`/`ContainerResult` vocabulary already established for `ContainerPort`:

```python
# src/squadops/ports/capabilities/build_sandbox.py  (illustrative)
class BuildSandboxPort(ABC):
    @abstractmethod
    async def run_build(self, job: BuildJob) -> BuildResult:
        """Execute a build/test job in an isolated, toolchain-provisioned
        sandbox. Never raises for build failure — a non-zero exit is a
        BuildResult, not an exception. Raises only on sandbox-provisioning
        failure (toolchain image unavailable, sandbox backend unreachable)."""
```

### 4.2 Models

```python
@dataclass(frozen=True)
class BuildJob:
    files: tuple[MaterializedFile, ...]   # generated source + test files
    toolchain: str                        # profile id: "node20", "python312", "fullstack"
    command: tuple[str, ...]              # e.g. ("npm", "install") then ("npx", "vitest", "run")
    working_subdir: str | None = None     # discovered package.json / pyproject dir (#303)
    timeout_seconds: float = 300.0
    network: NetworkPolicy = NetworkPolicy.DEPS_ONLY   # OFF | DEPS_ONLY | FULL

@dataclass(frozen=True)
class BuildResult:
    ran: bool                             # False iff the toolchain/sandbox was unavailable
    exit_code: int | None
    stdout: str
    stderr: str
    produced_files: tuple[MaterializedFile, ...] = ()   # e.g. dist/ from vite build
    error: str | None = None              # populated when ran is False
```

`ran=False` preserves the current non-blocking contract: a missing toolchain or unreachable sandbox is an environment limitation, not a deliverable failure (exactly as `run_frontend_build` returns `ran=False` today on missing npm). The caller decides blocking; the port never decides it.

### 4.3 Toolchain profiles

Declared config (`config/build_sandbox/toolchains.yaml` or a `SQUADOPS__BUILD_SANDBOX__*` section), each mapping a profile id to a pinned sandbox image digest and default command allowances:

```yaml
toolchains:
  python312:  { image: "squadops/build-python@sha256:...", default_network: deps_only }
  node20:     { image: "squadops/build-node@sha256:...",   default_network: deps_only }
  fullstack:  { image: "squadops/build-fullstack@sha256:...", default_network: deps_only }
```

This is the single pinned source of truth for "what environment did this build run in" (P3), and it is where a new buildable stack is added — a config entry and a sandbox image, never an agent Dockerfile (P1/P4).

### 4.4 Execution flow

1. `qa_test.py` (or any build-capable handler) assembles a `BuildJob` from the materialized files + the detected stack (`cycle/validation.py` already classifies frontend vs backend by file signatures).
2. It calls `ports.build_sandbox.run_build(job)`.
3. The adapter provisions an ephemeral sandbox from the profile's pinned image, mounts the materialized files read-only (or into an ephemeral overlay), applies the network policy and resource limits, runs the command as a non-root user, captures output, collects declared `produced_files`, and tears the sandbox down.
4. `test_runner` maps `BuildResult` → the existing `RunTestsResult` / `BuildCheckResult`, unchanged downstream.

### 4.5 Adapters

- **`DockerBuildSandboxAdapter`** — local dev default; implemented on the existing `ContainerPort` (Docker/Podman). Zero new infra for the laptop stack.
- **`RemoteBuildSandboxAdapter`** — an edge/cloud sandbox service (the SIP-Edge-Deployment-Profile target); stronger isolation (gVisor/Firecracker/ACI), no Docker socket on the agent host.
- **`NoOpBuildSandboxAdapter`** — always returns `ran=False`; the always-inject default so a deployment with no sandbox configured behaves exactly like today's missing-toolchain skip (parity, not a new failure mode).

Selection via the config-driven factory pattern already used for cycle registry / auth / telemetry.

## 5. Migration

1. Land the port, models, `NoOpBuildSandboxAdapter`, and the `DockerBuildSandboxAdapter` behind config (default NoOp → identical current behavior).
2. Move `test_runner.py`'s three `create_subprocess_exec` call sites onto `run_build`, keeping the result shapes. Unit tests assert parity (missing-sandbox → `ran=False`, failing build → non-zero exit surfaced, passing build → green) against a fake `BuildSandboxPort`.
3. Publish the pinned `build-node` / `build-python` / `build-fullstack` sandbox images.
4. Flip the dev stack to `DockerBuildSandboxAdapter`, live-validate a fullstack cycle (frontend build check runs in the sandbox, not the agent).
5. **Retire the toolchain from agent images:** delete the #306 `AGENT_ROLE=qa` Node branch and the pytest-as-runtime entry in `agents/instances/qa/requirements.txt`. Agent images return to runtime-only. This step is the payoff and the regression guard: once removed, a build that needs a toolchain *must* go through the sandbox.

## 6. Security

- Untrusted generated code no longer runs in the agent process (P2). The sandbox has no agent secrets, no DB/queue credentials, an ephemeral FS, resource caps, and a non-root user.
- Network **off by default**; `DEPS_ONLY` scopes egress to the package registries a dependency install needs; `FULL` is opt-in and logged. (Dependency-content trust remains out of scope — §3.)
- The Docker adapter's socket access is a known local-dev tradeoff; the remote adapter exists precisely so production/edge deployments never hand the agent host a Docker socket.

## 7. Open Questions

1. **File transport at scale.** Materialized files inline in `BuildJob` is simple but bounds job size. Do large repos need a content-addressed handoff (object store ref) instead of inline bytes?
2. **Produced-artifact flow.** `produced_files` (a built `dist/`) — does it flow back as an artifact into the run's artifact set, and if so does that belong here or in the artifact-promotion path?
3. **Sandbox reuse vs. per-job ephemerality.** Pure ephemerality is safest; a warm pool is faster. Is `npm install` latency enough to justify a pooled sandbox with a reset contract?
4. **Relationship to `CapabilityExecutor`.** Both dispatch work off-agent. Is the build sandbox a distinct port, or a specialization of the executor with a toolchain profile? (Leaning distinct: the executor dispatches whole *tasks* to agents; this runs a *command* with no agent on the other end.)
5. **Toolchain image ownership.** Who builds/publishes/pins the sandbox images, and does that pipeline live in this repo or the deployment-profile repo?

## 8. Alternatives Considered

- **Bundle toolchains per-role in agent images (status quo, #306 Option 1/2).** Simplest; it is what ships today for QA-Node. Rejected as the long-term model for P1–P4. This SIP does not undo #306 — #306 is the correct interim; this is its exit.
- **A single fat agent image with every toolchain.** Worst of P1 (max bloat on every agent) and P2 (max attack surface in the trust boundary). Rejected.
- **Run builds via the existing `CapabilityExecutor`/ACI queue.** Possible, but that path dispatches full task envelopes to *agents*; a build command has no agent on the far side. Modeling it as its own port keeps the semantics honest (Open Q4).

## 9. References

- #306 — agent image has no Node.js → frontend build check inert (the motivating case)
- #290 / #296 / #303 — frontend build check + vitest lineage
- SIP-0068 Enhanced Agent Build Capabilities; SIP-0071 Builder Role; SIP-0086 Build Convergence Loop
- `ContainerPort` — `src/squadops/ports/tools/container.py`; `CapabilityExecutor` — `src/squadops/ports/capabilities/executor.py`
- `test_runner.py` — `src/squadops/capabilities/handlers/test_runner.py` (the three in-process exec sites this SIP relocates)
- SIP-Edge-Deployment-Profile (remote sandbox adapter target); SIP-Capability-Backed-Agents (toolchain-as-capability)
