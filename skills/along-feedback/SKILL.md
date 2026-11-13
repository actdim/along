---
name: along-feedback
description: Inspect Along self-diagnostics, review sanitized incident logs in ~/.along/diagnostics/, and dispatch bug reports and protocol feedback via GitHub Pull Request, Telegram, Webhook, or File export. Use when encountering Along system/tool errors or invoking /along-feedback.
---

# Along Self-Diagnostics & Feedback Engine
Inspect captured system incidents, protocol anomalies, and tool exceptions, and dispatch sanitized diagnostics bundles to GitHub PRs, Telegram, Webhooks, or local export files.

## Privacy, Redaction & Security First
- **Zero Raw PII & Secret Leakage**: All absolute home paths (`C:\Users\<user>`, `/home/<user>`) and authentication tokens (`sk-...`, `ghp_...`, `Bearer ...`, DB passwords) are automatically redacted before logging to disk or transmitting.
- **Explicit Dispatch**: Transmissions to external channels (GitHub PR, Telegram Bot, Webhook) are never triggered silently without user invocation, consent confirmation, or configured opt-in in `~/.along/config.json`.

## Send Feedback to the Along Maintainers

When the user asks to "create feedback for Along" or "send feedback for Along":
1. **Draft Text**: Draft the feedback title and Markdown body describing the issue, enhancement, or reproduction steps.
2. **Stage Body**: Save the body into a temporary file.
3. **Preview & Consent**: Run preview without `--yes`:
   ```bash
   along feedback send --channel github --title "Feedback Title" --body-file /path/to/body.md
   ```
   Show the generated note path and preview to the user and request explicit confirmation.
4. **Dispatch with Consent**: After the user gives an explicit yes, execute with `--yes`:
   ```bash
   along feedback send --channel github --title "Feedback Title" --body-file /path/to/body.md --yes
   ```
5. **Share PR Link**: Share the resulting Pull Request URL (Path A) or browser fallback instructions (Path B) with the user.

## Core Commands
*(Or fallback: `python ~/.along/bin/along_exec.py feedback <subcommand>`)*

### 1. List Captured Incidents
View active unresolved incidents across all repositories on the local machine:
```bash
along feedback list
```

### 2. View Incident Details
Inspect specific stack trace, environment metadata, and sanitized error context:
```bash
along feedback show <incident_id>
```

### 3. Generate & View Report
Compile full diagnostics Markdown report from `~/.along/diagnostics/`:
```bash
along feedback report
```

### 4. Dispatch Feedback
Send unresolved incidents or user feedback notes to configured transports (GitHub PR, Telegram channel, Webhook API, or Local export file):
```bash
# Dispatch via all configured incident channels
along feedback send --note "Encountered issue in along_commit"

# Dispatch to specific channel (file, telegram, webhook, github)
along feedback send --channel telegram --note "Feedback summary"

# Dispatch user feedback via GitHub PR (requires --title, --body-file, and --yes)
along feedback send --channel github --title "Report Title" --body-file /path/to/body.md --yes

# Dry-run simulation (inspect payload without network/disk write)
along feedback send --dry-run
```

### 5. Manage Configuration
View and initialize global settings in `~/.along/config.json`:
```bash
along feedback config show
along feedback config init
```

Telegram transport settings are resolved via `alongkit.telegram` from global `~/.along/config.json`, local `.along/config.json`, or environment variables (`ALONG_TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_TOKEN`, `ALONG_TELEGRAM_CHAT_ID` / `TELEGRAM_CHAT_ID`). Environment variables override configuration files.

### 6. Clear Diagnostics Store
Clear resolved or all incident logs:
```bash
along feedback clear --all
```

