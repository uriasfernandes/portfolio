"""
scripts/main.py
Main orchestrator for the DevOps Portfolio pipeline.

Usage:
    python -m scripts.main
    python -m scripts.main --no-ai       # skip AI enrichment
    python -m scripts.main --no-github   # skip GitHub PR collection
    python -m scripts.main --dry-run     # don't write files
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

# ── Local imports ─────────────────────────────────────────────────────────────
from scripts.jira_collector import collect as jira_collect
from scripts.github_collector import collect as github_collect
from scripts.pr_extractor import enrich_tasks_with_prs
from scripts.portfolio_builder import build as portfolio_build
from src.analyzers.ai_enricher import enrich_issues_batch
from src.analyzers.sanitizer import sanitize

console = Console()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DevOps Portfolio Generator")
    p.add_argument("--no-ai", action="store_true", help="Skip AI enrichment")
    p.add_argument("--no-github", action="store_true", help="Skip GitHub collection")
    p.add_argument("--dry-run", action="store_true", help="Don't write output files")
    p.add_argument("--public", action="store_true", help="Also generate sanitized public site in site-public/")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    setup_logging(args.verbose)

    if args.no_ai:
        os.environ["USE_AI_ENRICHMENT"] = "false"

    # ── Validate required env vars ────────────────────────────────────────────
    missing = [v for v in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN") if not os.environ.get(v)]
    if missing:
        console.print(f"[red]Missing env vars: {', '.join(missing)}[/red]")
        console.print("Copy [cyan].env.example[/cyan] → [cyan].env[/cyan] and fill in credentials.")
        return 1

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:

        # 1. Jira
        task_id = progress.add_task("Collecting Jira issues…", total=None)
        jira_data = jira_collect()
        progress.update(task_id, description=f"✅ Jira: {len(jira_data['epics'])} epics, {len(jira_data['tasks'])} tasks")
        progress.stop_task(task_id)

        # 2. GitHub
        all_prs: list[dict] = []
        if not args.no_github and os.environ.get("GH_USERNAME"):
            task_id = progress.add_task("Collecting GitHub PRs…", total=None)
            all_prs = github_collect()
            progress.update(task_id, description=f"✅ GitHub: {len(all_prs)} PRs")
            progress.stop_task(task_id)

        # 3. Link PRs → tasks
        task_id = progress.add_task("Linking PRs to Jira issues…", total=None)
        if not os.environ.get("GH_TOKEN"):
            progress.update(task_id, description="⚠️  PR linking skipped (GH_TOKEN not set)")
        else:
            jira_data["tasks"] = enrich_tasks_with_prs(jira_data["tasks"], all_prs)
            progress.update(task_id, description="✅ PR linking complete")
        progress.stop_task(task_id)

        # 4. AI enrichment
        if not args.no_ai and os.environ.get("ANTHROPIC_API_KEY"):
            task_id = progress.add_task("AI-enriching issue descriptions…", total=None)
            jira_data["tasks"] = enrich_issues_batch(jira_data["tasks"])
            jira_data["epics"] = enrich_issues_batch(jira_data["epics"])
            progress.update(task_id, description="✅ AI enrichment complete")
            progress.stop_task(task_id)

        # 5. Build portfolio model
        task_id = progress.add_task("Building portfolio model…", total=None)
        portfolio = portfolio_build(
            jira_data,
            name=os.environ.get("PORTFOLIO_NAME", "DevOps Engineer"),
            role=os.environ.get("PORTFOLIO_ROLE", "DevOps / Platform Engineer"),
            location=os.environ.get("PORTFOLIO_LOCATION", "Remote"),
            github_url=os.environ.get("PORTFOLIO_GITHUB", "#"),
            linkedin_url=os.environ.get("PORTFOLIO_LINKEDIN", "#"),
        )
        progress.update(task_id, description="✅ Portfolio model built")
        progress.stop_task(task_id)

        # 6. Generate outputs
        if not args.dry_run:
            jinja_env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
            tmpl = jinja_env.get_template("index.html.j2")

            def write_site(p: "Portfolio", directory: str) -> None:
                site_dir = Path(directory)
                site_dir.mkdir(exist_ok=True)
                (site_dir / "portfolio.json").write_text(p.model_dump_json(indent=2), encoding="utf-8")
                (site_dir / "index.html").write_text(tmpl.render(portfolio=p), encoding="utf-8")

            # Full site (local — contains internal data)
            task_id = progress.add_task("Writing site/ (full)…", total=None)
            write_site(portfolio, "site")
            progress.update(task_id, description="✅ site/  (full, local only)")
            progress.stop_task(task_id)

            # Public site (sanitized — safe to commit)
            task_id = progress.add_task("Writing site-public/ (sanitized)…", total=None)
            public_portfolio = sanitize(portfolio)
            write_site(public_portfolio, "site-public")
            progress.update(task_id, description="✅ site-public/  (sanitized, safe to publish)")
            progress.stop_task(task_id)

    console.print("\n[bold green]✨ Portfolio generated successfully![/bold green]")
    console.print(f"  📄 site/          → full data  (local preview only)")
    console.print(f"  🌐 site-public/   → sanitized  (safe to commit & publish)")
    console.print(f"  📊 {portfolio.metrics.total_epics} epics · {portfolio.metrics.total_tasks} tasks · {portfolio.metrics.total_prs} PRs")
    console.print("\n[dim]Verify sanitization:[/dim]")
    console.print("  [dim]uv run python -m scripts.diff_check[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
