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
