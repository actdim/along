# Plan: OpenObserve Telemetry Sink, Orchestrator Tracing, and Named Profiles

Issue: `feat--openobserve-telemetry-sink` (REQ-1..REQ-6).

## Execution Mode
Direct

## Ground rules for the executor
- ASCII only in `.md .py` (no em dashes, no smart quotes, no ellipsis glyphs, no non-ASCII arrows).
- Do not edit projections `.along/ISSUES.md`, `.along/DECISIONS.md`, `.along/CONSTRAINTS.md`, `docs/INDEX.md` by hand.
- Run tests via `python .along/scripts/test.py -q tests/test_<name>.py`.
- Hermetic test fixtures only: temporary directories and isolated environments.

## Facts verified in code (2026-11-14)
- `scripts/alongkit/telemetry/otlp.py`:
  - `OTLPExporter` currently defaults to `http://localhost:4318/v1/traces` without reading `OTEL_EXPORTER_OTLP_*` env variables or repo config.
  - Takes `headers: Optional[Dict[str, str]]`, which can carry `Authorization: Basic ...`.
- `scripts/alongkit/runner/`:
  - `antigravity.py` exists but is omitted from `RUNNER_MAP` in `scripts/alongkit/runner/__init__.py`.
  - `ORCHESTRATOR_RUNTIMES` in `scripts/alongkit/orchestrator.py` lacks `antigravity`.
- `scripts/alongkit/orchestrator.py`:
  - `CrossRuntimeOrchestrator` does not import `Tracer` from `alongkit.telemetry.tracer`.
  - `load_role_config` only looks at legacy `orchestration` section in `along.yaml` without support for named profiles in `.along/orchestration/<name>.yaml`.

## Steps

### Step 1: Formal Specification
Create `docs/topic--multi-runtime-orchestration.md` documenting:
- Orchestration profile schema (`.along/orchestration/<name>.yaml`).
- Modes: `direct`, `team-native`, `cross-runtime`.
- Three-tier resolution cascade (code fallbacks -> repo YAML files -> CLI overrides).
- OpenObserve telemetry integration (endpoint, Basic Auth, semantic conventions, fail-open spooling).

### Step 2: OpenObserve OTLP Exporter Enhancement
Update `scripts/alongkit/telemetry/otlp.py`:
- Read `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` from `os.environ`.
- Add helper to resolve OpenObserve endpoint and Basic Auth credentials from repository configuration or environment.
- Add unit tests in `tests/test_telemetry_otlp.py` asserting environment and config header resolution.

### Step 3: Register Antigravity Runner
Update:
- `scripts/alongkit/runner/__init__.py`: Add `"antigravity": AntigravityRunner` to `RUNNER_MAP`.
- `scripts/alongkit/orchestrator.py`: Add `"antigravity"` to `ORCHESTRATOR_RUNTIMES`.

### Step 4: Named Orchestration Profile Loader
Create `scripts/alongkit/orchestration_profiles.py`:
- Load named profiles from `.along/orchestration/<name>.yaml`.
- Provide default in-memory profiles (`direct`, `team-native`, `cross-runtime`).
- Schema validation for roles, runtimes, timeouts, and env passthroughs.
- Integrate into `scripts/alongkit/orchestrator.py` via `load_role_config(repo_root, profile=...)`.

### Step 5: Instrument CrossRuntimeOrchestrator with Tracer
Update `scripts/alongkit/orchestrator.py`:
- Initialize `Tracer` in `CrossRuntimeOrchestrator.__init__`.
- Emit root agent run span `along.orchestrator.run`.
- Emit child spans for `scout`, `architect`, `step`, and `reviewer` phases with runtime and exit code metadata.
- Record gate denials, retry events, and step outcomes as Span Events.
- Ensure fail-open behavior: telemetry errors do not interrupt or fail the orchestration loop.

### Step 6: Automated Tests
- `tests/test_orchestration_profiles.py`: Test profile resolution, schema validation, and CLI overrides.
- `tests/test_telemetry_otlp.py`: Test OpenObserve endpoint and Basic Auth header parsing.
- `tests/test_orchestrator_telemetry.py`: Test `CrossRuntimeOrchestrator` execution generating full OTel span tree.

### Step 7: Sanitize and Verification
- Run test suite: `python .along/scripts/test.py -q`.
- Run typography check: `python scripts/along_exec.py sanitize`.
