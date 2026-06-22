"""
src/models/portfolio.py
Pydantic data models for the portfolio pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Skill(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    mentions: int = 0


class PullRequest(BaseModel):
    number: int
    title: str
    url: str
    repo: str
    state: str
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0
    description: Optional[str] = None           # AI-enriched


class JiraIssue(BaseModel):
    key: str
    summary: str
    description: Optional[str] = None
    issue_type: str
    status: str
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    pull_requests: list[PullRequest] = []
    skills: list[Skill] = []
    enriched_summary: Optional[str] = None      # AI-enriched
    cv_bullet: Optional[str] = None             # AI-enriched
    business_impact: Optional[str] = None       # AI-enriched


class Epic(BaseModel):
    key: str
    summary: str
    description: Optional[str] = None
    status: str
    tasks: list[JiraIssue] = []
    skills: list[Skill] = []
    enriched_summary: Optional[str] = None


class Metrics(BaseModel):
    total_epics: int = 0
    total_tasks: int = 0
    total_prs: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    avg_delivery_days: Optional[float] = None
    top_skills: list[Skill] = []


class Portfolio(BaseModel):
    name: str
    role: str
    location: str
    github_url: str
    linkedin_url: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    epics: list[Epic] = []
    standalone_tasks: list[JiraIssue] = []
    metrics: Metrics = Field(default_factory=Metrics)
