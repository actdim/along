# Plan: Cursor Agent and Rules Integration

Issue: `feat--cursor-agent-and-rules-integration`
Execution Mode: Role-Based

## Current state

- Cursor already has a generic runtime hook adapter and `.cursor/hooks.json` installer in `scripts/alongkit/hooks/config.py`; hook install supports `--runtime cursor`.
- Along installers currently treat Cursor as an attribution-only target. Cursor is not in `install.PROVIDERS`, and `configure_mcp.py` has no Cursor home/provider option.
- Cursor's runtime capability matrix still describes Cursor as rules-only with no runtime hooks, so its declared capability does not match the implemented hook installer.
- `along-init` currently scaffolds shared `AGENTS.md` and `.along/` context, but no Cursor project rule.
- `along-kb-search` is a CLI skill, not a registered MCP server. Existing MCP registration exposes `code-review-graph` and `along-webdev`; do not promise a nonexistent `along-kb-search` MCP endpoint.

## Goal

Give Cursor Agent first-class, non-destructive Along onboarding through a thin project rule that points to canonical repository guidance, accurately represent Cursor's supported hooks and advisory enforcement, and document the supported setup. Add Cursor MCP registration only for an Along server that exists and after its transport and configuration are verified.

## Steps

1. **Confirm integration contract**
   - Verify the supported Cursor rule frontmatter and project/global MCP configuration against current Cursor documentation.
   - Decide from current Cursor hook behavior and Along's generic adapter whether hook support is a supported integration or a best-effort/experimental capability. Keep actual enforcement claims aligned with runtime behavior.
   - Limit MCP work to existing Along MCP servers; explicitly defer `along-kb-search` MCP exposure unless a server implementation is in scope.
2. **Add project rule scaffolding**
   - Extend the `along-init` scaffold path to create `.cursor/rules/along.mdc` with valid Cursor frontmatter and concise pointers to `AGENTS.md`, `docs/INDEX.md`, and the Along CLI workflow.
   - Make creation idempotent and create-only for an existing user-owned file; preserve unrelated files and rules under `.cursor/`.
3. **Align installation and capability reporting**
   - Reconcile `install.ps1` / `install.sh`, Cursor hook setup, and `scripts/alongkit/runtime.py` so documented targets and installed configuration agree.
   - Keep user-level configuration changes scoped to verified, documented paths and preserve unknown settings.
   - Add Cursor to `configure_mcp.py` only if registering an existing server is useful and its `.cursor/mcp.json` contract is covered by tests; otherwise remove that promise from this issue's scope.
4. **Update documentation**
   - Update the setup guide, runtime capability matrix, and relevant README/provider overview.
   - Distinguish Cursor's instruction rules from mechanical hook enforcement and name any unsupported capabilities plainly.
5. **Verify**
   - Add hermetic tests for rule creation, valid frontmatter, idempotence, preservation of existing rules, runtime capability reporting, and MCP configuration only if implemented.
   - Run the affected scaffold, hook/runtime, installer, and documentation checks; inspect generated diffs for accidental writes outside Along-owned files.

## Acceptance criteria

- `along-init` generates a valid `.cursor/rules/along.mdc` that points to canonical shared guidance.
- Re-running init preserves an existing `.cursor/rules/along.mdc` and all unrelated Cursor configuration.
- Cursor runtime capability and enforcement reporting match the actual supported hook path; prose does not claim hard enforcement where it is advisory.
- Installation docs accurately explain how to enable Cursor integration and what remains advisory.
- Cursor MCP registration is included only for an existing, supported Along MCP server, with a verified config contract and preservation tests; no `along-kb-search` MCP endpoint is claimed without implementation.
- Relevant tests and documentation checks pass.

## Scope notes

This crosses scaffold generation, runtime capability reporting, installers, and documentation, so implementation should use the Along role-based step loop. Treat optional Cursor MCP registration as a design decision within step 1; do not add a new MCP server as incidental scope.

## Revision 2 (2026-11-25T10:51:25Z, along plan revise)

Reason: Step 1 contract verification: lock Cursor MDC frontmatter, existing-server MCP scope (~/.cursor/mcp.json), skills (~/.cursor/skills), beforeSubmitPrompt hook, and truthful advisory-by-default/optional-hooks runtime reporting

# Plan: Cursor Agent and Rules Integration

Issue: `feat--cursor-agent-and-rules-integration`
Execution Mode: Role-Based

## Requirement Traceability Matrix (STE-CNL)

- **REQ-1 (Contract Confirmation)**: The integration design MUST align Cursor project rules (`.cursor/rules/along.mdc`), existing Along MCP servers (`code-review-graph` opt-in/clean, `along-webdev`), skills (`~/.cursor/skills/along-*`), attribution (`~/.cursor/cli-config.json`), and hook capabilities (`preToolUse`, `postToolUse`, `stop`, `beforeSubmitPrompt`, `RUNTIME_HOOK_NARROWINGS['cursor']`) without adding nonexistent `along-kb-search` MCP endpoints or editing `write_policy: manual` docs.
- **REQ-2 (Project Rule Scaffolding)**: `along_init.py` and `alongkit.scaffold` MUST scaffold `.cursor/rules/along.mdc` via `write_if_missing` with valid Cursor MDC frontmatter (`description`, `globs`, `alwaysApply: true`) pointing to `AGENTS.md`, `.along/ISSUES.md`, `along kb-search` / `docs/INDEX.md`, and `along` CLI workflows, MUST support `--dry-run`, and MUST NOT overwrite an existing `.cursor/rules/along.mdc` or unrelated `.cursor/` files.
- **REQ-3 (Installers & MCP Parity)**: `alongkit.install` (`PROVIDERS`, `FOLDER_PROVIDERS`, `Homes`, `mcp_target`), `install_manifest.py`, `configure_mcp.py`, `along_update.py`, `install.ps1`, and `install.sh` MUST support `cursor` (`~/.cursor/skills`, `~/.cursor/mcp.json` verified `mcp_servers_json` layout for existing servers, attribution via `~/.cursor/cli-config.json`) while keeping Cursor hooks opt-in (`along hook install --runtime cursor`).
- **REQ-4 (Runtime & Hook Alignment)**: `alongkit.runtime` (`RUNTIME_MATRIX['cursor']`, `along_hooks_registered`, `enforcement_level`) and `alongkit.hooks.config` (`get_cursor_hook_manifest` adding `beforeSubmitPrompt`) MUST reflect Cursor skills + optional hooks accurately, preserving `ADVISORY` when no hooks are installed and reporting `RUNTIME_HOOK_NARROWINGS['cursor']` in `along doctor`.
- **REQ-5 (Documentation Parity)**: `README.md`, `AGENTS.md` (if needed), `docs/topic--setup-and-workflow.md`, `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--architecture.md`, `docs/topic--cli-reference.md`, `skills/along-init/SKILL.md`, and `skills/along-update/SKILL.md` MUST describe Cursor rule scaffolding, global skill/MCP targets, and advisory-vs-optional-hook enforcement truthfully, with `along kb-sync` provenance synced.
- **REQ-6 (Verification)**: Hermetic tests MUST verify `.cursor/rules/along.mdc` scaffolding/idempotence/preservation, installer parity (`install.ps1`/`install.sh`/`planned_files`), `~/.cursor/mcp.json` registration/preservation, `beforeSubmitPrompt` + `runtime.py` capability/enforcement reporting, and the full test suite + `along sanitize` + `along hook verify --strict` + `along kb-sync --check --strict` MUST pass.

## Steps

1. **Confirm integration contract** (`REQ-1`): Verify `.mdc` frontmatter, `~/.cursor/mcp.json` (`mcp_servers_json`), `~/.cursor/skills`, `beforeSubmitPrompt` hook shape, and `RUNTIME_HOOK_NARROWINGS['cursor']`; lock MCP scope to existing servers (`code-review-graph`, `along-webdev`).
2. **Add project rule scaffolding** (`REQ-2`): Add Cursor rule template/rendering in `scripts/alongkit/scaffold.py` and invoke create-only scaffolding in `scripts/along_init.py` (plus `.cursor` awareness in `scripts/alongkit/repo.py` / `containment.py` / `sanitizer.py` where safe).
3. **Align installation and capability reporting** (`REQ-3`, `REQ-4`): Add `cursor` to `scripts/alongkit/install.py`, `scripts/install_manifest.py`, `scripts/configure_mcp.py`, `scripts/along_update.py`, `install.ps1`, `install.sh`, `install.bat`; align `scripts/alongkit/runtime.py` and `get_cursor_hook_manifest()` in `scripts/alongkit/hooks/config.py`.
4. **Update documentation** (`REQ-5`): Reconcile `README.md`, `docs/topic--setup-and-workflow.md`, `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--architecture.md`, `docs/topic--cli-reference.md`, and affected `SKILL.md` / KB provenance without touching `write_policy: manual` files.
5. **Verify** (`REQ-6`): Update and add hermetic tests (`test_scaffold_init.py`, `test_installers.py`, `test_skills_and_scripts.py`, `test_hooks_generic.py`, `test_runtime_detection.py`), run full test suite, `along sanitize`, `along hook verify --strict`, and `along kb-sync --check --strict`.
