from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

import config
from models.state import PRReviewState


class SupervisorOutput(BaseModel):
    summary: str
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    markdown_review: str


def supervisor_node(state: PRReviewState) -> dict:
    security_findings = state.get("security_findings", [])
    docs_findings = state.get("docs_findings", [])
    performance_findings = state.get("performance_findings", [])

    print(f"[SupervisorAgent] security: {len(security_findings)} docs: {len(docs_findings)} performance: {len(performance_findings)}")

    if not security_findings and not docs_findings and not performance_findings:
        return {
            "supervisor_summary": "No findings. PR looks clean.",
        }

    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=config.ANTHROPIC_API_KEY,
        temperature=0,
    ).with_structured_output(SupervisorOutput)

    security_block = "\n".join(
        f"- [{f.get('severity', 'UNKNOWN')}] {f.get('file')}:{f.get('line')} — {f.get('description')} | Fix: {f.get('suggestion')}"
        for f in security_findings
    ) or "None."

    docs_block = "\n".join(
        f"- {f.get('file')} :: {f.get('function')} — {f.get('issue')}: {f.get('description')} | Fix: {f.get('suggestion')}"
        for f in docs_findings
    ) or "None."

    performance_block = "\n".join(
        f"- [{f.get('severity', 'UNKNOWN')}] {f.get('file')}:{f.get('line')} [{f.get('pattern')}] — {f.get('description')} | Fix: {f.get('suggestion')}"
        for f in performance_findings
    ) or "None."

    prompt = f"""You are a senior code review supervisor. Aggregate findings from SecurityAgent, DocsAgent, and PerformanceAgent into a final PR review.

SECURITY FINDINGS:
{security_block}

DOCUMENTATION FINDINGS:
{docs_block}

PERFORMANCE FINDINGS:
{performance_block}

Instructions:
1. Deduplicate — if multiple agents flagged the same function for different reasons, merge into one entry.
2. Rank by severity: CRITICAL → HIGH → MEDIUM → LOW → docs issues.
3. Resolve conflicts — if two findings overlap (same file+line), keep the more severe one and mention both.
4. Produce a clean markdown review comment suitable for posting directly on a GitHub PR.

Markdown format:
## Sentinel Review

### Summary
<one sentence>

### Security Issues
<ranked list, each with severity badge, file:line, description, suggestion>

### Performance Issues
<ranked list, each with severity badge, file:line, pattern, description, suggestion>

### Documentation Issues
<list of doc findings>

### Verdict
<APPROVE / REQUEST CHANGES> — <reason>

Be concise. No fluff. Engineers will read this in a PR."""

    result: SupervisorOutput = llm.invoke(prompt)
    print(f"[SupervisorAgent] review generated — {result.total_findings} total findings")

    return {"supervisor_summary": result.markdown_review}
