"""Collector and parser for Along Protocol entities and Knowledge Base."""

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# The dashboard reads the same entities as the engines, through the same reader.
# It used to carry a fourth copy of the front-matter parser, with a PyYAML fast path
# and a hand-rolled fallback, so the dashboard could disagree with search and sync
# about what a file contains.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))

from alongkit import frontmatter as _frontmatter

from ..schemas.entities import (
    IssueSchema,
    MilestoneSchema,
    RiskSchema,
    SpikeSchema,
    SessionSchema,
    DecisionSchema,
)
from ..schemas.kb import KBArticleSchema
from ..schemas.metrics import (
    DashboardMetricsSchema,
    StatusBreakdown,
    TypeBreakdown,
    PriorityBreakdown,
    FullDashboardDataSchema,
)


# The dashboard renders whatever it can read and must not fail to start because one
# entity file is malformed; the engines that write use the strict reader.
parse_frontmatter = _frontmatter.parse_tolerant


def find_agents_dir(start_dir: str = ".") -> Path:
    """Find nearest .along (or fallback .agents) directory starting from start_dir and walking upwards."""
    current = Path(start_dir).resolve()
    while current != current.parent:
        candidate = current / ".along"
        if candidate.is_dir():
            return candidate
        legacy_candidate = current / ".agents"
        if legacy_candidate.is_dir():
            return legacy_candidate
        current = current.parent
    return Path(start_dir).resolve() / ".along"


class EntityCollector:
    """Collects and parses all Along Protocol entities and Knowledge Base documents."""

    def __init__(self, agents_dir: Path):
        self.agents_dir = agents_dir
        self.repo_root = agents_dir.parent
        self.issues: List[IssueSchema] = []
        self.milestones: List[MilestoneSchema] = []
        self.risks: List[RiskSchema] = []
        self.spikes: List[SpikeSchema] = []
        self.sessions: List[SessionSchema] = []
        self.kb_articles: List[KBArticleSchema] = []
        self.decisions: List[DecisionSchema] = []
        self.context_text: str = ""
        self.issues_board_text: str = ""
        self.metrics: DashboardMetricsSchema = DashboardMetricsSchema()

    def collect_all(self) -> "EntityCollector":
        """Execute full scan and metric aggregation."""
        self.issues.clear()
        self.milestones.clear()
        self.risks.clear()
        self.spikes.clear()
        self.sessions.clear()
        self.kb_articles.clear()
        self.decisions.clear()

        self._collect_issues()
        self._collect_milestones()
        self._collect_risks()
        self._collect_spikes()
        self._collect_sessions()
        self._collect_decisions()
        self._collect_kb_articles()
        self._collect_context_and_board()
        self._calculate_metrics()
        return self

    def _collect_issues(self):
        issues_dir = self.agents_dir / "ISSUES"
        if not issues_dir.exists():
            return

        files = list(issues_dir.glob("*.md")) + list(issues_dir.glob("done/*.md"))
        for f in files:
            if f.name.startswith(".") or f.name in ("ISSUES.md", "README.md"):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                slug = fm.get("slug") or f.stem
                if "--" in f.stem:
                    inferred_type, inferred_slug = f.stem.split("--", 1)
                else:
                    inferred_type, inferred_slug = "feat", f.stem

                entity_type = fm.get("type", inferred_type)
                entity_slug = fm.get("slug", inferred_slug)
                canonical_id = f"{entity_type}--{entity_slug}"

                # Extract title from markdown H1 if not in frontmatter
                title = fm.get("title")
                if not title:
                    h1_match = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
                    title = h1_match.group(1).strip() if h1_match else entity_slug

                # Ensure tags/blocked_by/related are lists
                tags = fm.get("tags") or []
                if isinstance(tags, str):
                    tags = [tags]
                blocked_by = fm.get("blocked_by") or []
                if isinstance(blocked_by, str):
                    blocked_by = [blocked_by]
                related = fm.get("related") or []
                if isinstance(related, str):
                    related = [related]

                status = fm.get("status", "done" if "done" in f.parts else "open")

                issue = IssueSchema(
                    protocol=fm.get("protocol", "along"),
                    id=canonical_id,
                    slug=entity_slug,
                    type=entity_type,
                    title=title,
                    status=status,
                    priority=fm.get("priority", "medium"),
                    created=str(fm.get("created", "")) if fm.get("created") else None,
                    updated=str(fm.get("updated", "")) if fm.get("updated") else None,
                    completed=str(fm.get("completed", "")) if fm.get("completed") else None,
                    agent=fm.get("agent"),
                    tags=tags,
                    milestone=fm.get("milestone"),
                    blocked_by=blocked_by,
                    related=related,
                    parent=fm.get("parent"),
                    body=body.strip(),
                    file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                )
                self.issues.append(issue)
            except Exception:
                continue

    def _collect_milestones(self):
        m_dir = self.agents_dir / "MILESTONES"
        if not m_dir.exists():
            return
        for f in m_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                slug = fm.get("slug", f.stem)
                target_issues = fm.get("target_issues") or []
                if isinstance(target_issues, str):
                    target_issues = [target_issues]

                milestone = MilestoneSchema(
                    protocol=fm.get("protocol", "along"),
                    id=f"milestone--{slug}",
                    slug=slug,
                    title=fm.get("title", slug),
                    status=fm.get("status", "open"),
                    due_date=str(fm.get("due_date", "")) if fm.get("due_date") else None,
                    created=str(fm.get("created", "")) if fm.get("created") else None,
                    target_issues=target_issues,
                    progress_pct=int(fm.get("progress_pct", 0)),
                    body=body.strip(),
                    file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                )
                self.milestones.append(milestone)
            except Exception:
                continue

    def _collect_risks(self):
        r_dir = self.agents_dir / "RISKS"
        if not r_dir.exists():
            return
        for f in r_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                slug = fm.get("slug", f.stem)
                risk = RiskSchema(
                    protocol=fm.get("protocol", "along"),
                    id=f"risk--{slug}",
                    slug=slug,
                    title=fm.get("title", slug),
                    severity=fm.get("severity", "medium"),
                    status=fm.get("status", "active"),
                    owner=fm.get("owner", "agent"),
                    mitigation=fm.get("mitigation"),
                    created=str(fm.get("created", "")) if fm.get("created") else None,
                    updated=str(fm.get("updated", "")) if fm.get("updated") else None,
                    body=body.strip(),
                    file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                )
                self.risks.append(risk)
            except Exception:
                continue

    def _collect_spikes(self):
        s_dir = self.agents_dir / "SPIKES"
        if not s_dir.exists():
            return
        for f in s_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                slug = fm.get("slug", f.stem)
                spike = SpikeSchema(
                    protocol=fm.get("protocol", "along"),
                    id=f"spike--{slug}",
                    slug=slug,
                    title=fm.get("title", slug),
                    status=fm.get("status", "hypothesis"),
                    hypothesis=fm.get("hypothesis"),
                    outcome=fm.get("outcome"),
                    resulting_adr=fm.get("resulting_adr"),
                    created=str(fm.get("created", "")) if fm.get("created") else None,
                    body=body.strip(),
                    file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                )
                self.spikes.append(spike)
            except Exception:
                continue

    def _collect_sessions(self):
        sess_dir = self.agents_dir / "SESSIONS"
        if not sess_dir.exists():
            return
        for f in sess_dir.rglob("*.md"):
            if f.is_file():
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    fm, body = parse_frontmatter(content)
                    date_val = fm.get("date", f.stem.split("--")[0] if "--" in f.stem else "")
                    slug = fm.get("slug", f.stem)
                    session = SessionSchema(
                        protocol=fm.get("protocol", "along"),
                        id=f"session--{f.stem}",
                        slug=slug,
                        date=str(date_val),
                        agent=fm.get("agent"),
                        branch=fm.get("branch"),
                        commit=fm.get("commit"),
                        summary=fm.get("summary", ""),
                        milestone=fm.get("milestone"),
                        issues_advanced=fm.get("issues_advanced") or [],
                        issues_completed=fm.get("issues_completed") or [],
                        decisions=fm.get("decisions") or [],
                        risks_logged=fm.get("risks_logged") or [],
                        spikes_conducted=fm.get("spikes_conducted") or [],
                        body=body.strip(),
                        file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                    )
                    self.sessions.append(session)
                except Exception:
                    continue
        self.sessions.sort(key=lambda s: s.date or "", reverse=True)

    def _collect_decisions(self):
        dec_file = self.agents_dir / "DECISIONS.md"
        if not dec_file.exists():
            return
        try:
            content = dec_file.read_text(encoding="utf-8", errors="replace")
            blocks = re.split(r"\n(?=##\s+)", content)
            num = 1
            for block in blocks:
                block = block.strip()
                if not block.startswith("##"):
                    continue
                first_line = block.splitlines()[0].replace("##", "").strip()
                match = re.match(r"(?:(\d{4}-\d{2}-\d{2})\s*[-:]\s*)?(?:#?(\d+)\s*[-:]\s*)?(.*)", first_line)
                date_str = match.group(1) if match else None
                title_str = match.group(3) if match and match.group(3) else first_line

                status = "Accepted"
                if "superseded by" in block.lower():
                    status = "Superseded"

                decision = DecisionSchema(
                    id=f"ADR-{num:03d}",
                    number=num,
                    title=title_str.strip(),
                    date=date_str,
                    status=status,
                    raw_markdown=block,
                )
                self.decisions.append(decision)
                num += 1
        except Exception:
            pass

    def _collect_kb_articles(self):
        kb_dirs = [self.repo_root / "docs", self.agents_dir / "KB"]
        seen_paths = set()

        for kb_dir in kb_dirs:
            if not kb_dir.exists():
                continue
            for f in kb_dir.rglob("*.md"):
                if f.name.startswith(".") or str(f) in seen_paths:
                    continue
                # Ignore .archive, archive, and raw source subdirectories
                parts = [p.lower() for p in f.parts]
                if any(p.startswith(".") or p in ["archive", ".archive", "raw", "sources"] for p in parts[:-1]):
                    continue
                seen_paths.add(str(f))
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    fm, body = parse_frontmatter(content)
                    slug = fm.get("slug", f.stem)
                    title = fm.get("title")
                    if not title:
                        h1_match = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
                        title = h1_match.group(1).strip() if h1_match else slug

                    # Extract headings
                    headings = [h.strip() for h in re.findall(r"^#{1,3}\s+(.*)$", body, re.MULTILINE)]

                    # Extract outgoing links [[link]] and [text](link.md)
                    wiki_links = re.findall(r"\[\[(.*?)\]\]", body)
                    md_links = [
                        m[1].split("#")[0].lstrip("./").replace(".md", "")
                        for m in re.findall(r"\[([^\]]+)\]\(([^)]+\.md(?:#[^)]*)?)\)", body)
                        if not m[1].startswith("http://") and not m[1].startswith("https://") and not m[1].startswith("file://")
                    ]
                    out_links = list(set(wiki_links + md_links))

                    tags = fm.get("tags") or []
                    if isinstance(tags, str):
                        tags = [tags]

                    article = KBArticleSchema(
                        id=f"kb--{slug}",
                        slug=slug,
                        title=title,
                        type=fm.get("type", "topic"),
                        created=str(fm.get("created", "")) if fm.get("created") else None,
                        updated=str(fm.get("updated", "")) if fm.get("updated") else None,
                        tags=tags,
                        file_path=str(f.relative_to(self.repo_root)).replace("\\", "/"),
                        body=body.strip(),
                        headings=headings,
                        outgoing_links=out_links,
                    )
                    self.kb_articles.append(article)
                except Exception:
                    continue

    def _collect_context_and_board(self):
        ctx_file = self.agents_dir / "CONTEXT.md"
        if ctx_file.exists():
            try:
                self.context_text = ctx_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        board_file = self.agents_dir / "ISSUES.md"
        if board_file.exists():
            try:
                self.issues_board_text = board_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    def _calculate_metrics(self):
        total = len(self.issues)
        by_status = StatusBreakdown()
        by_type = TypeBreakdown()
        by_priority = PriorityBreakdown()

        for iss in self.issues:
            # Status
            if iss.status == "done":
                by_status.done += 1
            elif iss.status == "in-progress":
                by_status.in_progress += 1
            elif iss.status == "blocked":
                by_status.blocked += 1
            else:
                by_status.open += 1

            # Type
            if iss.type == "bug":
                by_type.bug += 1
            elif iss.type == "debt":
                by_type.debt += 1
            elif iss.type == "task":
                by_type.task += 1
            elif iss.type == "docs":
                by_type.docs += 1
            else:
                by_type.feat += 1

            # Priority
            if iss.priority == "critical":
                by_priority.critical += 1
            elif iss.priority == "high":
                by_priority.high += 1
            elif iss.priority == "low":
                by_priority.low += 1
            else:
                by_priority.medium += 1

        completion_pct = int((by_status.done / total) * 100) if total > 0 else 0
        active_risks = sum(1 for r in self.risks if r.status == "active")
        active_milestones = sum(1 for m in self.milestones if m.status != "completed")

        self.metrics = DashboardMetricsSchema(
            total_issues=total,
            open_issues=by_status.open,
            in_progress_issues=by_status.in_progress,
            blocked_issues=by_status.blocked,
            done_issues=by_status.done,
            completion_pct=completion_pct,
            active_risks=active_risks,
            active_milestones=active_milestones,
            total_kb_articles=len(self.kb_articles),
            total_decisions=len(self.decisions),
            total_sessions=len(self.sessions),
            by_status=by_status,
            by_type=by_type,
            by_priority=by_priority,
            scan_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def to_full_data(self) -> FullDashboardDataSchema:
        """Export all data as FullDashboardDataSchema."""
        from .graph import build_entity_dag_graph
        graph_data = build_entity_dag_graph(self)
        return FullDashboardDataSchema(
            repo_name=self.repo_root.name,
            metrics=self.metrics,
            issues=self.issues,
            milestones=self.milestones,
            risks=self.risks,
            spikes=self.spikes,
            sessions=self.sessions,
            decisions=self.decisions,
            kb_articles=self.kb_articles,
            graph=graph_data,
            context_text=self.context_text,
            issues_board_text=self.issues_board_text,
        )

