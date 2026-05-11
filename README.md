# Sentinel — Multi-Agent PR Review System | LangGraph + Claude + Semgrep + Human-in-the-Loop

> A production-grade multi-agent system that automates pull request security, performance, and documentation review using a LangGraph supervisor architecture, pluggable LLM backends, and Semgrep static analysis — with human-in-the-loop approval before any comment is posted.

![Python 3.13](https://img.shields.io/badge/Python-3.13-blue?style=flat) ![LangGraph 1.1.10](https://img.shields.io/badge/LangGraph-1.1.10-orange?style=flat) ![FastAPI](https://img.shields.io/badge/FastAPI-latest-green?style=flat) ![LangSmith](https://img.shields.io/badge/LangSmith-traced-purple?style=flat)

---

## What This Demonstrates

- **Multi-agent orchestration** — Three specialized agents (security, docs, performance) run in parallel inside a LangGraph StateGraph, coordinated by a SupervisorAgent that deduplicates and ranks findings
- **MCP server** — Sentinel exposes `review_pr` and `approve_review` as MCP tools; any MCP client (Claude Desktop, Cursor) can trigger and approve reviews without touching the HTTP API
- **Pluggable LLM backends** — Switch between Anthropic, Gemini, and OpenAI via `LLM_BACKEND` + `LLM_MODEL` env vars; no code changes required
- **System design thinking** — Event-driven webhook architecture, durable state checkpointing, human-in-the-loop interrupt, and a clear path to horizontal scale (see [FUTURE.md](./FUTURE.md))
- **Hybrid reasoning pipeline** — Combines deterministic SAST (Semgrep) with LLM contextual reasoning to reduce false positives and surface issues pattern matching alone cannot find
- **Production-grade observability** — End-to-end LangSmith tracing per node, Prometheus metrics at `GET /metrics`, and a benchmarking script that computes p50/p95/p99 latency from server logs
- **Cost discipline** — Measured cost per review ($0.003–$0.016), token counts, and LLM call budget tracked on real PRs — not just theoretical

---

## Why This Exists

Code review is a bottleneck. Security issues slip through not because reviewers do not care, but because they are reviewing logic rather than running static analysis and reading every docstring in context. Sentinel is an agentic code review automation system that does the mechanical part — running Semgrep, querying the LLM, aggregating findings — so human reviewers can focus on what matters.

---

## How It Works

When a PR is opened or updated:

1. GitHub App fires a webhook to Sentinel's FastAPI server
2. PR diff and changed file contents are fetched via JWT-authenticated GitHub API
3. **SecurityAgent**, **DocsAgent**, and **PerformanceAgent** run in parallel:
   - SecurityAgent runs Semgrep on changed files, sends findings + diff to the LLM — structured severity-ranked issues
   - DocsAgent sends diff to the LLM — flags missing or stale docstrings on changed functions
   - PerformanceAgent sends diff to the LLM — detects N+1 queries, unbounded queries, sync I/O in hot paths, inefficient loops, missing pagination
4. **SupervisorAgent** aggregates all three agents, deduplicates, resolves conflicts, produces ranked markdown review
5. Graph pauses — human approves via `POST /approve/{run_id}` or the `approve_review` MCP tool
6. Sentinel posts the final review as a GitHub PR comment

Every node is traced end-to-end in LangSmith. Graph state is checkpointed to SQLite and survives server restarts.

---

## Architecture

```
GitHub Webhook            MCP Client (Claude Desktop / Cursor)
       ↓                              ↓
 FastAPI /webhook           mcp_server.py (stdio)
       ↓                              ↓
       └──────────────┬───────────────┘
                      ↓
             LangGraph StateGraph
            (SqliteSaver checkpoint)
                      ↓
 ┌──────────────┬──────────────┬──────────────────┐
 │SecurityAgent │  DocsAgent   │PerformanceAgent  │  ← parallel
 │Semgrep + LLM │     LLM      │       LLM        │
 └──────┬───────┴──────┬───────┴───────┬──────────┘
        └──────────────┼───────────────┘
                       ↓
              SupervisorAgent
                       ↓
              [INTERRUPT — human approval]
                       ↓
       POST /approve/{run_id}  or  approve_review MCP tool
                       ↓
              GitHub PR Comment
```

---

## LLM Backend

Sentinel is backend-agnostic. Control the provider and model with two env vars:

| `LLM_BACKEND` | `LLM_MODEL` (default) | Requires |
|---|---|---|
| `anthropic` (default) | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| `gemini` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |

```bash
# Use Claude Opus
LLM_BACKEND=anthropic LLM_MODEL=claude-opus-4-7 python main.py

# Use Gemini 1.5 Pro
LLM_BACKEND=gemini LLM_MODEL=gemini-1.5-pro python main.py

# Use GPT-4o
LLM_BACKEND=openai LLM_MODEL=gpt-4o python main.py
```

---

## MCP Server

Sentinel exposes two MCP tools, usable from Claude Desktop, Cursor, or any MCP-compatible client:

- **`review_pr(repo, pr_number)`** — fetches the PR, runs all three agents + supervisor, returns `run_id` and the ranked markdown review
- **`approve_review(run_id)`** — resumes the paused graph from SQLite checkpoint and posts the comment to GitHub

Both tools share `sentinel.db` with the FastAPI server — a `run_id` started via MCP can be approved via `POST /approve/{run_id}` and vice versa.

Claude Desktop config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sentinel": {
      "command": "python",
      "args": ["/path/to/Sentinel/mcp_server.py"]
    }
  }
}
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
| LLM findings after filtering | 4–5 |
| Contextual issues LLM caught vs Semgrep | 1 (debug endpoint exposure) |
| LLM calls per review | 4 (Security + Docs + Performance + Supervisor) |
| Cost per review — with findings | ~$0.016 |
| Cost per review — clean PR | ~$0.003 |
| Tokens per full review | ~7,500–7,800 |

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph 1.1.10 |
| LLM (default) | Claude Haiku (claude-haiku-4-5-20251001) |
| LLM alternatives | Gemini 2.0 Flash, GPT-4o-mini (configurable) |
| Static Analysis | Semgrep (auto ruleset) |
| Agent Interface | MCP server (stdio) + FastAPI webhook |
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

# Optional — set to switch LLM backend
LLM_BACKEND=anthropic
LLM_MODEL=
GOOGLE_API_KEY=
OPENAI_API_KEY=

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=sentinel
```

## Approving a Review

After Sentinel processes a PR the graph pauses. Approve to post:

```bash
curl -X POST http://localhost:8000/approve/{run_id}
```

`run_id` is printed in server logs and returned in the webhook response. Alternatively, call `approve_review(run_id)` from any MCP client.

---

## Project Structure

```
sentinel/
├── api/webhook.py              # Webhook receiver + /approve endpoint + Prometheus instrumentation
├── agents/
│   ├── llm_factory.py          # Pluggable LLM backend — LLM_BACKEND + LLM_MODEL env vars
│   ├── security_agent.py       # Semgrep + LLM → structured security findings
│   ├── docs_agent.py           # LLM → docstring gap detection
│   ├── performance_agent.py    # LLM → N+1, unbounded queries, sync I/O, inefficient loops
│   └── supervisor_agent.py     # Aggregation, dedup, conflict resolution, ranked markdown
├── graph/workflow.py           # LangGraph graph + SqliteSaver checkpointer
├── tools/
│   ├── semgrep_tool.py         # Semgrep subprocess wrapper
│   └── github_tool.py          # GitHub App JWT auth + API calls
├── models/state.py             # PRReviewState TypedDict
├── scripts/
│   └── benchmark.py            # Parses server logs → min/avg/p50/p95/p99/stddev latency
├── mcp_server.py               # MCP server — review_pr and approve_review tools
├── config.py
└── main.py                     # FastAPI app + GET /metrics (Prometheus)
```

---

## Technical Highlights

### Contextual reasoning over static analysis

This is the core design decision that makes Sentinel useful rather than noisy. Semgrep provides pattern-matched SAST findings across changed files. The LLM receives those findings *plus the full diff* and does two things: it filters results that do not apply given the surrounding code, and it adds findings that pattern matching structurally cannot detect.

In one measured run, the LLM identified a debug endpoint where the route handler contained an RCE vulnerability, the inline comment said "not for production," but the route was still registered and live. Semgrep matched nothing; the LLM caught it. This hybrid pipeline took 6 raw findings to 4–5 high-confidence, actionable issues.

### Parallel agent execution

SecurityAgent, DocsAgent, and PerformanceAgent are all edges from `START` in the LangGraph `StateGraph`. LangGraph runs all three in a thread pool simultaneously. Each writes to a separate state key so there is no collision. SupervisorAgent reads all three after they complete. Adding a fourth agent requires one new node and one new edge — no graph restructuring.

### Human-in-the-loop

Graph compiled with `interrupt_before=["post_comment"]`. State is checkpointed to SQLite via `SqliteSaver` after every node. Calling `/approve/{run_id}` or the `approve_review` MCP tool resumes the exact graph run from where it paused — survives server restarts.

### MCP integration

`mcp_server.py` runs as a stdio MCP server alongside the FastAPI process. Both processes write to and read from `sentinel.db` — the `run_id` (LangGraph `thread_id`) is the shared key. A review started through the MCP interface can be approved through the HTTP interface and vice versa.

### Observability

Every node is traced end-to-end in LangSmith (inputs, outputs, token usage, per-node latency). Prometheus metrics exposed at `GET /metrics`: `sentinel_reviews_total`, `sentinel_review_latency_seconds` (histogram), `sentinel_findings_total` by agent. `scripts/benchmark.py` parses server logs to compute p50/p95/p99 latency across runs.

---

## Production Architecture

For scale, Sentinel's architecture evolves along four axes:

- **Queue-backed execution** — SQS decouples webhook intake from graph execution; N workers process reviews concurrently with no shared state
- **Redis checkpointing** — Replaces SQLite `SqliteSaver` with Redis for horizontal scaling and cross-node state access
- **Retrieval-augmented review** — Embed codebase context (past findings, coding standards) into agent prompts via vector search
- **Eval harness** — Label 10–20 historical PRs with ground-truth findings; measure precision/recall across Semgrep-only vs full Sentinel pipeline

Full production design: **[FUTURE.md](./FUTURE.md)**
