# Changelog

All notable changes to this project, newest first.

## v4.9.2 - 2026-11-24

- chore: Commit versioning decoupling and pending issue files (refs #decouple-protocol-and-toolchain-versioning)
- fix: Fix DSH tool-name map, global configPath/is_global, ASK capability, and DSH skills updater support (refs #dsh-tool-name-map-and-ask-capability)
- docs: Deduplicate commit entries in CHANGELOG and release engine (refs #changelog-deduplication)
- docs: Reconcile protocol counts, VISION version, and extras across documentation (refs #reconcile-protocol-counts-and-extras)
- feat(runner): support positional prompt delivery and token cache ratio observability for deepseek runner (refs #opencode-deepseek-cache-configuration-audit)
- debt(tests): deduplicate version bump tests and harden contract assertions across suite (refs #test-suite-paper-compliance-cleanup)
- fix(opencode): isolate node plugin contract test in tempdir to ensure test hermeticity (refs #opencode-plugin-test-hermeticity)
- feat: implement umbrella session hierarchy, smart dirty tree start handling, and submodule protocol auto-commit (refs #session-hierarchy-and-submodule-automation)
- fix: Fix engine wrap atomicity, gate reference integrity, and multi-subproject session friction across lifecycle, gates, and repo engines (refs #engine-atomicity-and-gate-resilience)
- feat(harness): create local LLM runtime harness epic and child work packages (refs #local-llm-runtime-harness)
- feat: Implement self-contained offline NL-to-WebDev step compiler and runner (refs #webdev-local-llm-engine)
- feat: Implement DeepSeek Harness headless runner and orchestration adapter (refs #deepseek-runtime-adapter)
- feat: add DeepSeek Harness adapter, installer target, and cordis bridge (refs #deepseek-harness-bridge)
- fix(webdev): prevent dual browser windows, handle SIGINT cleanly, and support CMD step shortcuts (refs #webdev-session-ux-improvements)

## v4.9.1 - 2026-11-21

- fix(webdev): session browser creation, thread affinity, and doctor checks (refs #webdev-session-create-browser-helper)
- fix(opencode): guard undefined output in shell hooks and align runner CLI contract (refs #opencode-shell-env-runner-fix)
- feat(webdev): browser engine, semantic locators, redaction, in-page probes, and diagnostics capture (refs #along-webdev-runner)
- feat(kb-sync): doc provenance drift CLI and commit-time verification gate (refs #provenance-drift-gate)
- feat: Preventive Git auto-merge protection, update propagation and stage-aware conflict resolution (refs #git-automerge-protection-and-semantic-merge)
- fix(gates): count untraced changes at Stop with one rule (refs #stop-gate-empty-writes-fallback)
- fix(ci): normalize line endings in opencode hooks and configure gitattributes text defaults (refs #windows-ci-line-endings)

## v4.9.0 - 2026-11-14

- fix(gates): resolve Stop gate false positives and add trace-backed denials (refs #stop-gate-false-positives)
- feat: implement named orchestration profiles, OpenObserve OTLP telemetry sink, and orchestrator tracing (refs #openobserve-telemetry-sink)
- feat: Implement issue-scoped verify policy with plan-approval snapshots and coverage-aware test reuse (refs #issue-test-scoping-policy)
- docs(issues): file provenance drift gate issue with approved plan (refs #provenance-drift-gate)
- docs(issues): file DITA topic paragraph and stale provenance hash review (refs #dita-topics-and-drift)
- docs(kb): align kb-search docs with engine; add authoring and progressive-disclosure sections (refs #kb-search-docs-accuracy)
- docs(comparisons): align LLM-Wiki stance and kb-search latency claim with measured behavior (refs #system-comparisons)
- feat(feedback): implement GitHub PR transport with gh CLI and web fallback (refs #feedback-github-pr-transport)
- refactor: Point budget.py comment at .along/PROTOCOL.md (leftover from bug--protocol-leaks-into-docs) (refs #stale-protocol-path-comment)
- fix(opencode): v2 plugin definition, complete lifecycle coverage and argument normalization (refs #opencode-runtime-v2-hardening)
- feat: opencode runtime hooks integration and multi-subproject issue discovery (refs #opencode-runtime-integration)
- chore(docs): sync index projections after v4.8.1 release (refs #bump-minor-version-and-reconcile-protocol-references)

## v4.8.1 - 2026-11-11

- fix(ci): hermetic sys.path in test_cli_chdir for uv no-project (refs #ci-test-matrix-workflow)
- feat(drafts): first-class untracked issue drafts with promotion and doctor hygiene (refs #issue-drafts-lifecycle)
- feat(hooks): emit early PreToolUse notice for raw test runners when lifecycle hook exists (refs #early-raw-runner-warning)
- feat(lint): validate existence of specified paths and return code 2 on missing files (refs #lint-arbitrary-paths)
- feat(planscope): approved plan grants Files to change as write scope (refs #plan-grants-write-scope)
- feat(worktree): harden lifecycle with wrap guards, teardown, and doctor audits (refs #worktree-lifecycle-hardening)
- feat(subproject): support top-down children binding and cross-context authorization (refs #top-down-umbrella-subproject-binding)
- fix(lifecycle): do not blame dirty files claimed by in-progress issues on wrapped issues (refs #start-dirty-check-misattribution)
- fix(subproject): map issue folder files to issue key in subproject boundary (refs #subproject-boundary-issue-folder-files)
- fix(gates): resolve retried denials and ack across issues (refs #gates-ack-cross-issue-denials)
- docs: finalize knowledge base index and llms-full synchronization (refs #release-v4-8-0)

## v4.8.0 - 2026-11-10

- chore: synchronize dependency registry, milestones, and issue tracking (refs #release-v4-8-0)
- feat(dashboard): integrate @actdim/ui-core runtime dependencies, tokens and component tests (refs #integrate-actdim-ui-core-runtime)
- refactor(errors): centralize domain exceptions hierarchy and error boundary (refs #domain-exceptions-and-error-flow)
- perf(test): add integration test registry and parallel xdist execution support (refs #optimize-test-suite-execution-time)
- fix(test): harden hermetic suite against windows git stat-cache flips (refs #hermetic-suite-flaky-git-cache)
- fix(hooks): resolve cli_safety false positives and detection gaps (refs #simplify-cli-safety-gate-and-predicates)
- refactor(cli): move _handle_chdir_options into dependency-free cliargs module (refs #refactor-cli-chdir-common)
- feat(test): add pytest runner support and fine-grained test runner filtering (refs #pytest-support-and-test-runner-filtering)
- fix(worktree): handle POSIX and root-relative paths in inspect_git_dir on Windows under Python 3.13 (refs #ci-worktree-python313-posix-path)

## v4.7.0 - 2026-11-06

- fix(lifecycle): prevent UnboundLocalError when updating already-done issue in wrap (refs #verify-worktree-env-readiness-hardening)
- fix(lifecycle): make --phase imply --keep-open and support flexible phase formats (refs #partial-session-wrap) (refs #verify-worktree-env-readiness-hardening)
- fix(cli): support global -C and --chdir options in alongkit.cli entrypoint (refs #cli-global-chdir)
- feat(gates): support subagent attribution for gate denials and unresolved reporting (refs #gate-denials-subagent-attribution)
- feat(gates): support unstaged linting and subproject protocol version skew doctor audit (refs #lint-worktree-and-doctor-subprojects)
- feat(entities): implement cross-repo and submodule entity references with path qualifiers (refs #cross-repo-entity-references)
- feat(lifecycle): implement batch plan approval and status: draft rejection (refs #plan-approve-batch)
- fix(gates): narrow entity-deletion-protection to canonical entity paths and plan.md (refs #entity-deletion-protection-path-scope)
- fix(hooks): prevent worktree-env-readiness false positives on submodules and allow recovery commands (refs #worktree-env-readiness-submodules)

## v4.6.1 - 2026-11-05

- fix: Relocate agent protocol to .along/PROTOCOL.md and exclude from public docs (refs #protocol-leaks-into-docs)
- fix(ci): fix executable permissions in docker test harness and update node to 24 (refs #autonomous-container-build-and-firewall)

## v4.6.0 - 2026-11-01

- docs(entities): register autonomous execution, team worktree, and diagnostics roadmap issues
- docs(dashboard-ui): sync topic index date header
- feat(gates): test-inert path classification, ignore_paths, and pre-existing failure baseline (refs #test-gate-scope)
- fix(autonomous): packaging cleanup, unified telegram helper, and env/brief hardening (refs #autonomous-mvp-minor-defects)
- fix(env): autonomous container build and fail-closed firewall (refs #autonomous-container-build-and-firewall)
- fix(runner): ground runtime adapters in verified CLI contracts and harden supervisor (refs #runtime-adapters-invented-cli-contracts)
- fix(daemon): classify telegram poll errors, jitter backoff and bound 409 conflict window (refs #telegram-poll-error-classification)
- chore(along): update dashboard-ui docs index projection
- fix(hooks): close autonomous gate residual holes and escalation overrides (refs #autonomous-gate-residual-holes)
- docs: record Telegram bot ownership and update transport design (refs #agent-execution-gate-telegram)

## v4.5.4 - 2026-10-28

- fix(daemon): keep worktree branches, persist the Telegram offset, verify PID identity, run tasks off the poll loop (refs #runner-daemon-lifecycle-safety)
- fix(orchestrator): fail closed on missing or invalid reviews; exclusive claims; read-only dry run; safe handoff ids (refs #orchestrator-review-fail-open)

## v4.5.3 - 2026-10-23

- fix(docs): declare text language on the isolation diagram fence (CI code-fence-language gate) (refs #ci-fence-language-missing)
- fix(hooks): ExitPlanMode capture reads the plan from tool_response.plan or the plan file, not only tool_input.plan (refs #exit-plan-text-not-captured)
- fix(wrap): auto-commit and uncommitted-work warning include the moved issue folder and the ticket's old path (refs #wrap-misses-moved-issue-folder)
- feat(plans): issue plans live with the ticket and can be approved ahead of along start; plan_status approved is set only by the CLI (approval log, gate guard, Stop check); along plan revise/rework; orchestrator runs an approved plan instead of its architect (refs #pre-approved-plans)
- fix(gates): plan gate accepts only CLI-written approval; restore session ownership check (refs #plan-approval-self-approval-bypass)
- feat(daemon): implement VPS runner daemon and Telegram ingress loop (refs #vps-runner-daemon)
- feat(orchestration): implement cross-runtime supervisor orchestrator for tiered multi-agent loops (refs #cross-runtime-supervisor-orchestrator)
- feat(runtime): implement multi-runtime adapters for Claude Code, Codex, OpenCode, and generic CLI (refs #agent-runtime-adapters-claude-codex-opencode)
- feat(gates): implement autonomous gate profile and deterministic decision engine (refs #autonomous-gate-profile)
- feat(handoff): implement cross-runtime handoff entities, run records, claims, and along brief (refs #cross-runtime-handoff-entities)
- feat(docker): implement along env isolated Docker environment CLI and assets (refs #isolated-environment-docker)
- refactor(core): define along core and modular extras architecture (refs #along-core-extras-split)
- docs(spike): assess headless agent runtimes on Linux and update downstream architecture (refs #headless-runtimes-on-linux)

## v4.5.2 - 2026-10-23

- feat: Gate denials are ledger events settled by retry, approval or user-verified ack; Stop gate unresolved_gate_denial; along gates denials/ack; closeout, wrap and issue done refuse unsettled denials (--force-reason under bypass rules); ADR-2026-10-23--gate-denials-are-ledger-events (refs #anti-silent-fallback-gate)
- chore: Supersede automated-ui-screenshots with along-webdev-runner, add along-report-engine and along-storage-providers issues, refresh milestone progress (refs #along-webdev-runner)
- feat(ste): implement Controlled Natural Language specification engine and issue scaffold (refs #ste-cnl-specification-engine)
- docs: reconcile v4.5.1 release history, milestone, and Step 16 migration scope

## v4.5.1 - 2026-10-21

- chore: setup v4.5.1 hotfix milestone and carry over v4.5.2
- fix: Quote description string in along-issue-sync frontmatter to fix YAML parsing in Antigravity (refs #along-issue-sync-frontmatter-quotes)
- refactor: Slim the entity model: spike becomes an issue type, risk and checklist types retire (migration Step 16 converts RISKS/SPIKES/CHECKLISTS with backup and reference rewrite), session logs keep attributed paths as files: front matter without plan or file-table copies, session gc archives blackboards of closed issues, nested contexts get no empty VISION/GLOSSARY, ADR-2026-10-19--entity-model-slimmed (refs #entity-model-slimming)
- fix: Wrap and session close commit engine-refreshed files (docs/topic--along-protocol.md, AGENTS.md changed only inside managed blocks); migration Step 15 removes retired circuit-breaker and tool-classifier artifacts with backup (refs #wrap-misses-engine-writes)
- chore: Doc sweep for the AGENTS.md core + protocol reference split, kb-sync per-context slug fix, global reinstall, release v4.5.0 tagged and pushed (refs #release-v4-5-0)

## v4.5.0 - 2026-10-18

- fix(kb-sync): treat engine-written per-context slugs (dependencies, along-protocol) as standard so strict release gate does not flag them as cross-project collisions; repin reviewed source hashes; hermetic rule now points to the protocol reference (refs #release-v4-5-0)
- refactor: Slim AGENTS.md managed block to a 4.9 KB core (state locations, issue anchoring, gate list, judgment rules); full procedure moved to managed on-demand docs/topic--along-protocol.md rendered by along init/update; marker-based profile sections; update honours active profile (refs #agents-md-core-slimming)
- refactor: DECISIONS.md board as a sliding window of the newest active ADRs with compact superseded lines (refs #decisions-board-sliding-window)
- refactor: Gates judge results, not commands: remove tool-nature classifier, circuit breaker and fast_retrieval; plan gate checks file targets and end-of-turn git status; narrow destructive_command gate; content rules commit-time via along lint; audit target field and loop stats (refs #gate-simplification)
- docs: Plan autonomous multi-runtime MVP: epic, headless-runtimes spike, Docker-now gVisor-later ADR, gate and entity simplification debts, handoff entities, re-scoped daemon/Telegram/orchestrator issues (refs #autonomous-multi-runtime-mvp)
- refactor: Prune and limit migration backups in .along (refs #migration-backup-retention-and-cleanup)
- refactor: Decomposed along_exec.py (2128 to 394 lines) and alongkit/entities.py (2453 lines) into modular command and entity subsystems with full backward compatibility (refs #split-along-exec-and-entities)
- fix: Improve session-record-append-only gate for deletions, renames, and subproject consolidation (refs #session-record-gate-lifecycle-resilience)
- chore: sync dependency registry and dashboard KB projections (refs #migrate-to-actdim-ui-core)
- docs: Sync recent features documentation across CLI reference and lifecycle guides (refs #sync-recent-features-documentation)
- docs: Document Monorepo Workspaces vs Git Submodules in release cycles (refs #monorepo-submodule-release-workflow)

## v4.4.16 - 2026-10-16

- feat: Implement issue stub validation, lifecycle quality gates, and doctor audit (refs #issue-stub-validation-and-lifecycle-gates)
- debt(dashboard-ui): consolidate subproject context into root repository (refs #consolidate-dashboard-ui-subproject)
- feat: atomic wrap commit, clean start guard, and CLI black-box invariance (refs #atomic-wrap-commit-and-start-guard)

## v4.4.15 - 2026-10-16

- docs: sync kb index and register backlog feature anti-silent-fallback-gate (refs #anti-silent-fallback-gate)
- refactor(dashboard-ui): align with dynstruct and msgmesh conventions
- feat(lifecycle): implement wrap checklist verification, prune amnesty, and zombie stub detection (refs #kb-integrity-and-wrap-verification)
- debt(vision): decouple roadmap into strategic horizons and relax tests (refs #vision-roadmap-decoupling)

## v4.4.14 - 2026-10-14

- fix(ci): cross-os toolnature paths, code-fence tag and secret pragma (refs #ci-linux-toolnature-and-secrets)
- chore(dashboard-ui): sync dashboard dependencies and milestone projections (refs #bump-dashboard-deps)
- fix: along-dash-missing-dashboard (refs #along-dash-missing-dashboard)
- fix: session-scanner-prompts-dir-leak (refs #session-scanner-prompts-dir-leak)
- feat: bounded-prompt-footprint-gate (refs #bounded-prompt-footprint-gate)
- chore: dashboard-docs-kb-alignment (refs #dashboard-docs-kb-alignment)
- feat: doc-routing-compliance-gate (refs #doc-routing-compliance-gate)
- refactor: remove-static-dashboard-data-json-export (refs #remove-static-dashboard-data-json-export)

## v4.4.13 - 2026-10-14

- feat: gate-strictness-profiles (refs #gate-strictness-profiles)
- feat(session): structured blackboard state machine and deterministic patch merging (refs #structured-blackboard-state-machine)

## v4.4.12 - 2026-10-13

- feat(orchestrator): add cross-runtime supervisor orchestrator issue (refs #cross-runtime-supervisor-orchestrator)
- docs(wiki): ground topic-based documentation architecture (refs #ground-topic-based-docs)
- fix(security): consume destructive confirmation on PreToolUse and eliminate classifier false positives (refs #destructive-pre-tool-consumption-and-false-positives)
- fix(security): harden destructive authorization, doc-manual-lock, git -c allowlist, and env stripping (refs #destructive-authorization-and-lock-hardening)
- fix(core): restore external commands, implement plan confirmation flags, and harden classifiers (refs #post-audit-regressions-and-alignment)
- fix(core): resolve audit findings across gates, toolnature, bootstrap, and docs (refs #post-audit-core-hardening)
- docs(claims): benchmark kb-search, ground performance metrics, and neutralize tone (refs #unverified-performance-claims)
- docs(rules): document prohibition of ad-hoc shell code probing (refs #anti-pattern-shell-code-probing)
- docs(comparisons): document paradigm 7 comparing conversational history vs explicit state (refs #state-centric-execution-and-skill-state-comparison)
- docs(vision): refresh scope, roadmap, bounded non-goals, and provenance (refs #vision-md-refresh)
- refactor(cli): migrate along_exec to modular commands with argparse validation (refs #along-exec-argparse-migration)
- feat(dev): automated local dev environment setup and editable install (refs #dev-environment-setup-and-editable-install)
- feat(bootstrap): support inline -c invocation in ensure_deps (refs #bootstrap-resilience-and-subcommand-proxying)
- debt(protocol): cleanup plan approval wording, literal kb-search, and quiet test runner (refs #protocol-friction-cleanup)
- feat(context): implement progressive disclosure, catalog toc, and issue contracts (refs #progressive-disclosure-and-context-scaling)
- feat(kb-search): exclude archived issues and session logs by default (refs #kb-search-archive-scope-default)
- feat(hooks): classify tools by nature with versioned layered rules (refs #tool-nature-classification)
- feat(release): check CI status of released commit before version bump (refs #release-ci-precondition-check)
- feat(security): scrub secrets in hooks audit logs and isolate diagnostics (refs #secret-scrubbing-in-hooks-and-diagnostics)
- fix(worktree): refuse worktree creation on cross-OS mounted repositories (refs #worktree-cross-os-mount-guard)
- fix(entities): prevent entity file deletion and support multi-issue supersede (refs #uncommitted-issue-deleted-without-trace)
- fix(lifecycle): skip wrap test gate for docs and along-only changes (refs #wrap-docs-only-test-skip)

## v4.4.11 - 2026-10-12

- chore(sync): reconcile entity projections and knowledge base index (refs #wrap-docs-only-test-skip)
- fix(git): enable push.followTags in git setup and add doctor checks for unpushed release tags (refs #release-tags-not-pushed)
- fix(lifecycle): auto-generate history entry on wrap fallback and add along history append (refs #history-append-blocked-after-wrap)
- fix(install): purge default MCP auto-registration from installers (refs #mcp-installer-cleanup-serve-arg)
- chore(release): close out v4.4.10 release task and glossary terms (refs #release-v4-4-10)

## v4.4.10 - 2026-10-11

- fix(gates): cross-context entity refs, test policy, transactional wrap, path-based subproject boundary, plan approval check, quote-aware CLI safety, scoped stop hook, AGENTS.md budget split; gate tiers, recorded bypasses and gate stats (refs #field-report-fixes)
- feat(merge): test-gated code conflict resolution and pre-merge predictor (refs #test-gated-code-merge-pipeline)

## v4.4.9 - 2026-10-10

- refactor: constraints-superseded-adr-filtering (refs #constraints-superseded-adr-filtering)
- chore(along): projections after closing out bug--along-install-marker-ambiguous, bug--archive-drops-research-md, bug--breaker-trips-on-test-output, bug--ci-windows-closeout-short-paths, bug--cli-entity-sync-defects, bug--inquiry-readonly-commands-blocked, bug--lexical-path-root-resolution, bug--lifecycle-test-false-pass, bug--plan-gate-blocks-help, bug--runtime-plan-dir-containment, bug--subcommand-help-as-argument, bug--subproject-model-overdetection, bug--update-maintenance-friction, bug--wrapped-work-left-uncommitted, debt--canonical-windows-paths, debt--constraints-superseded-adr-filtering, feat--docs-semantic-conflict-resolution, feat--test-gate-cost-reduction (refs #along-install-marker-ambiguous) (refs #archive-drops-research-md) (refs #breaker-trips-on-test-output) (refs #ci-windows-closeout-short-paths) (refs #cli-entity-sync-defects) (refs #inquiry-readonly-commands-blocked) (refs #lexical-path-root-resolution) (refs #lifecycle-test-false-pass) (refs #plan-gate-blocks-help) (refs #runtime-plan-dir-containment) (refs #subcommand-help-as-argument) (refs #subproject-model-overdetection) (refs #update-maintenance-friction) (refs #wrapped-work-left-uncommitted) (refs #canonical-windows-paths) (refs #constraints-superseded-adr-filtering) (refs #docs-semantic-conflict-resolution) (refs #test-gate-cost-reduction)
- chore: changes shared by bug--breaker-trips-on-test-output, bug--lexical-path-root-resolution, bug--lifecycle-test-false-pass, bug--subproject-model-overdetection, bug--wrapped-work-left-uncommitted, debt--canonical-windows-paths, feat--test-gate-cost-reduction (refs #breaker-trips-on-test-output) (refs #lexical-path-root-resolution) (refs #lifecycle-test-false-pass) (refs #subproject-model-overdetection) (refs #wrapped-work-left-uncommitted) (refs #canonical-windows-paths) (refs #test-gate-cost-reduction)
- chore: changes shared by bug--lifecycle-test-false-pass, bug--runtime-plan-dir-containment, bug--subproject-model-overdetection, bug--wrapped-work-left-uncommitted, feat--test-gate-cost-reduction (refs #lifecycle-test-false-pass) (refs #runtime-plan-dir-containment) (refs #subproject-model-overdetection) (refs #wrapped-work-left-uncommitted) (refs #test-gate-cost-reduction)
- chore: changes shared by bug--cli-entity-sync-defects, bug--subproject-model-overdetection, bug--update-maintenance-friction, debt--canonical-windows-paths, debt--constraints-superseded-adr-filtering (refs #cli-entity-sync-defects) (refs #subproject-model-overdetection) (refs #update-maintenance-friction) (refs #canonical-windows-paths) (refs #constraints-superseded-adr-filtering)
- chore: changes shared by bug--ci-windows-closeout-short-paths, bug--wrapped-work-left-uncommitted, debt--canonical-windows-paths (refs #ci-windows-closeout-short-paths) (refs #wrapped-work-left-uncommitted) (refs #canonical-windows-paths)
- fix: archive-drops-research-md (refs #archive-drops-research-md)
- chore: changes shared by debt--canonical-windows-paths, feat--docs-semantic-conflict-resolution (refs #canonical-windows-paths) (refs #docs-semantic-conflict-resolution)
- fix: inquiry-readonly-commands-blocked (refs #inquiry-readonly-commands-blocked)
- feat: docs-semantic-conflict-resolution (refs #docs-semantic-conflict-resolution)
- fix: wrapped-work-left-uncommitted (refs #wrapped-work-left-uncommitted)
- fix: plan-gate-blocks-help (refs #plan-gate-blocks-help)
- feat(gates): reduce test gate cost via tree-hash reuse and scoped doc tests (refs #test-gate-cost-reduction)

## v4.4.8 - 2026-10-08

- docs(issues): track canonical path gate expansion and record session (refs #canonical-path-gate-expansion)
- fix: preserve lexical path form in root discovery and installation while maintaining semantic canonicalization (refs #lexical-path-root-resolution)
- debt: enforce canonical path resolution across repository engines and test fixtures (refs #canonical-windows-paths)
- fix(ci): resolve windows 8.3 short paths against canonical git top in closeout engine (refs #ci-windows-closeout-short-paths)
- docs(issues): file v4.5.0 fixes from the 2026-10-07 closeout: archive-drops-research-md, wrapped-work-left-uncommitted, history-append-blocked-after-wrap, uncommitted-issue-deleted-without-trace, plan-gate-blocks-help, inquiry-readonly-commands-blocked, release-ci-precondition-check, protocol-friction-cleanup; test-gate-cost-reduction gains REQ-6 (version-only changes keep a green run) and moves to v4.5.0 (refs #file-v4-5-fixes-update)
- chore(release): wrap release-v4-4-7 closeout: session log, task moved to done, board (refs #release-v4-4-7)

## v4.4.7 - 2026-10-07

- docs(issues): file feat--test-gate-cost-reduction (Stop gate reuses green runs by tree hash, scoped doc tests under count_docs, suite speed); refine feat--tool-class-model, feat--tool-nature-classification, feat--agent-run-protocol-and-observability (refs #test-gate-cost-reduction)
- fix: land the 2026-10-06/07 session batch: stop gates no longer deadlock on the breaker and the breaker ignores test output; install marker disambiguated; CLI entity sync defects; lifecycle test false pass (executed test count, doc edits via count_docs); runtime plan dir containment; subcommand --help no longer taken as an argument; subproject boundary is a nested git or explicit init (ADR-2026-10-06); update maintenance commands pass the plan gate; Along installation is state, not AGENTS.md (ADR-2026-10-07); session logs, done issues and projections; orphan blackboards archived into session logs (refs #stop-gates-breaker-deadlock #breaker-trips-on-test-output #along-install-marker-ambiguous #cli-entity-sync-defects #lifecycle-test-false-pass #runtime-plan-dir-containment #subcommand-help-as-argument #subproject-model-overdetection #update-maintenance-friction) (refs #release-v4-4-7)
- feat(session): close parallel sessions in one step: session event ledger per issue (attribution of edits, test runs, plans, approvals; telemetry projection per ADR-2026-10-05--session-event-ledger-feeds-telemetry); test runs reused by working-tree hash; readiness via along session list; closeout approval (along plan approve --closeout); along session close (tests once, wrap, commits by attribution, push once, resumable); along issue reopen; doctor reports stale bindings and unbound work (refs #parallel-session-closeout)
- fix(session): session record captured and never lost: approved plan recorded in plan.md (ExitPlanMode tool_input.plan, plan approve --plan-file, scaffold refused, revisions kept); direct-mode execution trace from hooks and Along commands (edits, test results, gate denials, approvals, phase and step changes, bounded); one archive path for wrap, scratch purge and issue done, purge after the transaction commit; wrap-before-stop per completed issue; append-only Blackboard Record gate (git, ci, along commit); doctor reports orphan blackboards (refs #session-records-not-captured)
- fix(hooks): narrow the commit gate after wrap to completion tokens: along wrap leaves a token to the session whose plan for the slug was approved; along commit -i <slug> passes the plan gate only on that token and consumes it; held commits say why; an unbound session no longer inherits an orphan blackboard's approval (b7d1379 blanket allow removed) (refs #commit-blocked-after-wrap)
- fix(ci): resolve windows 8.3 short paths against git canonical top in gates and predicates (refs #ci-windows-short-paths)
- docs(issues): spec feat--tool-nature-classification: one rule model for shell and agent tools, three levels of nature, ask-and-record flow, versioned layers (built-in, rule packs, Along-managed user pack, repository), trusted fail-closed classifier plugins, phased plan (refs #tool-nature-classification)

## v4.4.6 - 2026-10-05

- chore(issues): file bug--subcommand-help-as-argument (decision create --help made an ADR named --help) (refs #subcommand-help-as-argument)
- chore(issues): file feat--tool-nature-classification (ask the nature of unknown tools, layered config, act by class) and bug--stop-gates-breaker-deadlock (refs #tool-nature-classification)
- fix(hooks): plan gate lets read-only git through: pure-read subcommands (ls-remote, for-each-ref, show-ref, cat-file, rev-list, blame, ...) and listing forms of tag/remote/stash/config/reflog/worktree/notes; git words keep their case so -C passes and -c stays held; file bug--release-tags-not-pushed; includes parallel-session issue notes (commit-blocked-after-wrap reopened, parallel-session-closeout) (refs #plan-gate-blocks-readonly-git)
- fix(hooks): along commit passes the plan gate as a completion command, so the checklist can commit after wrap unbinds the session (--fix-typography and raw git commit stay held) (refs #commit-blocked-after-wrap)
- chore(update): run along update in the dev repository (merge drivers registered, dashboard-ui migration state 4.4.5); file bug--session-records-not-captured (refs #along-update-dev-repo)
- fix(gates): keep per-machine .along/diagnostics/ out of git: untracked-exports rejects staging it at any depth, migration Step 14 untracks it (also on up-to-date repositories), along doctor reports leftovers (refs #diagnostics-files-stay-tracked)
- fix(hooks): activate only on an Along context (no bare AGENTS.md) or a declared root, never create .along/ for diagnostics, awk and verification commands pass the plan gate, edits counted on PostToolUse, unbound sessions fail open unless enforce_unbound (refs #hook-activation-and-gate-deadlock)
- fix(bootstrap): clear the re-exec guard once deps import so child engines bootstrap themselves; test hook runs in the uv project environment, dashboard tests skip without the stack (refs #bootstrap-guard-leaks-to-children)
- fix(entities): resolve downward references to nested .along contexts, gates block only problems absent at HEAD, migration stops inventing milestones (doctor --entities --fix), unconfigured test hook warns instead of passing, wrap empty-file audit scoped to truncations and session edits; untrack per-machine diagnostics (refs #entity-refs-ignore-nested-contexts)
- fix(hooks): anchor hook root on CLAUDE_PROJECT_DIR instead of shell cwd; read-only classifier accepts filters, sed/find reads, loops and command substitution (refs #readonly-classifier-pipelines) (refs #containment-root-from-shell-cwd)

## v4.4.5 - 2026-10-05

- fix(hooks): forward-slash global hook paths on Windows, fail open on missing deps, cached ~/.along/venv runtime (refs #cached-runtime-venv) (refs #windows-hook-fail-open)
## v4.4.4 - 2026-10-04

- fix(init): restore root VISION.md reconcile, FULL/REF blocks and hand-written AGENTS.md adoption via deterministic along init; migration Step 13; wrap and kb-sync onboarding checks (refs #init-onboarding-regressions)
- fix(ci): fix gates argparse on python <= 3.12 and windows short path traversal (refs #ci-matrix-gate-session-fixes) (refs #init-onboarding-regressions)

## v4.4.3 - 2026-10-03

- feat(gates): agent session bindings, scoped traces, Claude hook nested schema, and gate hardening [bug--session-state-cross-session-leak]

## v4.4.2 - 2026-10-01

- feat(gates): merge drivers, git-level and repo-state gates, containment, distillation, entity integrity, rule pack integrity (refs #rule-packs-local-extensions)
- chore(milestones): carry open v4.4.0 scope to new v4.5.0 and shift v4.5-v4.7 roadmap to v4.6-v4.8 (refs #roadmap-shift-after-v440-release)

## v4.4.1 - 2026-09-29

- chore(entities): add milestone target_issues sync requirement and log global update session (refs #entity-reference-integrity-gate)

## v4.4.0 - 2026-09-29

- chore(entities): reconcile entity references, schema priority, and Antigravity post-tool hook
- feat: suppress AI co-author attribution in agent runtimes and add commit gate (refs #suppress-ai-coauthor-attribution)

## v4.3.0 - 2026-09-29

- fix: resolve v4.3.0 review issues, CI matrix workflow, and Cowork support (refs #ci-test-matrix-workflow)
- feat: implement Antigravity runtime runner and bump v4.2.1 (refs #agent-runtime-runner-antigravity)

## v4.2.1 - 2026-09-27

- No commits recorded since the previous release tag.

## v4.2.0 - 2026-09-27

- chore(sync): synchronize projections, documentation and milestone progress [docs--state-centric-execution-and-skill-state-comparison]
- feat(governance): add doc taxonomy write policy, milestone collision gate, and cli safety [feat--doc-taxonomy-and-write-policy]
- feat(dep-scan): add subproject-scoped dependencies and internal monorepo dag [feat--subproject-scoped-dependencies]
- feat(telemetry): implement agent run protocol core specification and otlp engine [feat--agent-run-protocol-core]

## v4.1.0 - 2026-09-23

- feat(skills): add along-graph-impact and along-graph-arch user skills with lifecycle enforcement (refs #code-review-graph-user-skills)
- feat(kb): add deterministic fast-retrieval gate and harden kb-search skill (refs #kb-search-deterministic-gate-and-skill-hardening)
- refactor(dashboard): relocate dashboard ui architecture to standalone package (refs #relocate-dashboard-ui-frontend-architecture-to-package)

## v4.0.2 - 2026-09-23

- docs(readme): enhance dual-tier memory architecture and zero-vector retrieval (refs #readme-wiki-unified-search)

## v4.0.1 - 2026-09-23

- fix(ci): install uv and use uv run for dashboard export in pages workflow (refs #pages-workflow-uv-dependencies)

## v4.0.0 - 2026-09-22

- docs(cli): document entity lifecycle and milestone synchronization (refs #entity-lifecycle-cli-documentation)
- feat(dashboard): add architecture graph and automated GitHub Pages deployment (refs #dashboard-architecture-graph-and-pages-publish)

## v3.9.5 - 2026-09-22

- chore(entities): synchronize session logs, milestones, and backlog partition [feat--issues-board-backlog-partition]
- refactor(dashboard-ui): NSwag type safety, DOMPurify XSS, and security hardening [debt--dashboard-ui-type-safety-and-security]
- refactor(scripts): Python monolithic functions refactoring and cleanup [debt--python-monolithic-functions-and-boilerplate]
- docs(cli): documentation traceability and CLI reference reconciliation [docs--cli-and-documentation-traceability-reconciliation]
- feat(installer): cross-platform one-liner installer and CLI resolution [feat--oneliner-installer]
- refactor: Python CLI error handling hardening, BOM normalization, and IO standardization (refs #python-error-handling-and-io-consistency)

## v3.9.4 - 2026-09-21

- fix(hooks): omit quotes on windows hook commands (refs #windows-hook-command-quote-escaping)

## v3.9.3 - 2026-09-21

- fix: update engine deadlock, recursive hook purge, and CLI launcher shims (refs #update-engine-deadlock-and-cli-hardening)

## v3.9.2 - 2026-09-21

- fix: preserve agent runtime dirs on hook purge and sync doc versions (refs #preserve-runtime-dirs-and-doc-version-sync)

## v3.9.1 - 2026-09-21

- fix: harden runtime hooks dispatch and monorepo sync (refs #update-hooks-and-monorepo-sync-hardening)

## v3.9.0 - 2026-09-21

- feat: decouple repository updates from global skill installation (refs #updater-explicit-global-sync)

## v3.8.0 - 2026-09-20

- fix: fix CLI wrap flag collision and add dev script UV bootstrap (refs #cli-flag-collision-and-bootstrap)

## v3.7.0 - 2026-09-18

- feat: entity lifecycle orchestration, issue update, and milestone sync (refs #entity-lifecycle-cli-orchestration)

## v3.6.0 - 2026-09-16

- feat(hooks): Cursor and OpenCode runtime hook adapters, GenericCliAdapter, and along run proxy [feat--runtime-hooks-cursor-opencode]

## v3.5.0 - 2026-09-15

- feat(graph): add along-graph-sync engine, auto-ignore, and lifecycle hooks [feat--graph-build-lifecycle-integration]
- docs(actdim-along-full-branding): close issue, move to done

## v3.4.0 - 2026-09-15 (unreleased - consolidated into v3.5.0)

- feat(graph): code intelligence AST graph synchronization engine and lifecycle integration (refs #graph-build-lifecycle-integration)
- feat(resilience): systemic anomaly circuit breaker and zero-retry execution halts (refs #systemic-anomaly-circuit-breaker)
- docs(actdim-along-full-branding): adopt canonical ActDim Along branding across protocol entry points

## v3.3.0 - 2026-09-15

- No commits recorded since the previous release tag.

## v3.2.0 - 2026-09-14

- feat(runtime): worktree workspace isolation, runtime hooks, and automated lifecycle gates (refs #runtime-worktree-isolation)

## v3.1.0 - 2026-09-13

- feat: implement declarative gate engine and protocol traceability matrix [feat--declarative-gates-and-protocol-traceability]
- docs: record runtime hook rationale and reject monkey patching (refs #runtime-enforcement-of-prose-rules)

## v3.0.1 - 2026-09-10

- fix(updater): resolve sync_constraints path, along_update help flag, and AGENTS.md spacing (refs #updater-regressions-and-sync-constraints)
- fix: resolve MkDocs root 404 and sync home with README v3.0.0 (refs #mkdocs-root-index-404-and-version-drift)

## v3.0.0 - 2026-09-10

- chore(entities): reconcile v3.0 milestone, register v3.1 modular decisions and clean session log

## v2.6.1 - 2026-09-10

- fix(risks): resolve antigravity git index truncation following upstream v1.3.0 fix (refs #antigravity-extension-git-index-truncation)

## v2.6.0 - 2026-09-10

- No commits recorded since the previous release tag.

## v2.5.0 - 2026-09-10

- feat: implement executable along wrap CLI engine (refs #executable-along-wrap-engine)

## v2.4.0 - 2026-09-10

- refactor: prune AGENTS.md context budget and reconcile v3 DoD (refs #agents-md-context-budget-pruning)

## v2.3.0 - 2026-09-09

- fix(release): resolve broken relative links in session log and sync along-init skill on version bump (refs #runtime-enforcement-of-prose-rules)
- chore(milestone): move circuit breaker to milestone 4.0 and bind dependency on runtime enforcement (refs #systemic-anomaly-circuit-breaker)
- feat(kb): deterministic topic dictionary, auto-crosslinking, and ast grounding (refs #deterministic-kb-pipeline-and-ast-grounding)
- feat: programmatic integrity gates, AST patcher, and git guard (refs #programmatic-integrity-gates-and-git-guard)
- chore(audit): wrap session, record session log, and close quality audit remediation epic (refs #protocol-quality-audit-remediation)
- feat(kb-search): token-based IDF ranking, exact phrases, snippet extraction, and close debt--kb-search-ranking-and-snippet-quality (refs #kb-search-ranking-and-snippet-quality)
- fix(line-endings): enforce declared newlines across generator writers and add newline_for_path (refs #line-ending-churn-vs-gitattributes)
- chore: close debt--unpinned-mcp-and-ghost-wiki-query-tool (6/6 criteria met) (refs #unpinned-mcp-and-ghost-wiki-query-tool)
- docs(lifecycle): pluggable lifecycle hooks showcase and docs sync (refs #pluggable-lifecycle-hooks-showcase)

## v2.2.27 - 2026-09-09

- chore(protocol): untrack dashboard artifacts, formalize projection policy, and extend taxonomy (refs #generated-dashboard-artifact-committed)
- feat: auto-generate CONSTRAINTS.md on along-update and migration

## v2.2.26 - 2026-09-07

- refactor: optimize context budget, cap issues board, and compile active constraints (refs #always-on-context-budget-exceeds-claims)
- fix: record ADR for subproject Git path resolution under intent gate and ignore session blackboards (refs #kb-sync-subproject-intent-gate)
- docs(drift): resolve protocol documentation drift and update readme [debt--protocol-documentation-drift]

## v2.2.25 - 2026-09-07

- docs: clean illustrative links in session and decisions, include pyproject.toml in version bump
- fix(protocol): ban file:// URI scheme, update link gates, and migrate legacy references [generated-docs-emit-file-uri-links]

## v2.2.24 - 2026-09-07

- fix: revert broken git locking workarounds and restore stat cache (refs #remove-git-locking-workarounds)

## v2.2.23 - 2026-09-07

- feat: standardize skill commands, add durable session blackboard, and clean changelog (refs #skill-commands-reference-missing-script-paths)

## v2.2.22 - 2026-09-07

- fix: git index self-healing, committer selective staging, and kb-sync idempotency (refs #programmatic-integrity-gates-and-git-guard)
- docs(issues): translate worktree isolation issue to English and eliminate Cyrillic across all issues (refs #runtime-worktree-isolation)
- feat: add issue for deterministic kb pipeline and ast grounding (refs #deterministic-kb-pipeline-and-ast-grounding)

## v2.2.21 - 2026-09-06

- feat(orchestration): provider-agnostic team, engineering provenance, and runtime worktree isolation (refs #runtime-worktree-isolation)

## v2.2.20 - 2026-09-04

- feat(migration): migration resilience and link reconciliation (refs #migration-resilience-and-link-reconciliation)

## v2.2.19 - 2026-09-04

- fix(alongkit): clean up syntax and deduplicate rules.py logic (refs #recent-features-defects-and-guard-messages)

## v2.2.18 - 2026-09-02

- refactor(dashboard-ui): upgrade actdim packages to 1.5.13 and refactor EntityDrawer to Dynstruct (refs #runtime-enforcement-of-prose-rules)

## v2.2.17 - 2026-09-02

- feat: implement programmatic rule pack attachment and pruning (refs #runtime-enforcement-of-prose-rules)

## v2.2.16 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.15 - 2026-09-02

- fix(alongkit): add library execution guards and ensure_deps to engine scripts Completed debt--library-modules-runnable-as-scripts and updated AGENTS.md rules (refs #kb-source-provenance-and-reconstruction)

## v2.2.14 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.13 - 2026-09-02

- No commits recorded since the previous release tag.

## v2.2.12 - 2026-09-01

- test: properly skip bash installer tests if WSL is broken on Windows
- feat(installers): install manifest, MCP honesty, installer parity without deletion
- fix(migration): extend Step 5 typography scope to docs/ and AGENTS.md/README.md

## v2.2.11 - 2026-09-01

- fix(migration): merge instead of overwriting, back up first, dry run by default

## v2.2.10 - 2026-09-01

- fix(release): gate before mutating, roll back on failure, stop reinstalling globals
- fix(migration): stop rewriting prose in an already-current AGENTS.md
- docs(issues): record the managed-block drift finding and the closed REQ-5 in protocol-documentation-drift
- docs(protocol): ban file content in command lines, resync the managed block, gate both
- refactor(engines): extract scripts/alongkit/ as the single implementation, front-matter on ruamel.yaml
- fix: reframe BOM handling around the real invariant, report normalization, clean typography
- fix: repair ADR retrieval and entity lifecycle corruption, record v3.0.0 quality plan

## v2.2.7 - 2026-09-01

- feat(protocol): integrate documentation blast radius and llm-wiki synchronization (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.6 - 2026-09-01

- fix(update): add retroactive link rewriting, ~/.along/bin script discovery, and interactive prompts (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.5 - 2026-08-31

- feat(kb): add inbound link rewriting, link integrity gate, header dedup, and bump v2.2.5 (refs #automated-ui-screenshots-and-visual-verification)

## v2.2.3 - 2026-08-31

- feat(dashboard): integrate knowledge base and ADR decisions into graph visualization v2.2.2 (refs #automated-ui-screenshots-and-visual-verification)
- feat(protocol): bump to v2.2.1, concurrency projections, decentralized ADRs, and remove CONTEXT.md [feat--concurrency-projections-and-context-deprecation]

## v2.1.8 - 2026-08-31

- feat(bumper): auto-sync global installation on local machine during release bump

## v2.1.6 - 2026-08-31

- feat: multi-agent-blackboard-and-architectural-rationale feat(cli): add native entity and scratchpad subcommands to along_exec to prevent shell escaping errors (refs #external-issue-trackers-sync-and-import)

## v2.1.4 - 2026-08-31

- feat: centralize scripts suite, clean skills declarative purity, unify router, and bump v2.1.4 (refs #external-issue-trackers-sync-and-import)

## v2.1.3 - 2026-08-30

- docs: compile session log, refresh context snapshot and history for v2.1.2 release

## v2.1.2 - 2026-08-30

- feat: enable live Mermaid diagram rendering in Dashboard Drawer
- fix: implement transparent uv self-bootstrapping for along_dash runner
- feat: implement dual visual graph architecture with auto-generated Mermaid in INDEX.md and interactive Cytoscape in Dashboard
- refactor: rename along_bump_version to along_version_bump and purge all redundant skill aliases
- feat: implement unified multi-scope knowledge retrieval engine across docs/ and .along/ artifacts
- feat: treat README.md as primary KB source, streamline README into executive entry point, and enforce universal package registry rendering
- docs: add topic--llm-wiki-architecture.md and remove third-party repo references in favor of native paradigm
- feat: enforce strict source scanning (docs, wiki, kb, .along/KB) and front-matter discrimination in along-kb-sync
- fix: enforce deterministic migration pipeline in Step 7 and purge all legacy KB references
- docs: standardize all knowledge base articles to topic-- naming and scaffold .archive/ isolation folder
- docs: populate comprehensive architecture, domain-model and setup articles in docs/
- docs: document adaptive parallel research ingestion heuristic in along-kb-sync
- docs: compile full LLM-Wiki knowledge base and topic index in docs/
- feat: enforce nearest subproject localization and domain-first skill command aliases

## v2.1.1 - 2026-08-30

- v2.1.1 - LLM-Wiki Knowledge Base architecture, docs migration and singular domain-first skills refactoring

## v2.0.11 - 2026-08-28

- docs(llms): add llms.txt standard files, highlight dynamic dashboard and KB search, bump release v2.0.11
- fix(dashboard): resolve header KB search modal opening and reactive state binding
- docs(kb): sync Knowledge Base articles and index cross-links

## v2.0.10 - 2026-08-28

- feat(deps): add along-scan-deps skill and fix dashboard drawer scroll theme and search modal (v2.0.10)

## v2.0.9 - 2026-08-28

- v2.0.9 - upgrade ActDim packages to v1.5.9, NSwag client integration, dynamic MsgMesh adapters, and Decision #011
- docs(dash): update dashboard statistics for v2.0.8 (refs #external-issue-trackers-sync-and-import)

## v2.0.8 - 2026-08-27

- feat(tests): add comprehensive unit test suite and enforce pre-commit testing gate (refs #external-issue-trackers-sync-and-import)

## v2.0.7 - 2026-08-27

- fix(scripts): ensure clean 707-line migrate_protocol.py across scripts and skills/along-init -p (refs #external-issue-trackers-sync-and-import)

## v2.0.6 - 2026-08-27

- fix(dash): ensure defensive Cytoscape graph edge validation and add v2.0.0 milestone -p (refs #external-issue-trackers-sync-and-import)

## v2.0.5 - 2026-08-27

- fix(protocol): bump CURRENT_PROTOCOL_VERSION to 2.0.4 in migrate_protocol.py -p (refs #external-issue-trackers-sync-and-import)

## v2.0.4 - 2026-08-27

- feat(skills): unify along-wrap, add along-commit, and deploy lifecycle suite (refs #external-issue-trackers-sync-and-import)
- fix(scripts): ensure clean migrate_protocol.py and universal bump version engine

## v2.0.2 - 2026-08-27

- v2.0.2 - bump version and deploy global skills
- feat(issues): add external issue trackers integration and importer issue
- feat(issues): add OpenClaw and Hermes Agent integration issue
- feat(protocol): implement mandatory agentic code review and blast radius assessment gate
- feat(issues): add automated UI screenshots and agentic code review issues

## v2.0.1 - 2026-08-27

- v2.0.1 - bump version and deploy global skills
- docs: note former actdim-agents name in README subtitle

## v2.0.0 - 2026-08-27

- along v2.0.0 rebranding, isolated .along/ directory, along-* skills, and migration engine

## v1.5.7 - 2026-08-27

- v1.5.7 - repository dashboard and executive analytics engine

## v1.5.6 - 2026-08-27

- v1.5.6 - Recursive in-place update-agents and multi-context migration engine
- feat(update-agents): recursive in-place discovery and update of existing agent contexts

## v1.5.5 - 2026-08-27

- v1.5.5 - Platform Rule Packs, Central Package Management and Monorepo standards

## v1.5.4 - 2026-08-27

- v1.5.4 - entity relationships, dependency graph, and update-agents skill

## v1.5.3 - 2026-08-27

- v1.5.3 - Add bump-version skill and sanitize_typography helper
- feat(skills): add bump-version skill and auto-increment support to bump-version.py
- feat(typography): add sanitize_typography.py, expand forbidden non-ASCII character ban, and sanitize codebase
- fix(scripts): escape emdash unicode character in sanitize_emdash.py

## v1.5.2 - 2026-08-27

- v1.5.2 - Git history reconciliation, typography sanitization, and protocol sync
- fix(skills): populate sync-history SKILL.md and analyze_git_history.py

## v1.5.1 - 2026-08-27

- v1.5.1 - Protocol upgrade, migration engine, Language Rule Packs, and sync-history skill

## v1.3.3 - 2026-08-26

- v1.3.3 release with explicit MCP tool calls across all skills
- feat(skills): explicitly reference wiki-llm MCP tools (search_wiki_tool, sync_wiki_tool) in search-kb and sync-kb

## v1.3.2 - 2026-08-26

- fix(i18n): replace remaining Russian header text in search-kb SKILL.md with English
- feat(tools): add scripts/bump-version.py helper script for safe 2-step version updates
- feat(skills): restore and verify full SKILL.md contents for version v1.3.1
- fix(docs): ensure clean v1.3.1 versioning audit across all docs and protocol

## v1.3.1 - 2026-08-26

- feat(installer): add Windows Junction fallback for seamless non-admin Symlink creation
- feat(skills): add interactive re-initialization prompts for Code Graph and Knowledge Base
- feat(graph): add automatic .code-review-graph-ignore scaffolding and exclusion rules
- feat(protocol): add strict anti-hallucination & fact-grounding rules to protocol and init-kb v1.3.0
- feat(deps): add .mise.toml, uv dependency check, and -InstallDeps flag to installers
- docs(readme): add Git clone and One-Liner install instructions to README and KB
- docs(session): update commit hash in session log

## v1.2.0 - 2026-08-26

- feat(v1.2.0): Knowledge Base (KB) architecture, /init-kb, /search-kb, /check-graph skills and ADR #002/#003
- added stage definition, readme updated, plans updated
- Self-applied, planned new features
- update (tasks->issues) + antigravity support
- Readme updated
- added sync-decisions skill, removed general instructions
- Initial Commit
