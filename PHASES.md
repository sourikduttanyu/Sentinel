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

## Day 3 — DocsAgent ⬜ TODO
- [ ] DocsAgent prompts Claude on changed functions in diff
- [ ] Detects missing/stale docstrings
- [ ] Returns structured findings: `{file, function, issue}`
- [ ] LangSmith dashboard shows both agent traces

**Verify:** PR with undocumented functions → DocsAgent flags them

---

## Day 4 — SupervisorAgent ⬜ TODO
- [ ] Reads security_findings + docs_findings from state
- [ ] Deduplicates overlapping findings
- [ ] Ranks by severity
- [ ] Resolves conflicts (same function flagged by both agents)
- [ ] Produces final review markdown

**Verify:** Combined findings → clean structured review comment

---

## Day 5 — Human Gate + GitHub Comment ⬜ TODO
- [ ] LangGraph `interrupt()` after supervisor
- [ ] SqliteSaver checkpointer wired
- [ ] FastAPI `POST /approve/{run_id}` endpoint resumes graph
- [ ] `post_review_comment` called after approval
- [ ] Comment appears on actual GitHub PR

**Verify:** Full flow — PR opens → review generated → curl approve → comment posted on GitHub

---

## Day 6 — Real PR + Metrics ⬜ TODO
- [ ] End-to-end run on `Chronos_Pipeline` PR
- [ ] Manually record: latency, cost, false positive count vs raw Semgrep
- [ ] Fix any bugs surfaced by real PR
- [ ] Capture LangSmith trace screenshots

**Verify:** Numbers exist to put in resume bullets

---

## Day 7 — Buffer / Polish ⬜ TODO
- [ ] README finalized with architecture diagram
- [ ] Demo script written (what to show in interviews)
- [ ] At least one LangSmith trace screenshot saved
- [ ] Repo public and clean

---

## Post-Launch (during job search)
- [ ] Redis checkpointer swap (resume bullet: checkpoint recovery time)
- [ ] False positive delta measured across 10 labeled PRs
- [ ] Prometheus metrics + Grafana screenshot
- [ ] Cost comparison: Haiku vs Sonnet per review
- [ ] PerformanceAgent added as third parallel node
