"""
src/analyzers/sanitizer.py

Sanitizes a Portfolio model for public output (GitHub Pages).

What gets removed / replaced:
  - Jira issue keys          DEVOPS-123  → omitted
  - Internal repo names      casamagalhaes/tf-aws-vs-cm-resources → "Private Repository"
  - PR URLs                  https://github.com/org/repo/pull/N → omitted
  - Raw Jira descriptions    (may contain internal details) → replaced by enriched_summary
  - Epic / task summaries    kept only when an enriched_summary exists, otherwise genericised

What is KEPT (it's the whole point of the portfolio):
  - Skills + scores
  - Metrics (total PRs, additions, delivery time…)
  - enriched_summary, cv_bullet, business_impact  ← the AI-polished content
  - Dates / timeline
  - Status
"""
from __future__ import annotations

import copy
import re
from src.models.portfolio import Epic, JiraIssue, Metrics, Portfolio, PullRequest, Skill

# ── helpers ──────────────────────────────────────────────────────────────────

_JIRA_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def _clean_text(text: str | None) -> str | None:
    """Remove Jira keys from free text."""
    if not text:
        return text
    return _JIRA_KEY_RE.sub("", text).strip() or None


def _public_title(issue: JiraIssue) -> str:
    """
    Return a public-safe title for an issue.
    Priority: enriched_summary > cv_bullet > scrubbed raw summary > generic fallback.
    """
    if issue.enriched_summary:
        return _clean_text(issue.enriched_summary) or f"{issue.issue_type} · {issue.status}"
    if issue.cv_bullet:
        return _clean_text(issue.cv_bullet) or f"{issue.issue_type} · {issue.status}"
    # Strip Jira keys from the raw summary and use it if it still has content
    scrubbed = _clean_text(issue.summary)
    if scrubbed:
        return scrubbed
    # Last resort — skill hints only
    skills_hint = ", ".join(s.name for s in issue.skills[:3])
    if skills_hint:
        return f"{issue.issue_type} involving {skills_hint}"
    return f"{issue.issue_type} · {issue.status}"


def _sanitize_pr(pr: PullRequest) -> PullRequest:
    """Keep diff stats but strip URL and repo name."""
    return PullRequest(
        number=pr.number,
        title="Pull Request",           # no internal title
        url="",                         # no internal URL
        repo="Private Repository",
        state=pr.state,
        created_at=pr.created_at,
        merged_at=pr.merged_at,
        additions=pr.additions,
        deletions=pr.deletions,
        files_changed=pr.files_changed,
        description=None,
    )


def _sanitize_issue(issue: JiraIssue) -> JiraIssue:
    return JiraIssue(
        key="",                                         # no Jira key
        summary=_public_title(issue),
        description=None,                               # no raw description
        issue_type=issue.issue_type,
        status=issue.status,
        created=issue.created,
        updated=issue.updated,
        pull_requests=[_sanitize_pr(pr) for pr in issue.pull_requests],
        skills=issue.skills,
        enriched_summary=_clean_text(issue.enriched_summary),
        cv_bullet=_clean_text(issue.cv_bullet),
        business_impact=_clean_text(issue.business_impact),
    )


def _sanitize_epic(epic: Epic) -> Epic:
    public_summary = (
        _clean_text(epic.enriched_summary)
        or _clean_text(epic.summary)
        or "Infrastructure Initiative"
    )
    return Epic(
        key="",                                         # no Jira key
        summary=public_summary,
        description=None,
        status=epic.status,
        tasks=[_sanitize_issue(t) for t in epic.tasks],
        skills=epic.skills,
        enriched_summary=_clean_text(epic.enriched_summary),
    )


# ── public API ────────────────────────────────────────────────────────────────

def sanitize(portfolio: Portfolio) -> Portfolio:
    """
    Return a deep-copied Portfolio with all internal identifiers removed.
    The original object is not mutated.
    """
    return Portfolio(
        name=portfolio.name,
        role=portfolio.role,
        location=portfolio.location,
        github_url=portfolio.github_url,
        linkedin_url=portfolio.linkedin_url,
        generated_at=portfolio.generated_at,
        epics=[_sanitize_epic(e) for e in portfolio.epics],
        standalone_tasks=[_sanitize_issue(t) for t in portfolio.standalone_tasks],
        metrics=portfolio.metrics,   # metrics are already aggregate — safe to keep as-is
    )
