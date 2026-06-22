"""
scripts/pr_extractor.py
Links Jira issues to GitHub PRs via:
  1. PR URLs embedded in Jira description / comments
  2. Jira issue keys referenced in PR titles / bodies (e.g. DEVOPS-42)
"""
from __future__ import annotations

import re
import logging
from scripts.github_collector import fetch_pr_by_url

logger = logging.getLogger(__name__)

_JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def enrich_tasks_with_prs(
    tasks: list[dict],
    all_prs: list[dict],
) -> list[dict]:
    """
    For every Jira task, attach matching PRs from:
      - direct PR URLs stored in task["pr_urls"]
      - any GitHub PR whose title/body mentions the task key
    """
    # index PRs by Jira key mentions
    key_to_prs: dict[str, list[dict]] = {}
    for pr in all_prs:
        text = f"{pr.get('title','')} {pr.get('body','')}"
        for key in _JIRA_KEY_RE.findall(text):
            key_to_prs.setdefault(key, []).append(pr)

    enriched = []
    for task in tasks:
        matched: dict[str, dict] = {}  # url → pr dict

        # 1. Direct URLs embedded in Jira
        for url in task.get("pr_urls", []):
            pr = fetch_pr_by_url(url)
            if pr:
                matched[pr["url"]] = pr

        # 2. PRs that mention this Jira key
        for pr in key_to_prs.get(task["key"], []):
            matched[pr["url"]] = pr

        enriched.append({**task, "pull_requests": list(matched.values())})

    return enriched
