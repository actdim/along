"""Pydantic v2 schemas for Along Protocol entities."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class BaseEntitySchema(BaseModel):
    """Base model for all Along Protocol entities."""
    model_config = ConfigDict(extra="ignore")

    protocol: str = Field(default="along", description="Protocol identifier")
    slug: str = Field(..., description="Unique kebab-case slug of the entity")
    id: str = Field(..., description="Canonical entity identifier, e.g. feat--login")
    title: Optional[str] = Field(None, description="Human readable title")
    body: Optional[str] = Field(None, description="Markdown body content")
    file_path: Optional[str] = Field(None, description="Relative file path in repository")


class IssueSchema(BaseEntitySchema):
    """Schema for .along/ISSUES/<type>--<slug>.md."""
    type: Literal["feat", "bug", "debt", "task", "docs"] = Field(
        default="feat", description="Issue type"
    )
    status: Literal[
        "open",
        "in-progress",
        "blocked",
        "done",
        "superseded",
        "cancelled",
        "duplicate",
    ] = Field(
        default="open", description="Current lifecycle status"
    )
    priority: Literal["critical", "high", "medium", "low"] = Field(
        default="medium", description="Priority level"
    )
    created: Optional[str] = Field(None, description="Creation date YYYY-MM-DD")
    updated: Optional[str] = Field(None, description="Last update date YYYY-MM-DD")
    completed: Optional[str] = Field(None, description="Completion date YYYY-MM-DD")
    agent: Optional[str] = Field(None, description="Agent or author that worked on the issue")
    tags: List[str] = Field(default_factory=list, description="Array of topical tags")
    milestone: Optional[str] = Field(None, description="Milestone slug this issue belongs to")
    blocked_by: List[str] = Field(default_factory=list, description="List of blocking entity keys")
    related: List[str] = Field(default_factory=list, description="List of related entity keys")
    parent: Optional[str] = Field(None, description="Parent epic/entity key")
    superseded_by: Optional[str] = Field(None, description="Canonical entity key that supersedes this issue")
    duplicate_of: Optional[str] = Field(None, description="Canonical entity key this issue duplicates")


class MilestoneSchema(BaseEntitySchema):
    """Schema for .along/MILESTONES/<slug>.md."""
    status: Literal["open", "in-progress", "completed"] = Field(
        default="open", description="Milestone status"
    )
    due_date: Optional[str] = Field(None, description="Target due date YYYY-MM-DD")
    created: Optional[str] = Field(None, description="Creation date YYYY-MM-DD")
    target_issues: List[str] = Field(default_factory=list, description="Target issue slugs or keys")
    progress_pct: int = Field(default=0, ge=0, le=100, description="Completion percentage")


class RiskSchema(BaseEntitySchema):
    """Schema for .along/RISKS/<slug>.md."""
    severity: Literal["critical", "high", "medium", "low"] = Field(
        default="medium", description="Risk severity level"
    )
    status: Literal["active", "mitigated", "resolved"] = Field(
        default="active", description="Risk status"
    )
    owner: Optional[str] = Field("agent", description="Owner (agent or user)")
    mitigation: Optional[str] = Field(None, description="Mitigation strategy summary")
    created: Optional[str] = Field(None, description="Creation date YYYY-MM-DD")
    updated: Optional[str] = Field(None, description="Update date YYYY-MM-DD")


class SpikeSchema(BaseEntitySchema):
    """Schema for .along/SPIKES/<slug>.md."""
    status: Literal["hypothesis", "evaluating", "concluded"] = Field(
        default="hypothesis", description="Spike state"
    )
    hypothesis: Optional[str] = Field(None, description="Spike hypothesis statement")
    outcome: Optional[str] = Field(None, description="Spike outcome and conclusion")
    resulting_adr: Optional[str] = Field(None, description="Linked ADR in DECISIONS.md")
    created: Optional[str] = Field(None, description="Creation date YYYY-MM-DD")


class SessionSchema(BaseEntitySchema):
    """Schema for .along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<slug>.md."""
    date: str = Field(..., description="Session date YYYY-MM-DD")
    agent: Optional[str] = Field(None, description="Agent model/tool name")
    branch: Optional[str] = Field(None, description="Git branch name")
    commit: Optional[str] = Field(None, description="Git commit hash")
    summary: Optional[str] = Field(None, description="Summary of work completed")
    milestone: Optional[str] = Field(None, description="Associated milestone")
    issues_advanced: List[str] = Field(default_factory=list, description="Advanced issue keys")
    issues_completed: List[str] = Field(default_factory=list, description="Completed issue keys")
    decisions: List[str] = Field(default_factory=list, description="Recorded ADR numbers/titles")
    risks_logged: List[str] = Field(default_factory=list, description="Logged risk keys")
    spikes_conducted: List[str] = Field(default_factory=list, description="Conducted spike keys")


class DecisionSchema(BaseModel):
    """Schema for an ADR entry in .along/DECISIONS.md."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Decision identifier, e.g. ADR-001")
    number: Optional[int] = Field(None, description="Sequential ADR number")
    title: str = Field(..., description="Decision title")
    date: Optional[str] = Field(None, description="Date recorded YYYY-MM-DD")
    status: str = Field(default="Accepted", description="ADR status (Accepted, Superseded, etc.)")
    context: Optional[str] = Field(None, description="Context and problem description")
    decision: Optional[str] = Field(None, description="Decision made")
    consequences: Optional[str] = Field(None, description="Consequences and trade-offs")
    superseded_by: Optional[str] = Field(None, description="ADR identifier that supersedes this")
    raw_markdown: Optional[str] = Field(None, description="Full raw markdown of the entry")

