"""
src/analyzers/ai_enricher.py
Uses Anthropic's API to enrich Jira issue descriptions with:
  - Professional summary
  - CV-ready bullet point
  - Business impact statement
"""
from __future__ import annotations

import os
import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """You are an expert technical writer specializing in DevOps and Platform Engineering.
You transform raw Jira ticket data into polished portfolio content for senior engineers
targeting international remote positions (US/Europe).

Always respond with valid JSON only. No markdown, no explanation, just raw JSON."""

_PROMPT_TEMPLATE = """Given this Jira ticket:

Title: {summary}
Description: {description}
Issue Type: {issue_type}
Status: {status}

Generate a JSON object with exactly these keys:
- "enriched_summary": A 1-2 sentence professional description of the work done (past tense, active voice, technical precision)
- "cv_bullet": A single CV bullet point starting with a strong action verb (e.g. "Designed", "Implemented", "Automated"). Max 120 chars.
- "business_impact": A 1-sentence statement of measurable or strategic business impact (e.g. "Reduced deployment time by 60%", "Eliminated manual toil for X team")

Be specific, use technical language, and frame everything as demonstrable engineering value."""


def enrich_issue(issue: dict) -> dict:
    """
    Return the issue dict enriched with AI-generated fields.
    Falls back gracefully if the API key is missing or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return issue

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = _PROMPT_TEMPLATE.format(
            summary=issue.get("summary", ""),
            description=(issue.get("description") or "")[:1500],
            issue_type=issue.get("issue_type", "Task"),
            status=issue.get("status", ""),
        )

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        enriched = json.loads(raw)

        return {
            **issue,
            "enriched_summary": enriched.get("enriched_summary"),
            "cv_bullet": enriched.get("cv_bullet"),
            "business_impact": enriched.get("business_impact"),
        }

    except Exception as exc:
        logger.warning("AI enrichment failed for %s: %s", issue.get("key"), exc)
        return issue


def enrich_issues_batch(issues: list[dict]) -> list[dict]:
    """Enrich a list of issues, skipping those that already have enriched_summary."""
    if os.environ.get("USE_AI_ENRICHMENT", "true").lower() != "true":
        return issues
    return [
        enrich_issue(i) if not i.get("enriched_summary") else i
        for i in issues
    ]
