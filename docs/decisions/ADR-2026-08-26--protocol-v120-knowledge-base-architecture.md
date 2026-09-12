---
protocol: along
slug: protocol-v120-knowledge-base-architecture
title: "Protocol v1.2.0 & Knowledge Base (KB) Architecture Standard"
date: 2026-08-26
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-26--protocol-v120-knowledge-base-architecture - Protocol v1.2.0 & Knowledge Base (KB) Architecture Standard

- Date: 2026-08-26
- Status: accepted
- Context: Projects require a structured, persistent Knowledge Base that provides deep architecture, domain model, and workflow guidance without bloating `AGENTS.md` context window.
- Decision: Adopt Knowledge Base (KB) terminology and structure in `.along/KB/` (`INDEX.md`, `01-architecture.md`, `02-domain-model.md`, `03-setup-and-workflow.md`). `AGENTS.md` remains a compact executive entry point linking to KB articles (`[[.along/KB/INDEX.md]]`). Human `docs/` and `README.md` are scanned as read-only inputs during `/along-init-kb` and `/along-sync-kb`.
- Consequences: `AGENTS.md` stays lean (< 80 lines) while agents and humans have structured access to deep documentation.
