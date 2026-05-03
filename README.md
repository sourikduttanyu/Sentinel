# Sentinel — Multi-Agent PR Review System

Sentinel is a stateful multi-agent system that automatically reviews GitHub Pull Requests using LangGraph orchestration, Semgrep static analysis, and Claude AI.

## What It Does

When a PR is opened or updated, Sentinel:

1. **Receives** the GitHub webhook event via FastAPI
2. **Fetches** the PR diff using GitHub App authentication
3. **Runs two agents in parallel:**
   - **SecurityAgent** — scans the diff with Semgrep, then uses Claude to analyze findings and rank severity
   - **DocsAgent** — uses Claude to detect missing or stale docstrings in changed functions
4. **SupervisorAgent** aggregates findings, deduplicates, resolves conflicts, and produces a structured review
5. **Human-in-the-loop gate** — review is held until a human approves via API call
6. **Posts** the final review as a GitHub PR comment

Every agent decision is traced end-to-end in LangSmith.

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
| Orchestration | LangGraph |
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

## Project Status

Active development — Day 1 complete (GitHub App auth, webhook receiver, LangGraph skeleton).
