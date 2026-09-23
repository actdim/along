---
name: along-graph-arch
description: Inspect repository architectural structure, modular community boundaries, coupling hotspots, and critical bridge nodes. Use when invoking /along-graph-arch.
---

# Along Graph Architecture (`/along-graph-arch`)
Provides high-level architectural intelligence, community clustering, and hotspot risk analysis across the repository using the `code-review-graph` AST database.

## Usage
- Direct slash command: `/along-graph-arch`
- CLI command: `along graph-arch`
- Subcommand group: `along graph arch`
- Script fallback: `python ~/.along/bin/along_exec.py graph-arch`
- Compact summary: `along graph-arch --detail-level minimal`
- Custom hub/bridge limits: `along graph-arch --top-hubs 10 --top-bridges 10`
- Machine-readable JSON: `along graph-arch --json`

## Key Capabilities
1. **Community Detection & Layering**: Groups source files and symbols into cohesion-based functional communities (`get_architecture_overview_tool`).
2. **Coupling Warning System**: Detects unhealthy cross-community coupling, leakages across module boundaries, and high fan-in dependencies.
3. **Hub Node Hotspots**: Pinpoints the most heavily connected symbols in the codebase (high degree centrality via `get_hub_nodes_tool`). Modifying hub nodes introduces high regression risk.
4. **Bridge Node Bottlenecks**: Identifies critical architectural chokepoints sitting on shortest execution paths between subsystems (betweenness centrality via `get_bridge_nodes_tool`).
5. **Resilient Degradation**: If `code-review-graph` MCP or `uvx` is offline, automatically executes static structural analysis across directory modules and import hierarchies, flagging output as `[DEGRADED]`.

## Output Report Sections
- **Architectural Communities**: Subsystem names, dominant languages, node counts, and cohesion ratings.
- **Cross-Community Couplings & Warnings**: Coupling severity between module pairs.
- **Top Hub Hotspots**: Highly coupled functions and classes with refactoring advisories.
- **Critical Bridge Nodes**: Single-point-of-failure bottlenecks connecting subsystems.

## Lifecycle Integration
- **Architecture Planning**: Inspect high-level hotspots before refactoring core engines.
- **Code Review**: Audit whether PRs or changes increase cross-community coupling.
