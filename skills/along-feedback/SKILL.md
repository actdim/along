---
name: along-feedback
description: Inspect Along self-diagnostics, review sanitized incident logs in ~/.along/diagnostics/, and dispatch bug reports and protocol feedback via Telegram, Webhook, or File export. Use when encountering Along system/tool errors or invoking /along-feedback.
---

# Along Self-Diagnostics & Feedback Engine [v2.2.25]

Inspect captured system incidents, protocol anomalies, and tool exceptions, and dispatch sanitized diagnostics bundles to Telegram, Webhooks, or local export files.

## Privacy, Redaction & Security First
- **Zero Raw PII & Secret Leakage**: All absolute home paths (`C:\Users\<user>`, `/home/<user>`) and authentication tokens (`sk-...`, `ghp_...`, `Bearer ...`, DB passwords) are automatically redacted before logging to disk or transmitting.
- **Explicit Dispatch**: Transmissions to external channels (Telegram Bot, Webhook) are never triggered silently without user invocation or configured opt-in in `~/.along/config.json`.

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
Send unresolved incidents to configured transports (Telegram channel, Webhook API, or Local export file):
```bash
# Dispatch via all configured channels
along feedback send --note "Encountered issue in along_commit"

# Dispatch to specific channel (file, telegram, webhook)
along feedback send --channel telegram --note "Feedback summary"

# Dry-run simulation (inspect payload without network/disk write)
along feedback send --dry-run
```

### 5. Manage Configuration
View and initialize global settings in `~/.along/config.json`:
```bash
along feedback config show
along feedback config init
```

### 6. Clear Diagnostics Store
Clear resolved or all incident logs:
```bash
along feedback clear --all
```

