---
protocol: along
slug: global-self-diagnostics-and-feedback-subsystem
title: "Global Self-Diagnostics, PII Redaction, and Multi-Transport Feedback Engine"
date: 2026-08-31
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-31--global-self-diagnostics-and-feedback-subsystem - Global Self-Diagnostics, PII Redaction, and Multi-Transport Feedback Engine

- Date: 2026-08-31
- Status: accepted
- Context: When Along tools or agent scripts encounter unexpected runtime errors or platform incompatibilities in user repositories, developers lack a centralized telemetry and diagnostic mechanism to capture and report these incidents without risking credential or PII leaks.
- Decision: 1. Implement global diagnostics store in user home directory (~/.along/diagnostics/) with structured incident JSON files and an auto-compiled REPORT.md. 2. Enforce strict automatic regex redaction for user home paths and authentication credentials. 3. Support three pluggable feedback transports: File export, Telegram Bot API, and REST Webhook. 4. Deploy /along-feedback skill and along_feedback.py CLI tool.
- Consequences: Enables reliable debugging and continuous protocol improvement while guaranteeing zero silent transmissions and preventing secret/PII leakage.
