"""Pydantic v2 schemas for dashboard metrics and summary reports."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from .entities import IssueSchema, MilestoneSchema, RiskSchema, SpikeSchema, SessionSchema, DecisionSchema
from .kb import KBArticleSchema, KBGraphSchema


class StatusBreakdown(BaseModel):
    open: int = 0
    in_progress: int = 0
    blocked: int = 0
    done: int = 0
    superseded: int = 0
    cancelled: int = 0
    duplicate: int = 0


class TypeBreakdown(BaseModel):
    feat: int = 0
    bug: int = 0
    debt: int = 0
    task: int = 0
    docs: int = 0


class PriorityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class DashboardMetricsSchema(BaseModel):
    """Aggregated project metrics."""
    total_issues: int = 0
    open_issues: int = 0
    in_progress_issues: int = 0
    blocked_issues: int = 0
    done_issues: int = 0
    completion_pct: int = 0
    bug_debt_ratio: float = 0.0
    active_risks: int = 0
    active_milestones: int = 0
    total_kb_articles: int = 0
    total_decisions: int = 0
    total_sessions: int = 0
    by_status: StatusBreakdown = Field(default_factory=StatusBreakdown)
    by_type: TypeBreakdown = Field(default_factory=TypeBreakdown)
    by_priority: PriorityBreakdown = Field(default_factory=PriorityBreakdown)
    scan_timestamp: str = ""


class FullDashboardDataSchema(BaseModel):
    """Complete dataset for dashboard SPA."""
    repo_name: str
    metrics: DashboardMetricsSchema
    issues: List[IssueSchema] = Field(default_factory=list)
    milestones: List[MilestoneSchema] = Field(default_factory=list)
    risks: List[RiskSchema] = Field(default_factory=list)
    spikes: List[SpikeSchema] = Field(default_factory=list)
    sessions: List[SessionSchema] = Field(default_factory=list)
    decisions: List[DecisionSchema] = Field(default_factory=list)
    kb_articles: List[KBArticleSchema] = Field(default_factory=list)
    graph: Dict[str, Any] = Field(default_factory=dict)
    context_text: str = ""
    issues_board_text: str = ""

