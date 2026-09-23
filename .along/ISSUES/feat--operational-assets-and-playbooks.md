---
protocol: along
protocol_version: "4.0.1"
slug: operational-assets-and-playbooks
type: feat
status: open
priority: high
created: 2026-09-23
updated: 2026-09-23
completed: null
agent: antigravity
tags: [operations, assets, playbooks, topology, runbooks, schemas]
milestone: v5.0.0-agent-run-protocol-and-observability
blocked_by: [feat--agent-run-protocol-core]
related: [feat--system-invariants-and-health-probes, docs--operations-and-autonomous-systems-paradigm]
parent: feat--agent-run-protocol-and-observability
superseded_by: null
duplicate_of: null
---

# Operational Assets, Dependency Topology & Executable Playbooks

## Goal

Introduce operational domain primitives into Along, expanding beyond code repositories into external system management, cloud infrastructure, and autonomous agent operations (Hermes/OpenClaw paradigm).

## Problem Statement

Along currently assumes the target environment is always a local source code repository with Git diffs and code ASTs (`code-review-graph`). When agents manage external systems (cloud resources, databases, clusters, third-party APIs), Along lacks primitives to represent:
1. Target systems, assets, and their dependency topology for calculating operational blast radius.
2. Executable, parameterized Standard Operating Procedures (SOPs / Playbooks) with pre-flight checks and rollback logic.
3. Operational issue types (`incident`, `change`, `audit`) distinct from software development items (`feat`, `bug`, `debt`).

## Technical Specifications

### 1. Asset & Target System Modeling (`.along/ASSETS/<slug>.md`)
- Schema for external systems and resources:
  - `category`: `service`, `database`, `infrastructure`, `third-party-api`, `cluster`.
  - `environment`: `prod`, `staging`, `sandbox`.
  - `criticality`: `tier-1`, `tier-2`, `tier-3`.
  - `depends_on`: List of canonical asset slugs forming an operational dependency DAG.
- Operational blast radius resolver: determining affected downstream services when an asset is targeted for maintenance or mutation.

### 2. Executable Playbooks (`.along/PLAYBOOKS/<slug>.md`)
- Structured, parameterized operational runbooks:
  - `inputs`: Declared parameters and variable schemas.
  - `pre_flight`: Dry-run validations and safety guardrails before mutation.
  - `steps`: Ordered sequence of tool actions, commands, and sub-tasks.
  - `rollback`: Deterministic mitigation or restoration steps upon step failure.
  - `post_flight`: Verification assertions ensuring system invariants remain intact.

### 3. Operational Issue Taxonomy Extension
- Extend Along entity schemas and CLI parsers (`alongkit.entities`, `dashboard/schemas/entities.py`) with operational issue types:
  - `incident`: Unplanned service degradation, alert response, or outage triage.
  - `change`: Planned operational modification or infrastructure migration (RFC).
  - `audit`: Periodic compliance, security, or resource utilization review.

## Acceptance Criteria

- [ ] Schema specifications for `ASSETS` and `PLAYBOOKS` implemented in `alongkit.entities` and `dashboard/schemas/entities.py`.
- [ ] Operational issue types (`incident`, `change`, `audit`) recognized by Along CLI (`along issue create`, `along issue list`).
- [ ] Operational blast radius calculation using `depends_on` topology implemented and tested.
- [ ] Hermetic tests verifying validation, parsing, and serialization of assets and playbooks.
