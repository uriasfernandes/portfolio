# devops-portfolio — Contexto para Claude

> Este arquivo é o ponto de partida para continuar o desenvolvimento via **Claude Code** (`claude` no terminal) ou **VS Code**.
> Contém todo o histórico de decisões, bugs conhecidos e próximos passos.

---

## O que é este projeto

Pipeline Python que transforma **Jira + GitHub → portfólio público no GitHub Pages**.

```
Jira API → GitHub API → Skill Analyzer → AI Enricher → Portfolio Builder → site/ + site-public/
```

- `site/`         — dados completos (uso local, **nunca commitar**)
- `site-public/`  — sanitizado, sem dados internos (deploy via GHA)

---

## Stack

| Item | Decisão |
|---|---|
| Python | 3.14 (local), 3.12 (GHA) |
| Package manager | `uv` |
| Modelos de dados | Pydantic v2 |
| Templates HTML | Jinja2 |
| CI/CD | GitHub Actions → GitHub Pages |
| AI (opcional) | Anthropic SDK (`claude-sonnet-4-6`) |

---

## Estrutura de arquivos

```
my-portfolio/
├── .github/workflows/deploy.yml   # GHA: uv sync + uv run + deploy Pages
├── scripts/
│   ├── main.py                    # orquestrador principal
│   ├── jira_collector.py          # GET /rest/api/3/search/jql
│   ├── github_collector.py        # GET /user/repos (autenticado)
│   ├── pr_extractor.py            # cruza URLs de PRs com tickets Jira
│   ├── portfolio_builder.py       # monta modelo Pydantic + métricas
│   └── diff_check.py              # valida o que vazou no site-public/
├── src/
│   ├── models/portfolio.py        # Portfolio, Epic, JiraIssue, PullRequest, Skill, Metrics
│   ├── analyzers/skill_analyzer.py # detecção rule-based de 40+ tecnologias
│   ├── analyzers/ai_enricher.py   # enrich via Anthropic API
│   └── analyzers/sanitizer.py     # remove dados internos para output público
├── templates/index.html.j2        # site GitHub Pages (dark theme)
├── pyproject.toml
├── .env                           # NÃO commitar
└── .gitignore                     # bloqueia site/ e .env; permite site-public/
```

---

## Comandos do dia a dia

```bash
# Instalar dependências
uv sync

# Run completo (com GitHub, sem AI)
uv run python -m scripts.main --no-ai

# Run completo com AI
uv run python -m scripts.main

# Só Jira, sem GitHub, sem AI — mais rápido para testar
uv run python -m scripts.main --no-ai --no-github

# Dry-run (não gera arquivos)
uv run python -m scripts.main --dry-run --no-github --no-ai

# Verificar se site-public/ está limpo (sem dados internos)
uv run python -m scripts.diff_check

# Preview local
uv run python -m http.server 9000 --directory site          # dados completos
uv run python -m http.server 9001 --directory site-public   # versão pública
```

---

## Variáveis de ambiente (.env)

```bash
# Jira
JIRA_BASE_URL=https://casamagalhaes.atlassian.net
JIRA_EMAIL=urias@...
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=DEVOPS

# GitHub
GH_TOKEN=ghp_...          # Classic PAT com scope `repo` + SSO autorizado para casamagalhaes
GH_USERNAME=uriasfernandes

# Portfolio
PORTFOLIO_NAME=Urias Fernandes
PORTFOLIO_ROLE=DevOps / Platform Engineer
PORTFOLIO_LOCATION=Brazil · Open to Remote (US/EU)
PORTFOLIO_GITHUB=https://github.com/uriasfernandes
PORTFOLIO_LINKEDIN=https://linkedin.com/in/uriasfernandes

# AI (opcional)
ANTHROPIC_API_KEY=sk-ant-...
USE_AI_ENRICHMENT=true
```

---

## GitHub Actions secrets / variables

### Secrets
| Nome | Valor |
|---|---|
| `JIRA_BASE_URL` | URL do Jira |
| `JIRA_EMAIL` | email |
| `JIRA_API_TOKEN` | token Jira |
| `GH_PAT` | Classic PAT (não usar `GITHUB_*`) |
| `ANTHROPIC_API_KEY` | opcional |

### Variables
| Nome | Valor |
|---|---|
| `JIRA_PROJECT_KEY` | `DEVOPS` |
| `GH_USERNAME` | `uriasfernandes` |
| `PORTFOLIO_NAME` | nome |
| `PORTFOLIO_ROLE` | cargo |
| `PORTFOLIO_LOCATION` | localização |
| `PORTFOLIO_GITHUB` | URL GitHub |
| `PORTFOLIO_LINKEDIN` | URL LinkedIn |

> ⚠️ GitHub reserva o prefixo `GITHUB_` — usar `GH_*` para variáveis próprias.

---

## Bug ativo: site-public/ mostrando dados internos

### Sintoma
`site-public/portfolio.json` contém chaves Jira (`DEVOPS-3345`), URLs de repos internos
(`casamagalhaes/tf-aws-vs-cm-resources`) e descrições brutas dos tickets.

### O que já foi verificado
- O `sanitizer.py` funciona corretamente quando testado isoladamente
- O `main.py` chama `sanitize(portfolio)` antes de escrever `site-public/`
- O JSON colado pelo usuário pode ter sido do `site/` (não do `site-public/`)

### Diagnóstico pendente — rodar na raiz do projeto

```bash
python3 -c "
import json
for f in ['site/portfolio.json', 'site-public/portfolio.json']:
    d = json.load(open(f))
    e = d['epics'][0]
    tasks = e.get('tasks', [])
    pr_url = tasks[0]['pull_requests'][0]['url'] if tasks and tasks[0].get('pull_requests') else 'no PR'
    print(f'{f}:')
    print(f'  key         = {e[\"key\"]!r}')
    print(f'  description = {repr((e[\"description\"] or \"\")[:60])}')
    print(f'  pr.url      = {pr_url!r}')
    print()
"
```

### Resultado esperado para site-public/
```
key         = ''
description = None
pr.url      = ''
```

### Se ainda vazar — próximo passo
Verificar se o arquivo `src/analyzers/sanitizer.py` local está atualizado.
O conteúdo correto começa com:
```python
def _sanitize_issue(issue: JiraIssue) -> JiraIssue:
    return JiraIssue(
        key="",                   # ← deve estar assim
        description=None,         # ← deve estar assim
```

---

## Bugs corrigidos (histórico)

| Bug | Fix |
|---|---|
| `410 Gone` no Jira | endpoint atualizado para `/rest/api/3/search/jql` |
| `GITHUB_*` rejeitado pelo GHA | renomeado para `GH_TOKEN` e `GH_USERNAME` |
| `tool.uv.dev-dependencies` deprecated | migrado para `[dependency-groups]` |
| `model_dump_json(mode="json")` inválido | removido argumento `mode` |
| 403/404 em repos privados sem token | `fetch_pr_by_url` retorna `None` silenciosamente se sem `GH_TOKEN` |
| `GET /users/{username}/repos` não retorna repos de orgs | trocado para `GET /user/repos?affiliation=owner,collaborator,organization_member` |
| PR duplicado (url html + url api) | issue conhecida, a investigar |

---

## Próximos passos sugeridos

- [ ] Resolver bug do sanitizer (diagnóstico acima)
- [ ] Remover PRs duplicados — mesmo PR aparece com `url` html e `url` api
- [ ] Habilitar AI enrichment e validar qualidade dos `cv_bullet` gerados
- [ ] Fazer primeiro deploy no GitHub Pages e validar URL pública
- [ ] Adicionar `uv run python -m scripts.diff_check` como step no GHA (falha o build se vazar dados)

---

## Referências rápidas

- Jira API: `GET {JIRA_BASE_URL}/rest/api/3/search/jql`
- GitHub API repos: `GET https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member`
- GitHub Pages deploy action: `actions/deploy-pages@v4`
- uv docs: https://docs.astral.sh/uv/
