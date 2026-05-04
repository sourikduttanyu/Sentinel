# Sentinel — Interview Demo Script

## Setup (before interview)

```bash
# Terminal 1 — server
cd /Users/sourik/Sentinel && .venv/bin/python main.py

# Terminal 2 — ngrok
ngrok http 8000
# Update GitHub App webhook URL if ngrok URL changed
```

Verify ngrok URL matches GitHub App webhook URL at:
`github.com/settings/apps/sentinel-review0` → General → Webhook URL

---

## Demo Flow (5 minutes)

### 1. Show the architecture (30s)
Point to README architecture diagram. Key talking points:
- "Two agents run in parallel — Security and Docs"
- "Supervisor aggregates and resolves conflicts"
- "Human-in-the-loop gate before posting — graph checkpointed to SQLite so it survives restarts"

### 2. Trigger a PR review (live)
Push a commit to `experiment/readme-badges` branch on Chronos_Pipeline:
```bash
cd /path/to/Chronos_Pipeline
echo " " >> README.md && git add . && git commit -m "demo trigger" && git push
```

Watch Terminal 1. Should see:
```
[Webhook] PR #2 synchronize on sourikduttanyu/Chronos_Pipeline
[SecurityAgent] running Semgrep...
[DocsAgent] analyzing diff...
[SupervisorAgent] review generated
[Metrics] latency_to_interrupt=4.68s
[Metrics] approve via: curl -X POST http://localhost:8000/approve/{run_id}
```

### 3. Show LangSmith trace
Open smith.langchain.com → Project: sentinel → show the latest trace.
- Point out parallel node execution (security + docs fire simultaneously)
- Show node sequence: security → supervisor → interrupt

### 4. Approve and post comment
```bash
curl -X POST http://localhost:8000/approve/{run_id}
```

Show the PR on GitHub — Sentinel review comment now visible.

### 5. Show the code file PR (#3) review (pre-done)
Open `github.com/sourikduttanyu/Chronos_Pipeline/pull/3`
Show the Sentinel comment — ranked findings, CRITICAL SQL injection, RCE, verdict: REQUEST CHANGES.

---

## Key Talking Points

**"Why not just run Semgrep directly?"**
> Semgrep is pattern matching — it finds what it's told to find. Claude reasons about context. On PR #3, Semgrep found 6 raw findings. Claude filtered to 4 real issues AND added one Semgrep missed entirely — debug endpoints with RCE vulnerabilities marked 'not for production' but still registered as live routes. That contextual gap is where the agent adds value.

**"How does the parallel execution work?"**
> LangGraph StateGraph — SecurityAgent and DocsAgent are both edges from START. LangGraph runs them in a thread pool simultaneously. Both write to separate state keys so no collision. Supervisor reads both after they complete.

**"What happens if the server restarts mid-review?"**
> SqliteSaver checkpoints the graph state after every node. If the server restarts, the run_id is still valid — calling `/approve/{run_id}` resumes from exactly where it paused. That's the checkpoint recovery story.

**"How do you prevent false positives?"**
> Two layers. First, Semgrep with auto ruleset catches known patterns. Then Claude reviews the findings in context of the full diff and filters noise. On average, 1-2 raw Semgrep findings get dropped per review. The delta between raw Semgrep output and final Claude output is the precision improvement.

**"What's the latency?"**
> 4.68s for a clean PR with no findings. 15s for a PR with 6 findings and 3 LLM calls running in parallel. Well under the 45s target I set.

---

## If Asked to Extend It

**"How would you add a PerformanceAgent?"**
> Add a third node with edge from START, same as Security and Docs. Supervisor already handles N findings — just add `performance_findings` to the state TypedDict. No graph restructuring needed.

**"How would you scale this to 100 concurrent PRs?"**
> Swap SqliteSaver for RedisSaver — one line change in `graph/workflow.py`. Move `run_graph` to a Celery worker or AWS Lambda. FastAPI webhook handler stays thin — just enqueues the job.

**"How do you know the agents are working correctly?"**
> LangSmith traces every node — inputs, outputs, token usage, latency per node. For evals, I'd label 10-20 PRs with ground truth findings and measure precision/recall vs raw Semgrep baseline. That's the eval harness I'm building next.
