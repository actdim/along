---
protocol: along
protocol_version: "4.0.1"
slug: centralized-gpu-inference-pool-and-cloud-topologies
type: feat
status: open
priority: medium
created: 2026-09-23
updated: 2026-09-23
agent: antigravity
tags: [gpu-pool, vllm, scaleway, nebius, aws, azure, vpc, private-inference, topology]
milestone: v7.0.0-enterprise-governance-and-cloud-infrastructure
blocked_by: []
related: [feat--byoc-kubernetes-operator-and-private-sandboxes]
parent: feat--enterprise-governance-and-cloud-infrastructure
---

# Centralized GPU Inference Pool & Cloud Deployment Topologies

## Goal
Architect and document the centralized private GPU inference pool (vLLM) and turnkey deployment profiles across specialized AI clouds (Scaleway, Nebius AI Studio) and enterprise hyperscalers (AWS, Azure).

## Problem Statement
Assigning dedicated GPUs to every agent execution sandbox is economically non-viable: expensive GPU hardware sits idle while agents execute CPU-bound compilers and unit tests. Conversely, routing enterprise code tokens through public internet APIs raises severe compliance risks. A centralized private inference pool connected to cheap CPU sandboxes across an internal private VPC is required.

## Technical Specifications

### 1. Centralized GPU Inference Pool Architecture
- Centralized deployment of high-throughput open-weights inference engines (**vLLM** / **TGI**) utilizing Continuous Batching.
- Capable of serving 20-50 concurrent agent tasks on a shared GPU cluster (e.g. 2x RTX 4090 or 1x A100/H100) running DeepSeek-Coder or Llama 3 models.
- Standard OpenAI-compatible REST API exposed exclusively on an internal subnet (`http://192.168.1.10:8000/v1`). Public external IP address disabled.

### 2. High-Performance Private VPC Networking
- Sub-millisecond network latency (< 1 ms ping) between CPU sandboxes and the GPU inference pool inside the same datacenter rack/pod.
- Zero data egress charges: internal VPC network traffic is unmetered and free across supported cloud providers.

### 3. Turnkey Cloud Deployment Profiles
- **Profile A: Scaleway Private Network (Cost-Optimized European Cloud)**:
  - 1x GPU instance (NVIDIA L4 or H100) + N x cheap CPU instances (`DEV1-S`).
  - Unified Scaleway VPC private subnet.
- **Profile B: Nebius AI Studio (Enterprise AI Cloud)**:
  - Dedicated InfiniBand GPU clusters with managed vLLM endpoints + VPC Compute sandboxes.
- **Profile C: AWS Enterprise BYOC**:
  - EC2 `g5`/`g6` or AWS Bedrock Provisioned Throughput + AWS Fargate / ECS sandboxes in private AWS VPC.
- **Profile D: Azure Enterprise BYOC**:
  - Azure AI Studio Dedicated / VNet Private Endpoints + Azure Container Instances (ACI).

## Acceptance Criteria
- [ ] Centralized vLLM cluster benchmarks confirm stable throughput under 20+ concurrent agent connections.
- [ ] Network latency between CPU sandboxes and GPU inference pool benchmarked at < 1 ms over private VPC.
- [ ] Terraform modules published for Scaleway VPC and Nebius private subnets.
- [ ] Cloud deployment guide published in `docs/topic--cloud-topologies.md`.
