import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


def load_architecture_data(repo_root: Path) -> Dict[str, Any]:
    """Load architecture communities and cross-community edges from .along/architecture.json or fallback."""
    arch_file = repo_root / ".along" / "architecture.json"
    if arch_file.exists():
        try:
            with open(arch_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    # Lightweight fallback when no CRG cache exists
    fallback_communities = [
        {"id": 1, "name": "dashboard-ui", "description": "Frontend React 19 UI", "size": 20, "dominant_language": "typescript"},
        {"id": 2, "name": "dashboard-core", "description": "FastAPI and Data Collector", "size": 15, "dominant_language": "python"},
        {"id": 3, "name": "alongkit", "description": "Shared alongkit Python library", "size": 35, "dominant_language": "python"},
        {"id": 4, "name": "scripts", "description": "CLI skill engines and runners", "size": 25, "dominant_language": "python"},
        {"id": 5, "name": "tests", "description": "Hermetic automated test suite", "size": 50, "dominant_language": "python"},
    ]
    fallback_edges = [
        {"source_community": 1, "target_community": 2, "count": 10},
        {"source_community": 2, "target_community": 3, "count": 15},
        {"source_community": 4, "target_community": 3, "count": 25},
        {"source_community": 5, "target_community": 3, "count": 40},
        {"source_community": 5, "target_community": 4, "count": 20},
    ]
    return {
        "summary": "Architecture: 5 communities (fallback)",
        "communities": fallback_communities,
        "cross_community_edges": fallback_edges,
        "warnings": [],
    }


def build_entity_dag_graph(collector) -> Dict[str, Any]:
    """Construct Cytoscape-compatible JSON graph structure of entities and dependencies."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_nodes = set()

    # 1. Add Issue nodes
    for iss in collector.issues:
        node_id = iss.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": iss.title or iss.slug,
            "type": "issue",
            "issue_type": iss.type,
            "status": iss.status,
            "priority": iss.priority,
            "slug": iss.slug,
            "file_path": iss.file_path,
        })

    # 2. Add Milestone nodes
    for m in collector.milestones:
        node_id = m.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": m.title or m.slug,
            "type": "milestone",
            "status": m.status,
            "progress_pct": m.progress_pct,
            "slug": m.slug,
            "file_path": m.file_path,
        })

    # 3. Add Risk nodes
    for r in collector.risks:
        node_id = r.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": r.title or r.slug,
            "type": "risk",
            "severity": r.severity,
            "status": r.status,
            "slug": r.slug,
            "file_path": r.file_path,
        })

    # 4. Add Spike nodes
    for sp in collector.spikes:
        node_id = sp.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": sp.title or sp.slug,
            "type": "spike",
            "status": sp.status,
            "slug": sp.slug,
            "file_path": sp.file_path,
        })

    # 5. Add Decision (ADR) nodes
    for dec in collector.decisions:
        node_id = dec.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": dec.title or dec.id,
            "type": "decision",
            "status": dec.status,
            "date": dec.date,
            "file_path": getattr(dec, "file_path", ".along/DECISIONS.md"),
        })

    # 6. Add Knowledge Base (KB) nodes
    for kb in collector.kb_articles:
        node_id = kb.id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": kb.title or kb.slug,
            "type": "kb",
            "kb_type": kb.type,
            "slug": kb.slug,
            "tags": kb.tags,
            "file_path": kb.file_path,
        })

    # 7. Add Architecture (Module / Community) nodes
    repo_root = getattr(collector, "repo_root", Path("."))
    arch_data = load_architecture_data(repo_root)
    comm_map = {}
    for comm in arch_data.get("communities", []):
        comm_id = comm.get("id")
        node_id = f"arch--comm-{comm_id}"
        comm_map[comm_id] = node_id
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)
        nodes.append({
            "id": node_id,
            "label": comm.get("name", f"Module {comm_id}"),
            "type": "architecture",
            "description": comm.get("description", ""),
            "size": comm.get("size", 0),
            "cohesion": comm.get("cohesion", 0.0),
            "dominant_language": comm.get("dominant_language", ""),
            "level": comm.get("level", 0),
        })

    # Helper to add edge if not already present
    added_edge_keys = set()

    def add_edge(source: str, target: str, edge_type: str, label: str):
        edge_key = (source, target, edge_type)
        if edge_key not in added_edge_keys and source in seen_nodes and target in seen_nodes:
            added_edge_keys.add(edge_key)
            edges.append({
                "source": source,
                "target": target,
                "type": edge_type,
                "label": label,
            })

    # 7. Add Edges
    # A. Issue blocked_by edges
    for iss in collector.issues:
        for blocker in iss.blocked_by:
            target_id = None
            if "--" in blocker:
                target_id = blocker
            else:
                for candidate in collector.issues:
                    if candidate.slug == blocker:
                        target_id = candidate.id
                        break
            if target_id:
                add_edge(target_id, iss.id, "blocks", "blocks")

        # Related issue/risk edges
        for rel in iss.related:
            target_id = None
            if rel in seen_nodes:
                target_id = rel
            else:
                for cand in collector.issues:
                    if cand.slug == rel or cand.id == rel:
                        target_id = cand.id
                        break
                if not target_id:
                    for cand_r in collector.risks:
                        if cand_r.slug == rel or cand_r.id == rel:
                            target_id = cand_r.id
                            break
            if target_id:
                add_edge(iss.id, target_id, "related", "related")

    # B. Milestone target_issues / issue milestone relations
    for iss in collector.issues:
        if iss.milestone:
            m_id = f"milestone--{iss.milestone}"
            add_edge(iss.id, m_id, "belongs_to", "in milestone")

    for m in collector.milestones:
        for target_key in m.target_issues:
            target_id = None
            if "--" in target_key:
                target_id = target_key
            else:
                for candidate in collector.issues:
                    if candidate.slug == target_key:
                        target_id = candidate.id
                        break
            if target_id:
                add_edge(target_id, m.id, "belongs_to", "target")

    # C. Parent-child relationships
    for iss in collector.issues:
        if iss.parent:
            parent_id = iss.parent if "--" in iss.parent else f"feat--{iss.parent}"
            add_edge(parent_id, iss.id, "parent_of", "child")

        if iss.superseded_by:
            target_id = None
            if "--" in iss.superseded_by:
                target_id = iss.superseded_by
            else:
                for candidate in collector.issues:
                    if candidate.slug == iss.superseded_by:
                        target_id = candidate.id
                        break
            if target_id:
                add_edge(target_id, iss.id, "supersedes", "superseded by")

        if iss.duplicate_of:
            target_id = None
            if "--" in iss.duplicate_of:
                target_id = iss.duplicate_of
            else:
                for candidate in collector.issues:
                    if candidate.slug == iss.duplicate_of:
                        target_id = candidate.id
                        break
            if target_id:
                add_edge(iss.id, target_id, "duplicate_of", "duplicate of")

    # D. Decision supersedes relationships
    for dec in collector.decisions:
        if dec.superseded_by:
            target_id = dec.superseded_by
            if not target_id.startswith("decision--") and target_id not in seen_nodes:
                target_id = f"decision--{target_id}"
            add_edge(target_id, dec.id, "supersedes", "supersedes")

    # E. Knowledge Base cross-links (outgoing_links)
    kb_slug_map = {kb.slug: kb.id for kb in collector.kb_articles}
    for kb in collector.kb_articles:
        for out_ref in kb.outgoing_links:
            clean_ref = out_ref.strip().lstrip("./").replace(".md", "")
            # Check direct match
            target_id = None
            if f"kb--{clean_ref}" in seen_nodes:
                target_id = f"kb--{clean_ref}"
            elif clean_ref in kb_slug_map:
                target_id = kb_slug_map[clean_ref]
            elif clean_ref in seen_nodes:
                target_id = clean_ref
            else:
                # Try finding in issues, decisions, risks
                for cand in collector.issues:
                    if cand.slug == clean_ref or cand.id == clean_ref:
                        target_id = cand.id
                        break
                if not target_id:
                    for cand_d in collector.decisions:
                        if cand_d.id == clean_ref or cand_d.id == f"ADR-{clean_ref}":
                            target_id = cand_d.id
                            break

            if target_id and target_id != kb.id:
                add_edge(kb.id, target_id, "links_to", "links")

    # F. Architecture cross-module coupling edges
    for edge in arch_data.get("cross_community_edges", []):
        src_comm = edge.get("source_community")
        tgt_comm = edge.get("target_community")
        count = edge.get("count", 1)
        src_id = comm_map.get(src_comm)
        tgt_id = comm_map.get(tgt_comm)
        if src_id and tgt_id and src_id in seen_nodes and tgt_id in seen_nodes:
            add_edge(src_id, tgt_id, "calls", f"{count} calls")

    return {"nodes": nodes, "edges": edges}

