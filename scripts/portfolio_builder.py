"""
scripts/portfolio_builder.py
Assembles raw Jira + GitHub data into a Portfolio model with metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from statistics import mean

from src.models.portfolio import (
    Epic, JiraIssue, Metrics, Portfolio, PullRequest, Skill
)
from src.analyzers.skill_analyzer import detect_skills, aggregate_skills

logger = logging.getLogger(__name__)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_pr(raw: dict) -> PullRequest:
    return PullRequest(
        number=raw.get("number", 0),
        title=raw.get("title", ""),
        url=raw.get("url") or raw.get("html_url", ""),
        repo=raw.get("repo", ""),
        state=raw.get("state", ""),
        created_at=_parse_dt(raw.get("created_at")),
        merged_at=_parse_dt(raw.get("merged_at")),
        additions=raw.get("additions", 0),
        deletions=raw.get("deletions", 0),
        files_changed=raw.get("changed_files", raw.get("files_changed", 0)),
        description=raw.get("enriched_summary"),
    )


def _build_issue(raw: dict) -> JiraIssue:
    text = f"{raw.get('summary','')} {raw.get('description','')}"
    skills = [Skill(**s) for s in detect_skills(text)]
    prs = [_build_pr(p) for p in raw.get("pull_requests", [])]
    return JiraIssue(
        key=raw["key"],
        summary=raw.get("summary", ""),
        description=raw.get("description"),
        issue_type=raw.get("issue_type", "Task"),
        status=raw.get("status", ""),
        created=_parse_dt(raw.get("created")),
        updated=_parse_dt(raw.get("updated")),
        pull_requests=prs,
        skills=skills,
        enriched_summary=raw.get("enriched_summary"),
        cv_bullet=raw.get("cv_bullet"),
        business_impact=raw.get("business_impact"),
    )


def build(
    jira_data: dict[str, list[dict]],
    *,
    name: str,
    role: str,
    location: str,
    github_url: str,
    linkedin_url: str,
) -> Portfolio:
    raw_epics = jira_data.get("epics", [])
    raw_tasks = jira_data.get("tasks", [])

    # Map epic key → tasks
    epic_map: dict[str, list[dict]] = {e["key"]: [] for e in raw_epics}
    standalone: list[dict] = []

    for task in raw_tasks:
        elink = task.get("epic_link")
        if elink and elink in epic_map:
            epic_map[elink].append(task)
        else:
            standalone.append(task)

    # Build Epic objects
    epics: list[Epic] = []
    for raw_epic in raw_epics:
        tasks = [_build_issue(t) for t in epic_map[raw_epic["key"]]]
        all_skills = aggregate_skills([t.skills_as_dicts() for t in tasks])
        epic_text = f"{raw_epic.get('summary','')} {raw_epic.get('description','')}"
        epic_skills = aggregate_skills([detect_skills(epic_text), all_skills])

        epics.append(Epic(
            key=raw_epic["key"],
            summary=raw_epic.get("summary", ""),
            description=raw_epic.get("description"),
            status=raw_epic.get("status", ""),
            tasks=tasks,
            skills=[Skill(**s) for s in epic_skills[:10]],
            enriched_summary=raw_epic.get("enriched_summary"),
        ))

    standalone_issues = [_build_issue(t) for t in standalone]

    # ── Metrics ──────────────────────────────────────────────────────────────
    all_issues = [t for e in epics for t in e.tasks] + standalone_issues
    all_prs = [pr for i in all_issues for pr in i.pull_requests]

    delivery_days: list[float] = []
    for issue in all_issues:
        if issue.created:
            for pr in issue.pull_requests:
                if pr.merged_at:
                    delta = (pr.merged_at - issue.created).total_seconds() / 86400
                    if delta > 0:
                        delivery_days.append(delta)

    all_skill_lists = [
        [{"name": s.name, "score": s.score, "mentions": s.mentions} for s in i.skills]
        for i in all_issues
    ]
    top_skills = aggregate_skills(all_skill_lists)[:15]

    metrics = Metrics(
        total_epics=len(epics),
        total_tasks=len(all_issues),
        total_prs=len(all_prs),
        total_additions=sum(p.additions for p in all_prs),
        total_deletions=sum(p.deletions for p in all_prs),
        avg_delivery_days=round(mean(delivery_days), 1) if delivery_days else None,
        top_skills=[Skill(**s) for s in top_skills],
    )

    return Portfolio(
        name=name,
        role=role,
        location=location,
        github_url=github_url,
        linkedin_url=linkedin_url,
        epics=epics,
        standalone_tasks=standalone_issues,
        metrics=metrics,
    )


# Patch JiraIssue to expose skills as dicts (avoids circular import)
def _skills_as_dicts(self) -> list[dict]:
    return [{"name": s.name, "score": s.score, "mentions": s.mentions} for s in self.skills]

JiraIssue.skills_as_dicts = _skills_as_dicts  # type: ignore[attr-defined]
