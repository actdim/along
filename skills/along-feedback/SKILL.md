---
name: along-feedback
description: Inspect Along self-diagnostics, review sanitized incident logs in ~/.along/diagnostics/, and dispatch bug reports and protocol feedback via Telegram, Webhook, or File export. Use when encountering Along system/tool errors or invoking /along-feedback.
---

# Along Self-Diagnostics & Feedback Engine [v2.2.9]

Inspect captured system incidents, protocol anomalies, and tool exceptions, and dispatch sanitized diagnostics bundles to Telegram, Webhooks, or local export files.

## Privacy, Redaction & Security First
- **Zero Raw PII & Secret Leakage**: All absolute home paths (`C:\Users\<user>`, `/home/<user>`) and authentication tokens (`sk-...`, `ghp_...`, `Bearer ...`, DB passwords) are automatically redacted before logging to disk or transmitting.
- **Explicit Dispatch**: Transmissions to external channels (Telegram Bot, Webhook) are never triggered silently without user invocation or configured opt-in in `~/.along/config.json`.

## Core Commands

### 1. List Captured Incidents
View active unresolved incidents across all repositories on the local machine:
```bash
python scripts/along_exec.py feedback list
```

### 2. View Incident Details
Inspect specific stack trace, environment metadata, and sanitized error context:
```bash
python scripts/along_exec.py feedback show <incident_id>
```

### 3. Generate & View Report
Compile full diagnostics Markdown report from `~/.along/diagnostics/`:
```bash
python scripts/along_exec.py feedback report
```

### 4. Dispatch Feedback
Send unresolved incidents to configured transports (Telegram channel, Webhook API, or Local export file):
```bash
# Dispatch via all configured channels
python scripts/along_exec.py feedback send --note "Encountered PowerShell escaping crash in along_commit"

# Dispatch to specific channel (file, telegram, webhook)
python scripts/along_exec.py feedback send --channel telegram --note "Feedback summary"

# Dry-run simulation (inspect payload without network/disk write)
python scripts/along_exec.py feedback send --dry-run
```

### 5. Manage Configuration
View and initialize global settings in `~/.along/config.json`:
```bash
python scripts/along_exec.py feedback config show
python scripts/along_exec.py feedback config init
```

### 6. Clear Diagnostics Store
Clear resolved or all incident logs:
```bash
python scripts/along_exec.py feedback clear --all
```

