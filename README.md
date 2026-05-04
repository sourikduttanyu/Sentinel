# Sentinel — Multi-Agent PR Review System

Sentinel is a stateful multi-agent system that automatically reviews GitHub Pull Requests using LangGraph orchestration, Semgrep static analysis, and Claude AI.

## Status

| Day | Phase | Status |
|-----|-------|--------|
| 1 | Plumbing — webhook, auth, graph skeleton | ✅ Complete |
| 2 | SecurityAgent — Semgrep + Claude analysis | ✅ Complete |
| 3 | DocsAgent — docstring detection | ✅ Complete |
| 4 | SupervisorAgent — aggregation + conflict resolution | ✅ Complete |
| 5 | Human-in-the-loop gate + GitHub comment post | ✅ Complete |
| 6 | Real PR run + metrics capture | ⬜ Todo |
| 7 | Polish + demo prep | ⬜ Todo |

See [PHASES.md](./PHASES.md) for detailed task tracking.

## What It Does

When a PR is opened or updated, Sentinel:

1. **Receives** the GitHub webhook event via FastAPI
2. **Fetches** the PR diff using GitHub App authentication
3. **Runs two agents in parallel:**
   - **SecurityAgent** — scans with Semgrep, then uses Claude to analyze and rank findings
   - **DocsAgent** — uses Claude to detect missing or stale docstrings in changed functions
4. **SupervisorAgent** aggregates findings, deduplicates, resolves conflicts, produces structured review
5. **Human-in-the-loop gate** — review held until approved via `POST /approve/{run_id}`
6. **Posts** final review as GitHub PR comment

Every agent decision traced end-to-end in LangSmith.

## Architecture

```
GitHub Webhook
      ↓
FastAPI (/webhook)
      ↓
LangGraph Graph
      ↓
[SecurityAgent ‖ DocsAgent]  ← parallel execution
      ↓
SupervisorAgent
      ↓
Human Approval Gate (interrupt)
      ↓
GitHub PR Comment
```

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.1.10 |
| LLM | Claude (Anthropic) — Haiku for agents, Sonnet for supervisor |
| Static Analysis | Semgrep |
| Webhook Server | FastAPI |
| GitHub Integration | GitHub App (JWT auth) |
| Observability | LangSmith |
| State Persistence | SQLite (SqliteSaver) → Redis planned |

## Metrics Instrumented

- End-to-end PR review latency (target: <45s)
- Tool call success rate per agent (target: 95%+)
- False positive rate vs raw Semgrep baseline
- Cost per PR review (Haiku vs Sonnet)
- LangSmith traces: nodes fired, branching paths, tool calls

## Setup

```bash
git clone https://github.com/sourikduttanyu/Sentinel
cd Sentinel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
python main.py
```

## Environment Variables

```
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY_PATH=./keys/sentinel.pem
GITHUB_WEBHOOK_SECRET=
GITHUB_INSTALLATION_ID=

ANTHROPIC_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=sentinel
```
