---
protocol: along
protocol_version: "4.0.1"
slug: byoc-kubernetes-operator-and-private-sandboxes
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [byoc, kubernetes, k8s-operator, docker-appliance, ephemeral-sandboxes, workstations]
milestone: v7.0.0-enterprise-governance-and-cloud-infrastructure
blocked_by: []
related: []
parent: feat--enterprise-governance-and-cloud-infrastructure
---

# BYOC Kubernetes Operator & Private Execution Sandboxes

## Goal
Develop a vendor-agnostic Bring-Your-Own-Cloud (BYOC) Kubernetes Operator and Docker Compose Appliance that deploys isolated execution sandboxes inside customer-owned private VPCs and on-premise clusters.

## Problem Statement
Enterprises with strict security policies prohibit uploading source code or execution commands to third-party multi-tenant SaaS platforms. However, running autonomous agents on bare-metal developer laptops creates stability and security risks. An automated, self-hosted sandbox infrastructure running directly inside the customer's cloud account is required.

## Technical Specifications

### 1. BYOC Kubernetes Operator
- Custom Resource Definition (CRD): `AgentExecutionEnvironment`.
- Automated lifecycle management: dynamic provisioning, scaling, health checking, and automatic teardown of sandboxes.
- Zero-leakage architecture: the control plane communicates via secure RPC/gRPC; proprietary code never leaves the customer cluster.

### 2. Dual Sandbox Topologies
- **Topology A: Ephemeral Task Sandboxes (Micro-VM / Pod)**:
  - Spun up on-demand for single issues, PR reviews, or test executions.
  - Read-only root filesystem with isolated throwaway workspace volume.
  - Automatically destroyed upon completion (exit 0) or error.
- **Topology B: Persistent Agent Workstations (Stateful Pod)**:
  - Long-running dedicated environments assigned to developers or continuous integration bots.
  - Persistent volume caching dependencies (`node_modules`, `pip cache`, `.m2`, `cargo target`) to eliminate repetitive dependency downloads.

### 3. Docker Compose Appliance (Lightweight On-Premise)
- Self-contained `docker-compose.yml` distribution for smaller organizations or air-gapped single-server deployments (Hetzner, on-prem bare-metal) running OpenObserve, local sandboxes, and Telegram/Mattermost gateways.

## Acceptance Criteria
- [ ] Kubernetes Operator successfully reconciles `AgentExecutionEnvironment` resources.
- [ ] Ephemeral sandboxes execute tasks and terminate with zero orphaned resources.
- [ ] Persistent workstations retain build caches across multiple successive agent runs.
- [ ] Docker Compose appliance boots all core services with a single command.
- [ ] Network policy tests confirm no outbound traffic escapes the private perimeter.
