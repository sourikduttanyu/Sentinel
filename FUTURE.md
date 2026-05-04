# Future Work & Production Architecture

This document describes the production architecture Sentinel is designed to reach. It exists to make the engineering decisions behind the current implementation legible — what is simplified in the dev build, what replaces it at scale, and why each choice was made. If you are evaluating this project, this is where the production thinking lives.

---

## Table of Contents

1. [Infrastructure Evolution](#1-infrastructure-evolution)
2. [Scalability Design](#2-scalability-design)
3. [Production Stack](#3-production-stack)
4. [PerformanceAgent: Third Parallel Agent](#4-performanceagent-third-parallel-agent)
5. [Retrieval Augmentation](#5-retrieval-augmentation)
6. [Eval Harness Design](#6-eval-harness-design)
7. [Multi-Tenancy](#7-multi-tenancy)
8. [Failure Modes and Mitigations](#8-failure-modes-and-mitigations)
9. [Security Hardening](#9-security-hardening)
10. [Cost Optimization](#10-cost-optimization)

---

## 1. Infrastructure Evolution

### Dev vs Production: Component Mapping

| Layer | Dev | Production | Reason for Change |
|---|---|---|---|
| State / Checkpointer | SQLite (local file) | Redis Cluster | Horizontal scaling; SQLite is single-writer, not network-accessible |
| Ingress | ngrok tunnel | AWS ALB + API Gateway | TLS termination, WAF, DDoS protection, stable DNS |
| Server runtime | Local Uvicorn | Containerized FastAPI on ECS Fargate | Isolation, horizontal scaling, zero-downtime deploys |
| Job queue | None (synchronous) | Amazon SQS FIFO | Durable, decoupled, dead-letter queue built in |
| Secrets | .env file | AWS Secrets Manager | Rotation, audit trail, no secrets in source |
| GitHub App webhook | ngrok URL | API Gateway + Lambda proxy | Stable endpoint, scales to burst, no server to warm |
| LLM provider | Claude Haiku direct | Haiku + Sonnet with routing layer | Cost control, fallback, per-complexity routing |
| Observability | LangSmith (traces only) | LangSmith + Prometheus + Grafana + PagerDuty | Metrics, alerting, SLO tracking |
| Storage | Local filesystem | S3 + Aurora PostgreSQL | Durable review artifacts, queryable audit log |
| Deployment | Manual `uvicorn main:app` | GitHub Actions → ECR → ECS rolling deploy | Reproducibility, rollback capability |

### Migration Sequencing

**Phase 1 — Stable Endpoint.** Replace ngrok with a real domain on API Gateway. This is the highest-risk dev artifact: ngrok URLs reset on restart, breaking the GitHub App webhook registration. Cost is near zero.

**Phase 2 — Durable Queue.** Add SQS between webhook ingestion and the LangGraph runner. The webhook handler writes to SQS and returns HTTP 200 immediately; workers poll SQS. This is the architectural pivot from synchronous to async, and it unblocks everything that follows.

**Phase 3 — Redis Checkpointer.** Replace the SQLite checkpointer with a Redis-backed LangGraph checkpointer. LangGraph's `AsyncRedisSaver` or a custom implementation wrapping `redis.asyncio` works directly. This unblocks horizontal worker scaling.

**Phase 4 — Containerize and Deploy to ECS.** Build a production Docker image, push to ECR, deploy to ECS Fargate with auto-scaling policies.

**Phase 5 — Observability.** Add Prometheus metrics to the FastAPI app, deploy Grafana dashboards, set PagerDuty alerts on error rate and P95 latency SLOs.

---

## 2. Scalability Design

### Concurrency Problem

Each PR review is a stateful LangGraph run with a `thread_id`. At 10,000 concurrent reviews, three failure modes emerge:

1. State collision if two workers accidentally share a `thread_id`
2. Database connection exhaustion if every worker holds an open Redis connection
3. Thundering herd on the Claude API when PRs arrive in bursts (e.g., end of sprint)

### Webhook Ingestion Layer

```
GitHub → API Gateway (webhook endpoint) → Lambda Proxy → SQS FIFO Queue
```

API Gateway handles TLS and receives the raw GitHub webhook. A lightweight Lambda function performs HMAC-SHA256 validation of the `X-Hub-Signature-256` header and writes a canonical message to SQS, returning HTTP 200 to GitHub immediately.

The SQS message:

```json
{
  "event_type": "pull_request",
  "action": "opened",
  "org_id": "acme-corp",
  "repo": "acme-corp/backend",
  "pr_number": 1842,
  "pr_sha": "a3f9c1d",
  "installation_id": 12345678,
  "received_at": "2026-05-03T14:23:00Z",
  "thread_id": "acme-corp/backend/1842/a3f9c1d"
}
```

The `thread_id` is deterministic from org + repo + PR number + commit SHA. Re-runs for the same commit are idempotent, and state collision between different PRs is structurally impossible.

SQS FIFO is used with `MessageGroupId` set to `{org_id}/{repo}`. Multiple commits on the same PR are processed in order, not in parallel, preventing race conditions on the final review comment posted back to GitHub.

### Job Queue Design

| Property | Choice | Justification |
|---|---|---|
| Queue type | SQS FIFO | Ordered per-repo, exactly-once delivery with deduplication IDs |
| Deduplication | ContentBasedDeduplication on `thread_id` | Prevents duplicate reviews if GitHub retries the webhook |
| Visibility timeout | 900s (15 min) | Long enough for a complete graph run including retries |
| Dead-letter queue | SQS DLQ with 3 max receives | Failed jobs are captured for inspection, not silently dropped |
| Batch size | 1 message per worker poll | Each PR review is stateful and CPU/memory intensive; no queue-level batching |

### Worker Pool

Workers are ECS Fargate tasks polling SQS in a tight loop:

```python
while True:
    message = sqs.receive_message(WaitTimeSeconds=20)
    if message:
        sqs.change_message_visibility(timeout=900)
        await run_langgraph(message.body)
        sqs.delete_message(message.receipt_handle)
```

Auto-scaling uses a custom CloudWatch metric: `ApproximateNumberOfMessagesVisible` on the SQS queue.

- Target: 1 running task per 5 queued messages
- Scale-out cooldown: 30 seconds
- Scale-in cooldown: 300 seconds
- Min tasks: 2 (always available)
- Max tasks: 200 (cost ceiling)

At 10,000 concurrent PRs with an average 3-minute review time: peak concurrency is ~3,333 active reviews. At 1 review per worker, Fargate at 0.25 vCPU / 512MB (~$0.012/hr per task) costs ~$40/hr at peak.

### Checkpointing Strategy

- **Backend**: Redis Cluster (ElastiCache), 3 shards, Multi-AZ
- **Key format**: `sentinel:checkpoint:{thread_id}:{step_number}`
- **TTL**: 7 days
- **Serialization**: MessagePack (smaller than JSON, faster than Pickle)
- **Connection pooling**: Max 10 connections per ECS task via `redis.asyncio.ConnectionPool`. 200 max tasks = 2,000 connections, well within ElastiCache's 65,000 connection limit.

State collision is prevented at the queue layer: SQS FIFO ensures only one worker processes a given `thread_id` at a time via `MessageGroupId`.

---

## 3. Production Stack

### Ingestion

- **API Gateway (HTTP API)**: Receives GitHub webhooks. 70% cheaper than REST API for this use case.
- **AWS Lambda (Python 3.12)**: Validates webhook signature and enqueues to SQS. Stateless, scales to 10,000 concurrent invocations. Cold start is acceptable — review is async.

### Queue

- **Amazon SQS FIFO**: Chosen over RabbitMQ (operational overhead), Kafka (overkill for this throughput), and Celery (adds another abstraction with its own failure modes). Fully managed, native IAM auth. The 256KB message limit is sufficient — diff content is fetched by the worker, not embedded in the message.

### Workers

- **Amazon ECS Fargate**: Chosen over Lambda (15-minute hard timeout), EC2 (instance management overhead), and Kubernetes (significant operational overhead for this use case). Fargate tasks are billed per-second with no idle cost.
- **LangGraph**: Unchanged from dev. Only the checkpointer backend swaps.

### State

- **ElastiCache Redis Cluster (r7g.large)**: Chosen over DynamoDB (LangGraph's Redis checkpointer is mature; a DynamoDB adapter requires a custom implementation) and Memcached (no persistence — a crash loses in-progress reviews).

### Storage

- **Amazon S3**: Raw diffs, Semgrep JSON output, agent outputs, final review markdown. Lifecycle policy: move to Glacier after 90 days.
- **Aurora PostgreSQL Serverless v2**: Structured audit log — every review, finding, verdict, org config, latency, cost, and agent version. Source of truth for the eval harness and billing. Scales to 0 ACUs during idle.

### Observability

- **LangSmith**: LLM trace inspection, token counting, prompt debugging. Each run is tagged with `org_id`, `repo`, `pr_number`.
- **Prometheus + Amazon Managed Grafana**: Key metrics: `sentinel_review_duration_seconds`, `sentinel_agent_errors_total`, `sentinel_queue_depth`, `sentinel_findings_count`.
- **AWS X-Ray**: Distributed tracing across API Gateway, Lambda, SQS, ECS. Under 1ms overhead.
- **PagerDuty**: Alert on P95 latency > 120s and error rate > 5/min.

### Deployment

- **GitHub Actions**: On merge to `main` — run tests, build Docker image, push to ECR, trigger ECS rolling deploy.
- **Terraform**: All infrastructure as code. State in S3 with DynamoDB locking.

---

## 4. PerformanceAgent: Third Parallel Agent

### Responsibility

PerformanceAgent identifies runtime performance issues outside the scope of SecurityAgent (vulnerabilities) and DocsAgent (documentation):

- **N+1 query detection**: ORM calls inside loops
- **Algorithmic complexity**: Nested loops over unbounded collections; `list.index()` and `in` checks on lists where a set would be O(1)
- **Blocking I/O in hot paths**: Synchronous `requests.get()` or database calls in per-item functions
- **Memory anti-patterns**: Loading entire result sets instead of using streaming cursors; list comprehensions that should be generators
- **Caching opportunities**: Repeated computation of the same value within a function

### Integration

The current graph runs SecurityAgent and DocsAgent in parallel, then reduces. PerformanceAgent plugs in as a third parallel branch with no restructuring required:

```python
# Existing
graph.add_node("security_agent", run_security_agent)
graph.add_node("quality_agent", run_quality_agent)
graph.add_node("reducer", reduce_findings)
graph.add_edge("security_agent", "reducer")
graph.add_edge("quality_agent", "reducer")

# Adding PerformanceAgent: two lines
graph.add_node("performance_agent", run_performance_agent)
graph.add_edge("performance_agent", "reducer")
graph.add_edge("entry", "performance_agent")
```

The reducer aggregates findings from all upstream agents. Each agent's output conforms to the same `Finding` schema. The reducer does not know or care how many agents exist.

### Prompt Constraint

```
You are a performance review specialist. Your only job is to identify
runtime performance issues in the following code diff. Do not comment
on security vulnerabilities or code style. Focus exclusively on:
1. Algorithmic complexity (O(n²) or worse on unbounded inputs)
2. N+1 database query patterns
3. Blocking I/O in async or hot-path code
4. Memory inefficiency (loading large datasets fully into memory)
5. Repeated computation that could be cached

For each issue: file path, line range, description, severity (low/medium/high), concrete suggestion.
```

---

## 5. Retrieval Augmentation

### The Problem

For large PRs, agents lack context about code outside the diff — called functions, implemented interfaces, referenced database models. Without this context, agents produce false positives on findings that are handled correctly elsewhere in the codebase.

### Embedding Strategy

On first installation, a one-time indexing job runs:

1. Clone the repository's default branch
2. Parse all source files with tree-sitter — extract semantic units: functions, classes, module-level constants
3. Generate embeddings using `text-embedding-3-small` ($0.02 per million tokens — a 100k-line codebase costs ~$0.04 to index)
4. Store vectors with metadata: `{file_path, start_line, end_line, symbol_name, last_commit_sha}`

On subsequent PRs, only changed files are re-indexed via a `push` event webhook.

### Vector Store Options

| Option | Latency | Overhead | Cost at 10M vectors |
|---|---|---|---|
| pgvector (Aurora PostgreSQL) | 15–80ms | Low — same DB cluster | Included in Aurora cost |
| Pinecone (managed) | 10–50ms | None | ~$70/month |
| Qdrant (self-hosted on ECS) | 10–30ms | Medium | ~$30/month infra |

**Recommendation: pgvector on Aurora PostgreSQL.** This eliminates a separate managed service, uses the existing Aurora cluster, and is fast enough at startup scale. Migration to Pinecone is straightforward if latency becomes a bottleneck.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE code_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    file_path TEXT NOT NULL,
    symbol_name TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    commit_sha TEXT NOT NULL,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_embeddings_org_repo ON code_embeddings (org_id, repo);
CREATE INDEX idx_embeddings_vector ON code_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Feeding Context into Agent Prompts

Before any agent runs, a retrieval step extracts symbol names from changed diff lines, queries pgvector for the top-10 most similar code units, and prepends a `<context>` block to each agent's prompt:

```python
async def retrieve_context(diff: str, org_id: str, repo: str) -> str:
    symbols = extract_symbols_from_diff(diff)
    if not symbols:
        return ""
    query_embedding = await embed(symbols)
    results = await db.fetch_all(
        """
        SELECT content, file_path, start_line, symbol_name,
               1 - (embedding <=> $1) AS similarity
        FROM code_embeddings
        WHERE org_id = $2 AND repo = $3
        ORDER BY embedding <=> $1
        LIMIT 10
        """,
        query_embedding, org_id, repo
    )
    return format_context_block(results)
```

---

## 6. Eval Harness Design

### Goal

Measure whether Sentinel's multi-agent output is more useful than raw Semgrep. Useful means: higher precision (fewer false positives), comparable or better recall, and more actionable findings.

### Ground Truth Dataset

Built from real historical data:

1. Export closed PRs from the past 12 months for pilot organizations
2. For each PR, check if merged code introduced a bug later fixed in a subsequent commit — confirmed true positives
3. Findings dismissed by developers without action — false positives
4. Bugs caught in review and fixed — true positives

```sql
CREATE TABLE ground_truth (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id TEXT NOT NULL,
    repo TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    finding_id UUID REFERENCES findings(id),
    verdict TEXT CHECK (verdict IN ('true_positive', 'false_positive', 'unknown')),
    labeled_by TEXT,
    labeled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Target: 500 labeled findings across at least 5 organizations for statistical significance.

### Metrics

```
Precision = True Positives / (True Positives + False Positives)
Recall    = True Positives / (True Positives + False Negatives)
F1        = 2 * (Precision * Recall) / (Precision + Recall)
```

Run weekly against the ground truth dataset. Track all three in Grafana. Baseline is Semgrep alone on the same dataset.

### A/B Testing Prompt Changes

Every prompt change is versioned and stored with the review record (`prompt_version` column). When testing a new prompt:

1. Deploy a shadow worker running the new version on the same PRs, writing to `reviews_shadow`
2. After 200 reviews, compare precision/recall between control and experiment on ground truth labels
3. If the improvement is statistically significant (p < 0.05, two-proportion z-test), promote to production

Shadow workers read from a fanout copy of the SQS queue — no traffic splitting at the API level.

### False Positive Rate as Primary SLO

```
FPR = False Positives / (False Positives + True Negatives)
```

Alert if weekly FPR exceeds 30%. Developer signal is captured via a feedback endpoint called from emoji reactions on the GitHub PR comment:

```
POST /api/findings/{finding_id}/feedback
{ "verdict": "false_positive" | "valid" | "fixed" }
```

---

## 7. Multi-Tenancy

### Per-Organization Configuration

```sql
CREATE TABLE org_config (
    org_id TEXT PRIMARY KEY,
    installation_id INTEGER UNIQUE NOT NULL,
    enabled_agents TEXT[] DEFAULT ARRAY['security', 'quality'],
    min_severity_to_comment TEXT DEFAULT 'medium',
    block_pr_on_severity TEXT DEFAULT 'critical',
    custom_semgrep_rules_s3_key TEXT,
    semgrep_ruleset TEXT DEFAULT 'auto',
    max_reviews_per_hour INTEGER DEFAULT 100,
    max_diff_lines INTEGER DEFAULT 5000,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    monthly_review_quota INTEGER DEFAULT 50,
    reviews_used_this_month INTEGER DEFAULT 0,
    quota_reset_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Custom Semgrep rules are stored in S3 at `s3://sentinel-configs/{org_id}/semgrep-rules.yaml`.

### Rate Limiting

Two layers:

**Layer 1 — API Gateway**: AWS WAF rate rule limiting to 1,000 webhook requests per 5 minutes per source IP.

**Layer 2 — Application**: Redis counter with 1-hour TTL checked before enqueuing to SQS:

```python
pipe = redis.pipeline()
pipe.incr(f"rate:{org_id}:hourly")
pipe.expire(f"rate:{org_id}:hourly", 3600)
count, _ = await pipe.execute()

if count > org_config.max_reviews_per_hour:
    return {"status": "rate_limited"}
```

### Billing

Each completed review inserts a row into `usage_events`. A daily cron aggregates per org and checks against `monthly_review_quota`. Stripe handles invoicing via usage-based billing API.

---

## 8. Failure Modes and Mitigations

### Claude API Down

- Retry with exponential backoff: 1s, 2s, 4s, 8s (max 4 retries within the 15-minute SQS visibility timeout)
- On all retries failing: return message to SQS queue (do not delete it); SQS retries after visibility timeout
- After 3 SQS delivery attempts: route to Dead Letter Queue
- Circuit breaker: if Claude error rate exceeds 50% over 60 seconds, stop polling SQS and alert on-call

### Semgrep Timeout

- Retry per-file instead of full diff
- If per-file also times out (e.g., a 50,000-line generated file): skip Semgrep, run LLM agents only, log the skip
- Semgrep and LLM agents are independent — a Semgrep timeout does not block the review

### Diff Too Large

| Diff Size | Strategy |
|---|---|
| < 500 lines | Full diff to all agents |
| 500–2,000 lines | Full diff + retrieval augmentation |
| 2,000–5,000 lines | Split by file; run agents per-file in parallel; merge findings |
| 5,000–10,000 lines | SecurityAgent only; skip QualityAgent and PerformanceAgent; flag for human review |
| > 10,000 lines | Reject with a PR comment explaining the limit |

The rejection threshold is configurable per org via `org_config.max_diff_lines`. Enterprise plans can raise it.

### False Positive Spike

- Automatically lower `min_severity_to_comment` for the affected org to `high`
- Alert engineering to investigate which finding category spiked (queryable via `GROUP BY finding_category`)
- If the spike is prompt-version-specific: roll back the prompt version

### Agent Disagreement

Not treated as a failure — it is useful signal. Both findings appear in the review with their `agent_source` labeled. A confidence score is attached based on Semgrep corroboration and cross-agent agreement. High-confidence findings appear prominently; lower-confidence findings are grouped in a collapsible section.

### Redis Failure

- ElastiCache Multi-AZ provides automatic failover in ~60 seconds
- Workers retry Redis connections every 5 seconds for up to 90 seconds (covers the failover window)
- Beyond 90 seconds: the worker stops processing, returns the SQS message to the queue, and resumes when Redis recovers
- In-progress graph runs restart from the last successfully written checkpoint — safe because Semgrep and Claude calls are idempotent

---

## 9. Security Hardening

### /approve Endpoint Authentication

In production, the `/approve` endpoint requires a signed JWT with `scope: approve`. It is not exposed on the public API Gateway — it sits behind an internal ALB accessible only from within the ECS task subnet.

```python
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def require_approve_scope(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    payload = verify_jwt(credentials.credentials)
    if "approve" not in payload.get("scopes", []):
        raise HTTPException(status_code=403, detail="Missing approve scope")
    return payload

@app.post("/approve/{review_id}")
async def approve_review(review_id: str, auth: dict = Depends(require_approve_scope)):
    ...
```

### Secrets in State

LangGraph state is serialized into Redis checkpoints. No credentials belong in state.

- GitHub installation tokens are fetched fresh from AWS Secrets Manager at the start of each graph run, stored in a local worker variable — not in the `GraphState` TypedDict
- Enable Redis encryption at rest (ElastiCache AES-256) and TLS in transit
- A pre-commit hook checks `GraphState` fields for common secret patterns

### Webhook Validation

```python
import hmac, hashlib

def validate_webhook(body: bytes, signature_header: str, secret: bytes) -> bool:
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

Additional hardening beyond HMAC:

- **Replay attack prevention**: Processed GitHub delivery IDs (`X-GitHub-Delivery` header) are stored in Redis with a 24-hour TTL; duplicates are rejected
- **IP allowlisting**: GitHub publishes webhook source IP ranges; fetch daily and configure AWS WAF to block requests outside these ranges

### Network Isolation

- ECS tasks in private subnets; outbound internet via NAT Gateway
- ElastiCache and Aurora in database subnets; security groups allow inbound only from ECS task security groups on specific ports
- API Gateway uses a VPC endpoint for the internal ALB
- Lambda runs inside the VPC and communicates with SQS via VPC endpoint

---

## 10. Cost Optimization

### Haiku vs Sonnet Routing

| Condition | Model |
|---|---|
| Diff < 1,000 lines, non-critical files | Haiku |
| Diff > 1,000 lines | Sonnet |
| Security-critical files (`auth/**`, `**/crypto/**`, `**/payments/**`) | Sonnet |
| PerformanceAgent algorithmic complexity analysis | Sonnet |
| Enterprise org with custom rules | Sonnet |

**Cost comparison (approximate):**

| Model | Input | Output | 1,000-line diff (est.) |
|---|---|---|---|
| Claude Haiku | $0.80/M tokens | $4.00/M tokens | ~$0.006 |
| Claude Sonnet | $3.00/M tokens | $15.00/M tokens | ~$0.025 |

At 10,000 reviews/day, 80/20 Haiku/Sonnet split: ~$72/day in model costs.

### Caching

**Semantic cache**: Embed the diff chunk before invoking an agent; query Redis for cached responses with cosine similarity > 0.92. Key: `sentinel:cache:{agent_name}:{embedding_hash}`, TTL 48 hours. Expected hit rate: 15–25% for organizations with consistent coding patterns.

**Semgrep result cache**: Semgrep is deterministic. Cache results keyed by SHA256 hash of diff content, TTL 24 hours. At 15% hit rate on 10,000 reviews/day, saves approximately $10/day.

### Estimated Cost at Scale

Assumptions: 10,000 reviews/day, average 500-line diff, 80/20 Haiku/Sonnet split, 20% Semgrep cache hit rate.

| Component | Daily | Monthly |
|---|---|---|
| Claude API (80% Haiku) | $48 | $1,440 |
| Claude API (20% Sonnet) | $24 | $720 |
| ECS Fargate (avg 50 concurrent tasks) | $14 | $420 |
| ElastiCache Redis (r7g.large x3) | $14 | $420 |
| Aurora PostgreSQL Serverless v2 | $8 | $240 |
| SQS + API Gateway + Lambda | $4 | $120 |
| S3 storage | $2 | $60 |
| LangSmith (Team plan) | $3 | $83 |
| **Total** | **$117** | **$3,503** |

At $3,503/month for 300,000 reviews, infrastructure cost per review is **$0.012**. A Pro plan at $50/month with a 500-review quota ($0.10/review) covers infrastructure at 8x margin.

---

## Implementation Priority

1. **Phase 1 — Stable Endpoint**: The highest-risk dev artifact. ngrok URLs reset on restart, breaking GitHub App webhook registration. Fix first; cost is near zero.
2. **Phase 2 — SQS Queue**: The architectural pivot that enables everything else. Without the queue, horizontal worker scaling is impossible.
3. **Eval harness**: The highest-leverage long-term investment. Without ground truth labels, prompt changes cannot be validated. Start labeling findings immediately.
4. **PerformanceAgent**: Two lines to add to the graph. The constraint is writing a focused prompt that does not overlap with existing agents.
5. **Redis failure handling**: The most dangerous single point of failure. Multi-AZ ElastiCache and the 90-second worker retry window are non-negotiable before onboarding real organizations.
