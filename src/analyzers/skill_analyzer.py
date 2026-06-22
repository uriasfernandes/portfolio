"""
src/analyzers/skill_analyzer.py
Rule-based skill detection with weighted scoring.
"""
from __future__ import annotations

import re
from collections import defaultdict

# ── Keyword → (skill_name, base_score) ──────────────────────────────────────
SKILL_MAP: list[tuple[re.Pattern, str, int]] = [
    # Cloud
    (re.compile(r"\baws\b|\bamazon web services\b", re.I), "AWS", 90),
    (re.compile(r"\bec2\b", re.I), "AWS EC2", 85),
    (re.compile(r"\becs\b|elastic container", re.I), "AWS ECS", 85),
    (re.compile(r"\bfargate\b", re.I), "AWS Fargate", 85),
    (re.compile(r"\brds\b|\baurora\b", re.I), "AWS RDS", 80),
    (re.compile(r"\bs3\b", re.I), "AWS S3", 80),
    (re.compile(r"\bcloudfront\b", re.I), "AWS CloudFront", 78),
    (re.compile(r"\biam\b", re.I), "AWS IAM", 78),
    (re.compile(r"\bvpc\b", re.I), "AWS VPC", 78),
    (re.compile(r"\blambda\b", re.I), "AWS Lambda", 80),
    (re.compile(r"\bcloudwatch\b", re.I), "AWS CloudWatch", 78),
    # IaC
    (re.compile(r"\bterraform\b", re.I), "Terraform", 92),
    (re.compile(r"\bterragrunt\b", re.I), "Terragrunt", 85),
    (re.compile(r"\bpulumi\b", re.I), "Pulumi", 80),
    (re.compile(r"\bansible\b", re.I), "Ansible", 85),
    (re.compile(r"\bcfn\b|cloudformation", re.I), "CloudFormation", 80),
    # Containers & orchestration
    (re.compile(r"\bdocker\b|dockerfile", re.I), "Docker", 88),
    (re.compile(r"\bkubernetes\b|\bk8s\b", re.I), "Kubernetes", 90),
    (re.compile(r"\bhelm\b", re.I), "Helm", 82),
    # CI/CD
    (re.compile(r"\bgithub actions\b", re.I), "GitHub Actions", 88),
    (re.compile(r"\bjenkins\b", re.I), "Jenkins", 80),
    (re.compile(r"\bargo\b|argocd", re.I), "ArgoCD", 85),
    (re.compile(r"\bgitlab ci\b", re.I), "GitLab CI", 82),
    # Observability
    (re.compile(r"\bgrafana\b", re.I), "Grafana", 85),
    (re.compile(r"\bloki\b", re.I), "Loki", 82),
    (re.compile(r"\btempo\b", re.I), "Tempo", 80),
    (re.compile(r"\bmimir\b", re.I), "Mimir", 80),
    (re.compile(r"\bprometheus\b", re.I), "Prometheus", 88),
    (re.compile(r"\bopentelemetry\b|otel\b", re.I), "OpenTelemetry", 82),
    (re.compile(r"\bdatadog\b", re.I), "Datadog", 80),
    # Languages
    (re.compile(r"\bpython\b", re.I), "Python", 85),
    (re.compile(r"\bbash\b|shell script", re.I), "Bash/Shell", 80),
    (re.compile(r"\bgo\b|golang\b", re.I), "Go", 80),
    # Networking / Linux
    (re.compile(r"\blinux\b", re.I), "Linux", 85),
    (re.compile(r"\bnginx\b", re.I), "Nginx", 78),
    (re.compile(r"\bdns\b", re.I), "DNS", 75),
    (re.compile(r"\bssl\b|\btls\b", re.I), "SSL/TLS", 75),
    # DB / storage
    (re.compile(r"\bpostgres\b|postgresql", re.I), "PostgreSQL", 78),
    (re.compile(r"\bmysql\b", re.I), "MySQL", 75),
    (re.compile(r"\bredis\b", re.I), "Redis", 78),
    # Security
    (re.compile(r"\bvault\b", re.I), "HashiCorp Vault", 82),
    (re.compile(r"\bsonarqube\b", re.I), "SonarQube", 75),
    (re.compile(r"\btrivy\b|\bsnyk\b", re.I), "Container Security", 78),
]


def detect_skills(text: str) -> list[dict]:
    """Return skills detected in `text`, sorted by score descending."""
    if not text:
        return []

    counts: dict[str, int] = defaultdict(int)
    scores: dict[str, int] = {}

    for pattern, skill, base_score in SKILL_MAP:
        matches = pattern.findall(text)
        if matches:
            counts[skill] += len(matches)
            scores[skill] = base_score

    return sorted(
        [{"name": k, "score": scores[k], "mentions": counts[k]} for k in scores],
        key=lambda x: (-x["score"], -x["mentions"]),
    )


def aggregate_skills(skill_lists: list[list[dict]]) -> list[dict]:
    """Merge multiple skill lists, summing mentions and taking max score."""
    agg: dict[str, dict] = {}
    for skills in skill_lists:
        for s in skills:
            if s["name"] not in agg:
                agg[s["name"]] = {"name": s["name"], "score": s["score"], "mentions": 0}
            agg[s["name"]]["mentions"] += s["mentions"]
            agg[s["name"]]["score"] = max(agg[s["name"]]["score"], s["score"])
    return sorted(agg.values(), key=lambda x: (-x["score"], -x["mentions"]))
