# 🚀 DevOps Portfolio Generator

> Transforms your Jira tickets + GitHub PRs into a public, professional portfolio — automatically.

**Live example:** `https://<your-username>.github.io/devops-portfolio/`

---

## What it does

| Input | Output |
|---|---|
| Jira Epics / Tasks / Stories / Bugs | `site/portfolio.json` — structured data |
| GitHub Pull Requests | `site/index.html` — GitHub Pages site |
| Anthropic Claude (optional) | AI-enriched summaries + CV bullets |

The pipeline runs daily via GitHub Actions and keeps your portfolio fresh without any manual work.

---

## Quick start

### 1. Clone & configure

```bash
git clone https://github.com/<you>/devops-portfolio
cd devops-portfolio
cp .env.example .env
# Fill in .env with your credentials
```

### 2. Install dependencies

```bash
# instalar uv (uma vez só, globalmente)
pip install uv

# criar o venv e instalar dependências
uv sync
```

### 3. Run locally

```bash
uv run python -m scripts.main              # full pipeline with AI
uv run python -m scripts.main --no-ai      # skip AI enrichment
uv run python -m scripts.main --no-github  # skip GitHub
uv run python -m scripts.main --dry-run    # preview without writing files
```

The site is generated in `./site/`. Open `site/index.html` in a browser to preview.

---

## GitHub Actions setup

### Required Secrets (Settings → Secrets → Actions)

| Secret | Value |
|---|---|
| `JIRA_BASE_URL` | `https://yourcompany.atlassian.net` |
| `JIRA_EMAIL` | your Jira email |
| `JIRA_API_TOKEN` | [create here](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `GH_PAT` | GitHub Personal Access Token (read:repo) |
| `ANTHROPIC_API_KEY` | your Anthropic API key (optional) |

### Required Variables (Settings → Variables → Actions)

| Variable | Value |
|---|---|
| `JIRA_PROJECT_KEY` | e.g. `DEVOPS` |
| `GH_USERNAME` | your GitHub username |
| `PORTFOLIO_NAME` | Your Full Name |
| `PORTFOLIO_ROLE` | e.g. `DevOps / Platform Engineer` |
| `PORTFOLIO_LOCATION` | e.g. `Brazil · Open to Remote (US/EU)` |
| `PORTFOLIO_GITHUB` | `https://github.com/your_username` |
| `PORTFOLIO_LINKEDIN` | `https://linkedin.com/in/your_profile` |

### Enable GitHub Pages

1. Go to **Settings → Pages**
2. Source: **GitHub Actions**
3. Push to `main` or trigger manually → your site is live!

---

## Architecture

```
Jira API  ──┐
             ├─► Data Processing (Python)
GitHub API ──┘        │
                       ▼
               Skill Analyzer (rule-based)
                       │
               AI Enricher (Anthropic Claude, optional)
                       │
               Portfolio Builder (Pydantic)
                  │           │
            portfolio.json  index.html
                  └─────┬─────┘
                  GitHub Actions
                        │
                  GitHub Pages 🌐
```

---

## Skill detection

Skills are detected automatically from ticket text and PR descriptions using a keyword map covering:

- **Cloud:** AWS (EC2, ECS, Fargate, RDS, S3, Lambda, IAM, VPC…)
- **IaC:** Terraform, Terragrunt, Ansible, CloudFormation
- **Containers:** Docker, Kubernetes, Helm
- **CI/CD:** GitHub Actions, ArgoCD, Jenkins, GitLab CI
- **Observability:** Grafana, Prometheus, Loki, Tempo, Mimir, OpenTelemetry
- **Languages:** Python, Bash, Go

---

## AI enrichment (optional)

When `ANTHROPIC_API_KEY` is set, each ticket gets:

- **`enriched_summary`** — professional past-tense description
- **`cv_bullet`** — single-line CV bullet starting with an action verb
- **`business_impact`** — measurable/strategic impact statement

Example:

| Raw | AI-enriched |
|---|---|
| `"Created ECS cluster"` | `"Designed and implemented scalable AWS ECS infrastructure to support containerized workloads, reducing provisioning time by 80%"` |

---

## Roadmap

- [x] MVP: Jira + GitHub + GitHub Pages
- [ ] V2: GitLab MR support
- [ ] V2: PDF CV export
- [ ] V3: FastAPI backend + PostgreSQL history
- [ ] V3: LinkedIn integration
- [ ] V3: AWS ECS/Fargate + CloudFront deploy

---

## License

MIT
