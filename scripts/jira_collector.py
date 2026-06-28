"""
scripts/jira_collector.py
Fetches Epics, Tasks, Stories and Bugs from Jira for the current user.
"""
from __future__ import annotations

import os
import re
import logging
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# ── Regex patterns to detect GitHub / GitLab links inside Jira text ──────────
_GH_PR_RE = re.compile(
    r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", re.IGNORECASE
)
_GL_MR_RE = re.compile(
    r"https://gitlab\.com/([^/]+(?:/[^/]+)+)/-/merge_requests/(\d+)", re.IGNORECASE
)


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(
        os.environ["JIRA_EMAIL"],
        os.environ["JIRA_API_TOKEN"],
    )


def _base() -> str:
    return os.environ["JIRA_BASE_URL"].rstrip("/")


def _extract_pr_urls(text: str | None) -> list[str]:
    if not text:
        return []
    urls: list[str] = []
    for m in _GH_PR_RE.finditer(text):
        urls.append(m.group(0))
    for m in _GL_MR_RE.finditer(text):
        urls.append(m.group(0))
    return urls


def _search(jql: str, fields: list[str], max_results: int = 200) -> list[dict]:
    """Paginate through Jira search results."""
    url = f"{_base()}/rest/api/3/search/jql"
    results: list[dict] = []
    start = 0

    while True:
        resp = requests.get(
            url,
            auth=_auth(),
            params={
                "jql": jql,
                "fields": ",".join(fields),
                "maxResults": min(max_results, 100),
                "startAt": start,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])
        results.extend(issues)
        start += len(issues)
        if start >= data.get("total", 0) or not issues:
            break

    logger.info("Jira JQL '%s' → %d issues", jql, len(results))
    return results


def _text_from_adf(node: Any) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        parts = [_text_from_adf(child) for child in node.get("content", [])]
        return " ".join(p for p in parts if p)
    if isinstance(node, list):
        return " ".join(_text_from_adf(item) for item in node)
    return ""


def _parse_issue(raw: dict) -> dict:
    f = raw["fields"]
    desc_raw = f.get("description") or ""
    desc_text = _text_from_adf(desc_raw) if isinstance(desc_raw, dict) else str(desc_raw)

    # collect PR urls from description + comments
    pr_urls = _extract_pr_urls(desc_text)
    for comment in (f.get("comment") or {}).get("comments", []):
        body = _text_from_adf(comment.get("body", ""))
        pr_urls.extend(_extract_pr_urls(body))

    # also check issuelinks for remote links
    for link in f.get("issuelinks") or []:
        obj = link.get("object") or {}
        pr_urls.extend(_extract_pr_urls(obj.get("url", "")))

    return {
        "key": raw["key"],
        "summary": f.get("summary", ""),
        "description": desc_text,
        "issue_type": (f.get("issuetype") or {}).get("name", "Task"),
        "status": (f.get("status") or {}).get("name", ""),
        "created": f.get("created"),
        "updated": f.get("updated"),
        "epic_link": f.get("customfield_10014") or f.get("customfield_10008"),
        "pr_urls": list(set(pr_urls)),
    }


FIELDS = [
    "summary",
    "description",
    "issuetype",
    "status",
    "created",
    "updated",
    "issuelinks",
    "comment",
    "customfield_10014",  # Epic Link (classic)
    "customfield_10008",  # Epic Link (next-gen)
]


def fetch_epics(project: str) -> list[dict]:
    jql = (
        f'project = "{project}" AND issuetype = Epic '
        f"AND (reporter = currentUser() OR assignee = currentUser()) "
        f"ORDER BY created DESC"
    )
    return [_parse_issue(r) for r in _search(jql, FIELDS)]


def fetch_tasks(project: str) -> list[dict]:
    jql = (
        f'project = "{project}" AND issuetype in (Task, Story, Bug, Sub-task) '
        f"AND (reporter = currentUser() OR assignee = currentUser()) "
        f"ORDER BY created DESC"
    )
    return [_parse_issue(r) for r in _search(jql, FIELDS)]


def collect(project: str | None = None) -> dict[str, list[dict]]:
    project = project or os.environ.get("JIRA_PROJECT_KEY", "DEVOPS")
    epics = fetch_epics(project)
    tasks = fetch_tasks(project)
    return {"epics": epics, "tasks": tasks}
