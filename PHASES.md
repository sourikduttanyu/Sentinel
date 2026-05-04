# Sentinel — Build Phases

## Day 1 — Plumbing ✅ COMPLETE
- [x] Task 1 — Repo structure, dependencies, venv
- [x] Task 2 — PRReviewState TypedDict
- [x] Task 3 — GitHub App auth (JWT → installation token, get_pr_diff, get_pr_files, post_review_comment)
- [x] Task 4 — FastAPI webhook endpoint with signature validation
- [x] Task 5 — LangGraph skeleton (parallel security + docs → supervisor)
- [x] Task 6 — Webhook wired to graph, real diff flows through all nodes

**Verify:** Start server → push commit to PR branch → all 4 nodes fire in terminal

---

## Day 2 — SecurityAgent ✅ COMPLETE
- [x] Semgrep subprocess tool (`tools/semgrep_tool.py`)
- [x] SecurityAgent calls Semgrep on diff files
- [x] SecurityAgent sends Semgrep output + diff to Claude
- [x] Returns structured findings: `{file, line, severity, description, suggestion}`
- [x] LangSmith traces wired (2 env vars already set)

**Result:** PR #3 → 6 Semgrep raw findings → 4 Claude findings (SQL injection CRITICAL, RCE CRITICAL, hardcoded creds HIGH, debug endpoints HIGH). Claude caught 1 contextual issue Semgrep missed.

---

## Day 3 — DocsAgent ✅ COMPLETE
- [x] DocsAgent prompts Claude on changed functions in diff
- [x] Detects missing/stale docstrings
- [x] Returns structured findings: `{file, function, issue}`
- [x] temperature=0 + per-call LLM init for parallel stability

**Result:** PR #3 → 2 doc findings (missing param + return docs on device_search, eval_config). Parallel execution stable after fixing module-level LLM instantiation.

---

## Day 4 — SupervisorAgent ✅ COMPLETE
- [x] Reads security_findings + docs_findings from state
- [x] Deduplicates overlapping findings
- [x] Ranks by severity CRITICAL → HIGH → MEDIUM → docs
- [x] Resolves conflicts (same function flagged by both agents)
- [x] Produces final review markdown with verdict

**Result:** PR #3 → 5 security + 2 docs → clean ranked markdown with REQUEST CHANGES verdict.

---

## Day 5 — Human Gate + GitHub Comment ✅ COMPLETE
- [x] `interrupt_before=["post_comment"]` on graph compile
- [x] SqliteSaver checkpointer wired (sentinel.db)
- [x] FastAPI `POST /approve/{run_id}` endpoint resumes graph
- [x] `post_review_comment` called after approval
- [x] Comment visible on GitHub PR #3

**Result:** Full flow verified — graph pauses → curl approve → Sentinel review comment posted on Chronos_Pipeline PR #3.

---

## Day 6 — Real PR + Metrics ✅ COMPLETE
- [x] End-to-end run on `Chronos_Pipeline` PR
- [x] Manually record: latency, cost, false positive count vs raw Semgrep
- [x] Fix any bugs surfaced by real PR
- [x] Capture LangSmith trace screenshots

**Result:** 4.68s clean PR, 15.13s with 6 findings + 3 LLM calls, $0.016/review, $0.003 clean. Numbers in README metrics table.

---

## Day 7 — Polish ✅ COMPLETE
- [x] README finalized — architecture, metrics table, resume bullets
- [x] DEMO.md — full interview script with talking points for every likely question
- [x] Repo public and clean (no secrets, no WAL files)
- [x] LangSmith trace screenshot — added to docs/ and referenced in README
- [x] FUTURE.md — production architecture doc (infrastructure, scalability, eval harness, multi-tenancy)
- [x] SETUP.md — full self-setup guide for external users
- [x] SEO optimized — repo description, 12 GitHub topics, README keyword tuning

---

## Post-Launch (during job search)
- [ ] Redis checkpointer swap (resume bullet: checkpoint recovery time)
- [x] Latency benchmark script — `scripts/benchmark.py` parses server log, reports min/avg/p50/p95/p99/stddev
- [ ] False positive delta measured across 10 labeled PRs (need ground truth labels)
- [ ] Cost per review — instrument token usage via LangSmith, compare Haiku vs Sonnet
- [x] Prometheus metrics — `sentinel_reviews_total`, `sentinel_review_latency_seconds`, `sentinel_findings_total` exposed at GET /metrics
- [x] PerformanceAgent — third parallel node (N+1, unbounded queries, sync I/O, inefficient loops, missing pagination)
