# Changelog

All notable changes to Sentinel are documented here. Entries are grouped by feature milestone, derived from commit history.

---

## [Unreleased] — feature/model-selection

### Added
- `LLM_MODEL` env var — override the model name for any backend without changing code
- OpenAI as a third supported backend (`LLM_BACKEND=openai`) via `langchain-openai`
- Per-backend model defaults: `claude-haiku-4-5-20251001` / `gemini-2.0-flash` / `gpt-4o-mini`

---

## [2026-05-10] — MCP server + pluggable LLM backend

### Added
- `mcp_server.py` — MCP stdio server exposing `review_pr` and `approve_review` as tools; works with Claude Desktop, Cursor, any MCP client
- `agents/llm_factory.py` — single `get_llm()` factory; backend selected via `LLM_BACKEND` env var (`anthropic` or `gemini`)
- Gemini 2.0 Flash support via `langchain-google-genai`; free-tier compatible
- `tools/github_tool.py`: `get_pr_head_sha()` for MCP path (no webhook payload to extract SHA from)
- `GOOGLE_API_KEY`, `LLM_BACKEND` added to `config.py` and `.env.example`
- `CLAUDE.md` — codebase guidance for Claude Code

### Changed
- All four agents (`security`, `docs`, `performance`, `supervisor`) now call `get_llm()` instead of constructing `ChatAnthropic` directly — switching LLM backend requires only env var change
- `ANTHROPIC_API_KEY` softened from `os.environ[]` to `os.getenv()` so gemini-only setups don't fail at import
- `.gitignore` extended: `medium_post.md`, `substack_post.md`, `screenshots/`, `.DS_Store`

---

## [2026-05-04] — PerformanceAgent + Prometheus metrics + benchmark script

### Added
- `agents/performance_agent.py` — detects N+1 queries, unbounded queries, sync I/O in async paths, inefficient loops, missing pagination
- Prometheus metrics at `GET /metrics`: `sentinel_reviews_total`, `sentinel_review_latency_seconds` (histogram with latency buckets), `sentinel_findings_total` labeled by agent
- `scripts/benchmark.py` — parses server stdout for `[Metrics]` lines, computes min/avg/p50/p95/p99/stddev/max latency across N runs
- `PerformanceFinding` Pydantic model with `pattern` field (`N_PLUS_ONE`, `UNBOUNDED_QUERY`, `SYNC_IO`, `MISSING_INDEX`, `INEFFICIENT_LOOP`, `MISSING_PAGINATION`)

### Changed
- SupervisorAgent prompt updated to include performance findings block
- `PRReviewState` extended with `performance_findings: list[dict]`
- LangGraph graph wired `performance` node in parallel with `security` and `docs`

### Measured
- Latency to interrupt: 4.68s (clean PR), 15.13s (PR with 6 findings)
- Cost per review: ~$0.003 (clean) to ~$0.016 (with findings)
- Tokens per full review: ~7,500–7,800

---

## [2026-04-30] — Human-in-the-loop + SQLite checkpointing + GitHub comment posting

### Added
- `POST /approve/{run_id}` endpoint — resumes paused LangGraph run from SQLite checkpoint
- `SqliteSaver` checkpointer (`sentinel.db`) — graph state persists across server restarts
- `post_comment_node` — posts supervisor markdown as GitHub PR review comment via `post_review_comment()`
- `graph/workflow.py`: `interrupt_before=["post_comment"]` — graph always pauses for human approval

### Changed
- `run_id` (UUID) now used as LangGraph `thread_id` for checkpoint lookup
- Graph invocation moved to FastAPI `BackgroundTask` to return webhook response immediately

---

## [2026-04-28] — SupervisorAgent

### Added
- `agents/supervisor_agent.py` — aggregates security + docs findings, deduplicates overlapping issues, ranks by severity (CRITICAL → HIGH → MEDIUM → LOW → docs), produces GitHub-ready markdown comment
- `SupervisorOutput` Pydantic model with `summary`, `total_findings`, severity counts, `markdown_review`
- Supervisor prompt instructs deduplication and conflict resolution when multiple agents flag the same file+line

### Changed
- `PRReviewState` extended with `supervisor_summary: str`

---

## [2026-04-27] — DocsAgent + parallel execution verified

### Added
- `agents/docs_agent.py` — detects missing docstrings, stale docstrings (params/return changed but docs not updated), missing parameter/return documentation on changed functions
- `DocsFinding` Pydantic model with `issue` field (`MISSING_DOCSTRING`, `STALE_DOCSTRING`, `MISSING_PARAM_DOCS`)

### Changed
- LangGraph graph fans out to `security` and `docs` from `START` — both run in parallel, verified on real PR
- LLM initialization moved inside node functions (prevents import-time failure when env vars absent)
- `temperature=0` set on all LLM calls for deterministic output

---

## [2026-04-26] — SecurityAgent + Semgrep integration

### Added
- `agents/security_agent.py` — runs Semgrep on changed files, sends raw findings + full diff to Claude, returns filtered + enriched structured findings
- `tools/semgrep_tool.py` — writes changed files to temp dir, runs `semgrep --config=auto --json`, strips temp dir prefix from paths, returns parsed findings list
- `SecurityFinding` / `SecurityFindings` Pydantic models with `severity` (`LOW/MEDIUM/HIGH/CRITICAL`), `description`, `suggestion`
- `tools/github_tool.py`: `get_file_content()` for fetching full file content at PR head SHA
- LangSmith end-to-end tracing per node

### Measured
- Semgrep: 6 raw findings → Claude: 4–5 high-confidence findings after false positive filtering
- Claude caught 1 contextual issue Semgrep missed (debug RCE endpoint registered in production)

---

## [2026-04-25] — Initial scaffold + webhook skeleton

### Added
- FastAPI webhook receiver (`api/webhook.py`) — HMAC signature verification, filters `pull_request` events (`opened`, `synchronize`, `reopened`)
- `tools/github_tool.py` — GitHub App JWT auth, installation token exchange, `get_pr_diff()`, `get_pr_files()`
- LangGraph `StateGraph` skeleton with `PRReviewState` TypedDict
- `main.py` — FastAPI app entry point; prepends venv `bin/` to PATH for `semgrep`
- `models/state.py` — `PRReviewState` TypedDict (`pr_number`, `repo`, `diff`, `files_changed`, `files_content`, `security_findings`, `docs_findings`, `performance_findings`, `supervisor_summary`, `human_approved`, `run_id`)
- `PHASES.md` — build tracker
- `FUTURE.md` — production architecture design (SQS, Redis checkpointing, RAG, eval harness)
- `SETUP.md` — full self-setup guide including GitHub App creation
