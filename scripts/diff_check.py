"""
scripts/diff_check.py
Compares site/ (full) vs site-public/ (sanitized) and reports what was stripped.

Usage:
    uv run python -m scripts.diff_check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()

_JIRA_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
_GITHUB_URL_RE = re.compile(r"https://github\.com/[^\s\"']+")


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Not found: {path}[/red]")
        console.print("Run [cyan]uv run python -m scripts.main --no-ai[/cyan] first.")
        sys.exit(1)
    return json.loads(p.read_text())


def all_strings(obj, _acc=None) -> list[str]:
    """Recursively collect all string values from a JSON object."""
    if _acc is None:
        _acc = []
    if isinstance(obj, str):
        _acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            all_strings(v, _acc)
    elif isinstance(obj, list):
        for item in obj:
            all_strings(item, _acc)
    return _acc


def find_leaks(strings: list[str]) -> dict[str, list[str]]:
    leaks: dict[str, list[str]] = {"jira_keys": [], "github_urls": []}
    for s in strings:
        keys = _JIRA_KEY_RE.findall(s)
        urls = _GITHUB_URL_RE.findall(s)
        leaks["jira_keys"].extend(keys)
        leaks["github_urls"].extend(urls)
    # deduplicate preserving order
    leaks["jira_keys"] = list(dict.fromkeys(leaks["jira_keys"]))
    leaks["github_urls"] = list(dict.fromkeys(leaks["github_urls"]))
    return leaks


def main() -> int:
    full = load("site/portfolio.json")
    pub  = load("site-public/portfolio.json")

    full_strings = all_strings(full)
    pub_strings  = all_strings(pub)

    full_leaks = find_leaks(full_strings)
    pub_leaks  = find_leaks(pub_strings)

    # ── Summary table ─────────────────────────────────────────────────────────
    table = Table(title="Sanitization check", show_header=True)
    table.add_column("Item", style="dim")
    table.add_column("site/ (full)", justify="right")
    table.add_column("site-public/ (sanitized)", justify="right")
    table.add_column("Status")

    def row(label, full_val, pub_val, ok_when):
        status = "✅" if ok_when(pub_val) else "❌ LEAK"
        style = "green" if ok_when(pub_val) else "red"
        table.add_row(label, str(full_val), str(pub_val), f"[{style}]{status}[/{style}]")

    row("Jira keys found",   len(full_leaks["jira_keys"]),   len(pub_leaks["jira_keys"]),   lambda v: v == 0)
    row("GitHub URLs found", len(full_leaks["github_urls"]), len(pub_leaks["github_urls"]), lambda v: v == 0)
    row("Total string values", len(full_strings), len(pub_strings), lambda v: True)

    console.print(table)

    # ── Detail on leaks ───────────────────────────────────────────────────────
    if pub_leaks["jira_keys"]:
        console.print("\n[red bold]Jira keys still present in site-public/:[/red bold]")
        for k in pub_leaks["jira_keys"][:20]:
            console.print(f"  {k}")

    if pub_leaks["github_urls"]:
        console.print("\n[red bold]GitHub URLs still present in site-public/:[/red bold]")
        for u in pub_leaks["github_urls"][:20]:
            console.print(f"  {u}")

    if not pub_leaks["jira_keys"] and not pub_leaks["github_urls"]:
        console.print("\n[green bold]✅ site-public/ is clean — safe to commit and publish.[/green bold]")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
