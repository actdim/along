---
protocol: along
protocol_version: "4.0.1"
slug: agent-execution-gate-telegram
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [telegram, live-card, execution-gate, permission-hook, fail-safe, human-in-the-loop, task-dispatch, multi-room, mini-app, semi-autonomous]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-run-protocol-core]
related: [feat--agent-runtime-runner-antigravity, feat--agent-chat-adapters-discord-slack-mattermost-matrix]
parent: feat--agent-run-protocol-and-observability
---

# Telegram Remote Operational Gateway & Execution Gate

## Goal
Establish Telegram as a primary bidirectional remote operational gateway for semi-autonomous agent execution. The gateway enables dispatching tasks, referencing existing repository issues, routing across project-specific chat rooms and topics, exploring issue context via Telegram Mini Apps or interactive cards, and enforcing human-in-the-loop safety via in-place Live Status Cards with synchronous approval hooks.

## Problem Statement
Autonomous agents operating in background, remote, or VPS environments require a low-friction remote control interface. However:
1. Pure notification bots are passive and cannot trigger work or anchor tasks remotely.
2. Standard conversational chat bots degrade into noisy, uncontrolled "ping-pong" dialogues without issue grounding, causing context drift and token bloat.
3. Interactive line-by-line software development cannot and should not be forced into a chat client. Deep pair-programming requires full IDE workspaces (such as Antigravity remote sessions accessible via QR code / web terminal).
4. Multi-project teams require strict context boundaries so commands in a project room or forum topic map deterministically to the correct workspace without cross-contamination.

## Technical Specifications

### 1. Operational Paradigm: Semi-Autonomous Mode vs Interactive IDE Mode
- **Semi-Autonomous Operational Mode (Remote Chat Gateway)**:
  - Asynchronous, goal-directed orchestration: task dispatch, issue binding, autonomous execution with milestone checkpoints, blocking approval gates on high-risk operations, and structured summaries.
  - Zero conversational "ping-pong": the bot does not act as a conversational LLM chatter. It acts as an operational control terminal.
- **Interactive Development Mode (Direct IDE / Antigravity Workspace)**:
  - Deep exploratory coding, complex debugging, refactoring, and line-by-line diff inspections remain strictly in the primary IDE.
  - Remote operator connection to the full interactive workspace is provided via dedicated development endpoints (such as Antigravity web interface or QR-code terminal access), completely decoupled from the chat gateway.

### 2. Bidirectional Task Dispatch & Issue Referencing
- **Command Dispatch Syntax**:
  - `/run <type>--<slug>`: Initiates an autonomous run bound to an existing issue in `.along/ISSUES/`.
  - `/run #<slug>`: Shorthand reference to an issue within the active project context.
  - `/task "<title>" [--type feat|bug|debt|task] [--priority high|medium|low]`: Dynamically anchors and creates a new issue file in `.along/ISSUES/` before triggering execution.
- **Execution Parameter Flags**:
  - `--branch <name>`: Target git branch or worktree.
  - `--dry-run`: Runs analysis, planning, and test simulation without mutating repository files.
  - `--autonomy-limit <N>`: Maximum tool steps before requiring a checkpoint.
- **Mandatory Issue Anchoring [gate: require-active-issue]**:
  - Every dispatched run must resolve to an active issue file (`status: in-progress`).
  - Tasks initiated via free-form text automatically generate an issue stub in `.along/ISSUES/` marked `source: telegram-remote` prior to runner invocation.

### 3. Multi-Project & Multi-Room / Forum Topic Routing
- **Context Routing Map (`~/.along/config.json` or daemon config)**:
  - Bind Telegram `chat_id` and `message_thread_id` (Telegram Forum Topics) to explicit repository workspace paths:
    ```json
    {
      "telegram": {
        "room_bindings": {
          "-1001234567890": {
            "default_repo": "/var/repos/along",
            "topics": {
              "101": { "repo": "/var/repos/along", "project_slug": "actdim/along" },
              "204": { "repo": "/var/repos/infra-k8s", "project_slug": "actdim/infra" }
            }
          }
        }
      }
    }
    ```
- **Ambiguity Guard**:
  - If a command is received in a direct message (DM) or unmapped group without topic binding, the bot rejects execution unless explicitly qualified with a project prefix (e.g. `/run actdim/along:feat--token-refresh`) or selected via the context UI.
- **Per-Room Access Control**:
  - Verify initiating user against an allowlist of authorized Telegram `user_id` values mapped to roles (`admin`, `operator`, `viewer`).

### 4. Issue Context & Browsing Interface (Dual-Layer)
Operators need visibility into pending issues and project status before initiating runs:
- **Layer A: Native Interactive Cards & Inline Queries**:
  - Inline bot query support: typing `@alongbot issue <query>` displays a searchable popup list of active issues with status badges.
  - `/issues [active|backlog|all]`: Emits an interactive message card with pagination buttons.
  - Card detail view includes issue goal, tags, blockers, and an inline `[ Run Task ]` button.
- **Layer B: Telegram Mini App (TMA / WebApp)**:
  - WebApp button attached to chat menu: `[ Open Project Board ]`.
  - Launches an embedded, lightweight web interface backed by the local `along_dash` service (exposed via authenticated local tunnel or internal proxy):
    - Visual Kanban board of `.along/ISSUES.md`.
    - Dependency DAG inspection.
    - Active runs monitor with live milestone updates.
    - One-tap task initiator with parameter selectors (branch, model profile, dry-run).

### 5. Synchronous Blocking Permission Hook & Live Status Card
- **Pre-Execution Guard Hook**:
  - Intercepts high-risk commands during autonomous runs: destructive filesystem edits, forced git operations, staging/production deployments, credential access.
  - Halts the runner process and dispatches a blocking approval event with an approval request ID.
- **Telegram Live Status Card Pattern**:
  - A single in-place editable message per run (`editMessageText`) to eliminate notification flood:
    - **Header**: `[Run #421] Project: actdim/along | Issue: feat--auth-refresh | Status: WAITING FOR APPROVAL`
    - **Milestone Progress Checklist**:
      ```text
      [x] Read package.json
      [x] Search codebase (AST)
      [x] Run unit tests (14/14 passed)
      [!] Dangerous action: Deploy to staging
      ```
    - **Inline Callback Buttons**:
      - `[ Approve ]` (callback `approve:<req_id>`)
      - `[ Reject ]` (callback `reject:<req_id>`)
      - `[ View Trace ]` (link to trace/telemetry dashboard)
  - Upon decision, updates in-place: `[x] Action approved by @admin at 14:22`.

### 6. Concurrency, Worktree Isolation & Security
- **Atomic Callback Resolution**:
  - Prevent race conditions when multiple operators view the same room card. The first callback locks the decision; subsequent presses receive a Telegram alert notification (`Decision already recorded by @user`).
- **Worktree Containment**:
  - Each run dispatched from Telegram executes in an isolated runtime worktree (`.along/worktrees/run-<id>`) as specified in ADR-2026-09-13, preventing collisions with the primary developer working tree.
- **Fail-Safe Timeout**:
  - Configurable decision timeout (default: 120 seconds). If unapproved, the hook automatically aborts with exit code 1 (`Action rejected: decision timed out`).
- **Secret Redaction**:
  - All command strings, environment variables, and output snippets displayed in Telegram are sanitized to strip API tokens, private keys, and passwords.

## Acceptance Criteria
- [ ] Bidirectional task initiation supported via `/run <slug>` and `/task <title>`.
- [ ] Tasks dispatched via Telegram strictly bind to or automatically create `.along/ISSUES/` records.
- [ ] Project-specific routing correctly maps Telegram group chats and forum topics to repository paths.
- [ ] Ambiguous or unmapped chats require explicit project qualification before execution.
- [ ] Native inline issue search (`@alongbot issue <query>`) and paginated `/issues` card functional.
- [ ] Telegram Mini App integration connects to local dashboard for graphical issue browsing and dispatch.
- [ ] Live Status Card updates in-place per run via `editMessageText` without chat spam.
- [ ] Blocking permission hook halts tool execution until authorized inline callback is received.
- [ ] Multi-operator race conditions resolved atomically with user attribution.
- [ ] Configurable timeout aborts stalled runs safely.
- [ ] Clear operational boundary maintained: semi-autonomous orchestration in Telegram; deep interactive development directed to full IDE / Antigravity workspace.
