"""
scripts/github_collector.py
Fetches Pull Requests (and their diff stats) from GitHub for a given user.
"""
from __future__ import annotations

import os
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_GH_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    token = os.environ.get("GH_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get(url: str, params: dict | None = None) -> Any:
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _paginate(url: str, params: dict | None = None) -> list[dict]:
    results: list[dict] = []
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    while True:
        params["page"] = page
        data = _get(url, params)
        if not data:
            break
        results.extend(data)
        if len(data) < params["per_page"]:
            break
        page += 1
    return results


def fetch_user_repos(username: str) -> list[dict]:
    """Return all repos the authenticated user has access to (own + all orgs)."""
    # /user/repos with affiliation=owner,collaborator,organization_member
    # returns everything the token can see — including private org repos.
    # Falls back to the public /users/{username}/repos if no token is present.
    if os.environ.get("GH_TOKEN"):
        url = f"{_GH_API}/user/repos"
        repos = _paginate(url, {"affiliation": "owner,collaborator,organization_member", "sort": "updated"})
    else:
        url = f"{_GH_API}/users/{username}/repos"
        repos = [
            r
            for r in _paginate(url, {"type": "all", "sort": "updated"})
            if not r.get("archived", False) and not r.get("disabled", False)
        ]
    logger.info("GitHub: found %d repos for %s", len(repos), username)
    return repos


def fetch_pr_details(pr: dict) -> dict:
    """Enrich a PR summary with file-change stats."""
    try:
        detail = _get(pr["url"])
        return {
            **pr,
            "additions": detail.get("additions", 0),
            "deletions": detail.get("deletions", 0),
            "changed_files": detail.get("changed_files", 0),
            "body": detail.get("body") or "",
        }
    except Exception as exc:
        logger.warning("Could not fetch PR details for %s: %s", pr.get("url"), exc)
        return {**pr, "additions": 0, "deletions": 0, "changed_files": 0, "body": ""}


def fetch_prs_for_repo(repo_full_name: str, username: str) -> list[dict]:
    url = f"{_GH_API}/repos/{repo_full_name}/pulls"
    prs = _paginate(url, {"state": "all", "sort": "updated"})
    mine = [p for p in prs if (p.get("user") or {}).get("login", "") == username]
    return [fetch_pr_details(p) for p in mine]


def fetch_pr_by_url(pr_url: str) -> dict | None:
    """Fetch a single PR given its HTML url (github.com/org/repo/pull/N)."""
    import re

    if not os.environ.get("GH_TOKEN"):
        logger.debug("Skipping PR fetch (no GH_TOKEN): %s", pr_url)
        return None

    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_url)
    if not m:
        return None
    repo, number = m.group(1), m.group(2)
    api_url = f"{_GH_API}/repos/{repo}/pulls/{number}"
    try:
        detail = _get(api_url)
        return {
            "number": detail["number"],
            "title": detail["title"],
            "url": detail["html_url"],
            "repo": repo,
            "state": detail["state"],
            "created_at": detail.get("created_at"),
            "merged_at": detail.get("merged_at"),
            "additions": detail.get("additions", 0),
            "deletions": detail.get("deletions", 0),
            "changed_files": detail.get("changed_files", 0),
            "body": detail.get("body") or "",
        }
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        if status in (403, 404):
            # Private repo or PR deleted — expected, not an error
            logger.debug("PR not accessible (HTTP %s): %s", status, pr_url)
        else:
            logger.warning("Could not fetch PR %s: %s", pr_url, exc)
        return None
    except Exception as exc:
        logger.warning("Could not fetch PR %s: %s", pr_url, exc)
        return None


def collect(username: str | None = None) -> list[dict]:
    """
    Fetch all PRs authored by `username` across their repos.
    Returns a flat list of enriched PR dicts.
    """
    username = username or os.environ["GH_USERNAME"]
    repos = fetch_user_repos(username)
    all_prs: list[dict] = []

    for repo in repos:
        full_name = repo["full_name"]
        prs = fetch_prs_for_repo(full_name, username)
        all_prs.extend(prs)
        if prs:
            logger.info("  %s → %d PRs", full_name, len(prs))

    logger.info("GitHub: total %d PRs collected", len(all_prs))
    return all_prs
