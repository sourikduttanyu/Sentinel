# Sentinel — Multi-Agent PR Review System

> Stateful multi-agent system that reviews GitHub Pull Requests using LangGraph orchestration, Semgrep static analysis, and Claude AI. Built in 7 days.

## Status

| Day | Phase | Status |
|-----|-------|--------|
| 1 | Plumbing — GitHub App auth, webhook, LangGraph skeleton | ✅ Complete |
| 2 | SecurityAgent — Semgrep + Claude structured analysis | ✅ Complete |
| 3 | DocsAgent — docstring gap detection | ✅ Complete |
| 4 | SupervisorAgent — aggregation, dedup, ranked markdown | ✅ Complete |
| 5 | Human-in-the-loop gate + GitHub comment post | ✅ Complete |
| 6 | Real PR run + metrics capture | ✅ Complete |
| 7 | Polish + demo prep | ✅ Complete |

## What It Does

When a PR is opened or updated on GitHub:

1. **GitHub App** fires a webhook to Sentinel's FastAPI server
2. **Diff + file contents** fetched via GitHub App JWT auth
3. **SecurityAgent + DocsAgent run in parallel:**
   - SecurityAgent runs Semgrep on changed files, sends output + diff to Claude Haiku → structured findings ranked by severity
   - DocsAgent sends diff to Claude Haiku → flags missing/stale docstrings on changed functions
4. **SupervisorAgent** aggregates both, deduplicates, resolves conflicts, produces ranked markdown review
5. **Graph pauses** — human approves via `POST /approve/{run_id}`
6. **Sentinel posts** the review as a GitHub PR comment

Every node traced end-to-end in LangSmith. Graph state checkpointed to SQLite — survives restarts.

## Architecture

```
GitHub Webhook (PR opened/synchronize)
          ↓
    FastAPI /webhook
          ↓
    LangGraph Graph ──────────────────────────────────┐
          ↓                                            │
  ┌───────────────┐                          SqliteSaver
  │ SecurityAgent │ ← Semgrep + Claude Haiku  checkpoint
  └───────┬───────┘
          │  (parallel)
  ┌───────────────┐
  │   DocsAgent   │ ← Claude Haiku
  └───────┬───────┘
          ↓
   SupervisorAgent ← Claude Haiku
          ↓
   [INTERRUPT] ── human approves via POST /approve/{run_id}
          ↓
   Post GitHub PR Comment
```

## Key Metrics (measured on real PRs)

| Metric | Value |
|---|---|
| End-to-end latency (clean PR) | 4.68s |
| End-to-end latency (6 findings, 3 LLM calls) | 15.13s |
| Semgrep raw findings | 6 |
| Claude final findings after filtering | 4–5 |
| Contextual findings Claude added vs Semgrep | 1 (debug endpoint exposure) |
| LLM calls per review | 3 (Security + Docs + Supervisor) |
| Checkpoint recovery | SqliteSaver → Redis (planned) |

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.1.10 |
| LLM | Claude Haiku (claude-haiku-4-5-20251001) |
| Static Analysis | Semgrep (auto ruleset) |
| Webhook Server | FastAPI + uvicorn |
| GitHub Integration | GitHub App — JWT → installation token |
| Observability | LangSmith (auto-traced) |
| State Persistence | SqliteSaver → Redis (planned) |
| Language | Python 3.13 |

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

## How to Approve a Review

After Sentinel processes a PR, the graph pauses waiting for human approval:

```bash
curl -X POST http://localhost:8000/approve/{run_id}
```

`run_id` is returned in the webhook response and printed in server logs.

## Project Structure

```
sentinel/
├── api/webhook.py          # FastAPI — webhook receiver + approve endpoint
├── agents/
│   ├── security_agent.py   # Semgrep + Claude → structured security findings
│   ├── docs_agent.py       # Claude → docstring gap detection
│   └── supervisor_agent.py # Aggregation, dedup, ranked markdown review
├── graph/workflow.py       # LangGraph graph definition + SqliteSaver
├── tools/
│   ├── semgrep_tool.py     # Semgrep subprocess wrapper
│   └── github_tool.py      # GitHub App JWT auth + API calls
├── models/state.py         # PRReviewState TypedDict
├── config.py               # dotenv loader
└── main.py                 # FastAPI entrypoint
```

## Resume Bullets

**AI Engineer framing:**
> Engineered a production LangGraph multi-agent system with LangSmith observability — orchestrating SecurityAgent (Semgrep + Claude), DocsAgent, and SupervisorAgent with parallel execution, SqliteSaver state persistence, and human-in-the-loop approval gates. Achieved 15s end-to-end latency on PRs with findings; Claude reduced Semgrep false positives and identified 1 contextual issue (debug endpoint exposure) that raw static analysis missed.

**Agentic AI framing:**
> Architected a stateful multi-agent PR review system in LangGraph — 3 parallel specialized agents, interrupt-based human approval gate, SqliteSaver checkpoint recovery, and GitHub App JWT auth. End-to-end LangSmith tracing across all agent decisions. Supervisor resolves cross-agent conflicts and produces ranked review comments posted directly to GitHub.
