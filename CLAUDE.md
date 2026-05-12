# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install deps (includes mcp, langchain-google-genai)
pip install -r requirements.txt

# Run the FastAPI server (with reload)
python main.py

# Run the MCP server (for Claude Desktop / Cursor integration)
python mcp_server.py

# Capture server output for latency benchmarking
python main.py 2>&1 | tee sentinel.log

# Run latency benchmark against captured logs
python scripts/benchmark.py sentinel.log

# Approve a paused review
curl -X POST http://localhost:8000/approve/{run_id}

# Check Prometheus metrics
curl http://localhost:8000/metrics
```

No test suite exists. Validate changes by running the server and sending a real or simulated webhook.

## Architecture

**Entry point:** `main.py` — FastAPI app, mounts `api/webhook.py` router, exposes `GET /metrics`.

**Request flow:**

1. `POST /webhook` — verifies GitHub HMAC signature, fetches PR diff + file contents via JWT-authenticated GitHub API, spawns `run_graph()` as a FastAPI `BackgroundTask`
2. `graph.invoke(state)` runs the LangGraph `StateGraph` defined in `graph/workflow.py`
3. Three agents fan out from `START` and run **in parallel** (LangGraph thread pool): `security_node`, `docs_node`, `performance_node` — each writes to its own state key, no collision
4. `supervisor_node` reads all three results, deduplicates, ranks, and produces a markdown review
5. Graph **pauses** at `interrupt_before=["post_comment"]` — state checkpointed to `sentinel.db` (SQLite via `SqliteSaver`)
6. `POST /approve/{run_id}` resumes the exact graph run; `post_comment_node` posts the review to GitHub

**State:** `PRReviewState` TypedDict in `models/state.py`. All agents read from `diff`/`files_content` and write to their respective `*_findings` key.

**Checkpointing:** `graph/workflow.py` opens a single SQLite connection (`sentinel.db`) and passes it as `SqliteSaver` to `build_graph()`. The graph survives server restarts — `run_id` is the `thread_id` for LangGraph config.

## LLM Backend

Controlled by `LLM_BACKEND` env var (`"anthropic"` default, `"gemini"` for Gemini 2.0 Flash).

`agents/llm_factory.py` — single `get_llm(StructuredOutputModel)` function. All agents call this instead of constructing `ChatAnthropic` directly. Switching backends requires only the env var — no code changes.

- Anthropic: needs `ANTHROPIC_API_KEY`
- Gemini: needs `GOOGLE_API_KEY` (free tier available at aistudio.google.com)

## MCP Server

`mcp_server.py` exposes two tools over MCP stdio:
- `review_pr(repo, pr_number)` — fetches PR, runs full graph, returns `run_id` + supervisor markdown
- `approve_review(run_id)` — resumes paused graph, posts comment to GitHub

Shares the same `sentinel.db` checkpointer as the FastAPI server — `run_id` is portable between both.

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

## Agent Design

Each agent in `agents/` follows the same pattern:
- Receives `PRReviewState`, reads `diff` and/or `files_content`
- Calls Claude Haiku (`claude-haiku-4-5-20251001`) with `.with_structured_output()` using a Pydantic model
- Returns a dict with exactly one state key (e.g. `{"security_findings": [...]}`)

**SecurityAgent** — runs Semgrep via subprocess on a temp dir containing changed files, then sends raw findings + diff to Claude to filter false positives and add missed issues. Claude's output is structured as `SecurityFindings(findings: list[SecurityFinding])`.

**SupervisorAgent** — receives all three agents' findings, prompts Claude to deduplicate, rank by severity, and produce a GitHub-ready markdown comment. Returns `{"supervisor_summary": markdown_review}`.

## Key Constraints

- `semgrep` must be on PATH — `main.py` prepends the venv `bin/` dir at startup
- All env vars are required — `config.py` will raise `KeyError` at import if any are missing; see `.env.example`
- GitHub App private key lives at `keys/sentinel.pem` (gitignored)
- `sentinel.db` persists graph state across restarts — delete it to reset all pending runs
- Diff is truncated to 6000 chars when sent to Claude in `security_agent.py` — relevant for large PRs

## Adding a New Agent

1. Create `agents/your_agent.py` with a node function returning `{"your_findings": [...]}`
2. Add `your_findings: list[dict]` to `PRReviewState` in `models/state.py`
3. In `graph/workflow.py`: `builder.add_node("your_agent", your_node)`, then `builder.add_edge(START, "your_agent")` and `builder.add_edge("your_agent", "supervisor")`
4. Update `supervisor_node` prompt to include the new findings block
