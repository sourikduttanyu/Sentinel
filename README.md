# Sentinel — Multi-Agent PR Review System | LangGraph + Claude + Semgrep + Human-in-the-Loop

> A production-grade multi-agent system that automates pull request security, performance, and documentation review using a LangGraph supervisor architecture, Claude LLM, and Semgrep static analysis — with human-in-the-loop approval before any comment is posted.

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue?style=flat) ![LangGraph 1.1.10](https://img.shields.io/badge/LangGraph-1.1.10-orange?style=flat) ![FastAPI](https://img.shields.io/badge/FastAPI-latest-green?style=flat) ![LangSmith](https://img.shields.io/badge/LangSmith-traced-purple?style=flat)

---

## What This Demonstrates

- **Multi-agent orchestration** — Three specialized agents (security, docs, performance) run in parallel inside a LangGraph StateGraph, coordinated by a SupervisorAgent that deduplicates and ranks findings
- **System design thinking** — Event-driven webhook architecture, durable state checkpointing, human-in-the-loop interrupt, and a clear path to horizontal scale (see [FUTURE.md](./FUTURE.md))
- **Hybrid reasoning pipeline** — Combines deterministic SAST (Semgrep) with LLM contextual reasoning (Claude) to reduce false positives and surface issues pattern matching alone cannot find
- **Production-grade observability** — End-to-end LangSmith tracing per node, Prometheus metrics at `GET /metrics`, and a benchmarking script that computes p50/p95/p99 latency from server logs
- **Cost discipline** — Measured cost per review ($0.003–$0.016), token counts, and LLM call budget tracked on real PRs — not just theoretical

---

## Why This Exists

Code review is a bottleneck. Security issues slip through not because reviewers do not care, but because they are reviewing logic rather than running static analysis and reading every docstring in context. Sentinel is an agentic code review automation system that does the mechanical part — running Semgrep, querying Claude, aggregating findings — so human reviewers can focus on what matters.

---

## How It Works

When a PR is opened or updated:

1. GitHub App fires a webhook to Sentinel's FastAPI server
2. PR diff and changed file contents are fetched via JWT-authenticated GitHub API
3. **SecurityAgent**, **DocsAgent**, and **PerformanceAgent** run in parallel:
   - SecurityAgent runs Semgrep on changed files, sends findings + diff to Claude — structured severity-ranked issues
   - DocsAgent sends diff to Claude — flags missing or stale docstrings on changed functions
   - PerformanceAgent sends diff to Claude — detects N+1 queries, unbounded queries, sync I/O in hot paths, inefficient loops, missing pagination
4. **SupervisorAgent** aggregates all three agents, deduplicates, resolves conflicts, produces ranked markdown review
5. Graph pauses — human approves via `POST /approve/{run_id}`
6. Sentinel posts the final review as a GitHub PR comment

Every node is traced end-to-end in LangSmith. Graph state is checkpointed to SQLite and survives server restarts.

---

## Architecture

```
GitHub Webhook
       ↓
 FastAPI /webhook
       ↓
 LangGraph (SqliteSaver checkpoint)
       ↓
 ┌──────────────┬──────────────┬──────────────────┐
 │SecurityAgent │  DocsAgent   │PerformanceAgent  │  ← parallel
 │Semgrep+Claude│    Claude    │     Claude       │
 └──────┬───────┴──────┬───────┴───────┬──────────┘
        └──────────────┼───────────────┘
                       ↓
              SupervisorAgent
                       ↓
              [INTERRUPT — human approval]
                       ↓
              POST /approve/{run_id}
                       ↓
              GitHub PR Comment
```

---

## LangSmith Trace

![LangSmith Trace](./docs/langsmith-trace.png)

*Three parallel nodes (security, docs, performance), per-node latency breakdown, token counts, full state visible at each step*

---

## Measured on Real PRs

| Metric | Value |
|---|---|
| Latency — clean PR (no findings) | 4.68s |
| Latency — PR with 6 findings, 3 LLM calls | 15.13s |
| Semgrep raw findings | 6 |
| Claude findings after filtering | 4–5 |
| Contextual issues Claude caught vs Semgrep | 1 (debug endpoint exposure) |
| LLM calls per review | 4 (Security + Docs + Performance + Supervisor) |
| Cost per review — with findings | ~$0.016 |
| Cost per review — clean PR | ~$0.003 |
| Tokens per full review | ~7,500–7,800 |

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.1.10 |
| LLM | Claude Haiku (claude-haiku-4-5-20251001) |
| Static Analysis | Semgrep (auto ruleset) |
| Webhook Server | FastAPI + uvicorn |
| GitHub Integration | GitHub App — JWT → installation token |
| Observability | LangSmith + Prometheus (`GET /metrics`) |
| State Persistence | SqliteSaver (SQLite) |
| Language | Python 3.13 |

---

## Setup

> Full step-by-step instructions including GitHub App creation: **[SETUP.md](./SETUP.md)**

```bash
git clone https://github.com/sourikduttanyu/Sentinel
cd Sentinel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
python main.py
```

Required environment variables:

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

## Approving a Review

After Sentinel processes a PR the graph pauses. Approve to post:

```bash
curl -X POST http://localhost:8000/approve/{run_id}
```

`run_id` is printed in server logs and returned in the webhook response.

---

## Project Structure

```
sentinel/
├── api/webhook.py              # Webhook receiver + /approve endpoint + Prometheus instrumentation
├── agents/
│   ├── security_agent.py       # Semgrep + Claude → structured security findings
│   ├── docs_agent.py           # Claude → docstring gap detection
│   ├── performance_agent.py    # Claude → N+1, unbounded queries, sync I/O, inefficient loops
│   └── supervisor_agent.py     # Aggregation, dedup, conflict resolution, ranked markdown
├── graph/workflow.py           # LangGraph graph + SqliteSaver checkpointer
├── tools/
│   ├── semgrep_tool.py         # Semgrep subprocess wrapper
│   └── github_tool.py          # GitHub App JWT auth + API calls
├── models/state.py             # PRReviewState TypedDict
├── scripts/
│   └── benchmark.py            # Parses server logs → min/avg/p50/p95/p99/stddev latency
├── config.py
└── main.py                     # FastAPI app + GET /metrics (Prometheus)
```

---

## Technical Highlights

### Contextual reasoning over static analysis

This is the core design decision that makes Sentinel useful rather than noisy. Semgrep provides pattern-matched SAST findings across changed files. Claude receives those findings *plus the full diff* and does two things: it filters Semgrep results that do not apply given the surrounding code, and it adds findings that pattern matching structurally cannot detect.

In one measured run, Claude identified a debug endpoint where the route handler contained an RCE vulnerability, the inline comment said "not for production," but the route was still registered and live. Semgrep matched nothing; Claude caught it. This Semgrep + Claude pipeline took 6 raw findings to 4–5 high-confidence, actionable issues.

### Parallel agent execution

SecurityAgent, DocsAgent, and PerformanceAgent are all edges from `START` in the LangGraph `StateGraph`. LangGraph runs all three in a thread pool simultaneously. Each writes to a separate state key so there is no collision. SupervisorAgent reads all three after they complete. Adding a fourth agent requires one new node and one new edge — no graph restructuring.

### Human-in-the-loop

Graph compiled with `interrupt_before=["post_comment"]`. State is checkpointed to SQLite via `SqliteSaver` after every node. Calling `/approve/{run_id}` resumes the exact graph run from where it paused — survives server restarts.

### Observability

Every node is traced end-to-end in LangSmith (inputs, outputs, token usage, per-node latency). Prometheus metrics exposed at `GET /metrics`: `sentinel_reviews_total`, `sentinel_review_latency_seconds` (histogram), `sentinel_findings_total` by agent. `scripts/benchmark.py` parses server logs to compute p50/p95/p99 latency across runs.

---

## Production Architecture

For scale, Sentinel's architecture evolves along four axes:

- **Queue-backed execution** — SQS decouples webhook intake from graph execution; N workers process reviews concurrently with no shared state
- **Redis checkpointing** — Replaces SQLite `SqliteSaver` with Redis for horizontal scaling and cross-node state access
- **Retrieval-augmented review** — Embed codebase context (past findings, coding standards) into the SecurityAgent and PerformanceAgent prompts via vector search
- **Eval harness** — Label 10–20 historical PRs with ground-truth findings; measure precision/recall across Semgrep-only vs full Sentinel pipeline

Full production design: **[FUTURE.md](./FUTURE.md)**
