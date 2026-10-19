"""Entities REST API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from ..schemas.entities import (
    IssueSchema,
    MilestoneSchema,
    RiskSchema,
    SpikeSchema,
    SessionSchema,
    DecisionSchema,
)
from ..core.collector import EntityCollector

router = APIRouter(prefix="/entities", tags=["Entities"])


def get_collector() -> EntityCollector:
    # Collector instance is injected by app.state
    raise NotImplementedError


@router.get("/issues", response_model=List[IssueSchema], summary="List all issues")
def list_issues(
    status: Optional[str] = Query(None, description="Filter by status (open, in-progress, blocked, done)"),
    type: Optional[str] = Query(None, description="Filter by type (feat, bug, debt, task, docs, spike)"),
    priority: Optional[str] = Query(None, description="Filter by priority (critical, high, medium, low)"),
    milestone: Optional[str] = Query(None, description="Filter by milestone slug"),
    collector: EntityCollector = Depends(get_collector),
):
    collector.collect_all()
    results = collector.issues
    if status:
        results = [i for i in results if i.status == status]
    if type:
        results = [i for i in results if i.type == type]
    if priority:
        results = [i for i in results if i.priority == priority]
    if milestone:
        results = [i for i in results if i.milestone == milestone]
    return results


@router.get("/issues/{issue_id}", response_model=IssueSchema, summary="Get issue details")
def get_issue(issue_id: str, collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    for iss in collector.issues:
        if iss.id == issue_id or iss.slug == issue_id:
            return iss
    raise HTTPException(status_code=404, detail=f"Issue '{issue_id}' not found")


@router.get("/milestones", response_model=List[MilestoneSchema], summary="List all milestones")
def list_milestones(collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    return collector.milestones


@router.get("/risks", response_model=List[RiskSchema], summary="List all risks")
def list_risks(collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    return collector.risks


@router.get("/spikes", response_model=List[SpikeSchema], summary="List all spikes")
def list_spikes(collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    return collector.spikes


@router.get("/sessions", response_model=List[SessionSchema], summary="List all session logs")
def list_sessions(collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    return collector.sessions


@router.get("/decisions", response_model=List[DecisionSchema], summary="List all ADR decisions")
def list_decisions(collector: EntityCollector = Depends(get_collector)):
    collector.collect_all()
    return collector.decisions

