from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

import config
from models.state import PRReviewState


class PerformanceFinding(BaseModel):
    file: str
    line: int
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    pattern: str   # N_PLUS_ONE, UNBOUNDED_QUERY, SYNC_IO, MISSING_INDEX, INEFFICIENT_LOOP, MISSING_PAGINATION
    description: str
    suggestion: str


class PerformanceFindings(BaseModel):
    findings: list[PerformanceFinding]


def performance_node(state: PRReviewState) -> dict:
    print("[PerformanceAgent] analyzing diff for performance issues...")

    diff = state.get("diff", "")
    files_content = state.get("files_content", {})

    if not diff.strip():
        return {"performance_findings": []}

    llm = ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        api_key=config.ANTHROPIC_API_KEY,
        temperature=0,
    ).with_structured_output(PerformanceFindings)

    files_summary = "\n\n".join(
        f"=== {path} ===\n{content[:3000]}"
        for path, content in files_content.items()
        if path.endswith((".py", ".js", ".ts", ".jsx", ".tsx"))
    )

    prompt = f"""You are a performance code reviewer. Analyze this PR diff for performance issues.

PR DIFF:
{diff[:4000]}

FULL FILE CONTENTS (code files only):
{files_summary[:4000] if files_summary else "No code files changed."}

Find performance issues in code that was added or modified in this diff:

1. N+1 query patterns — queries inside loops, repeated DB calls that could be batched
2. Unbounded queries — SELECT without LIMIT on potentially large tables
3. Synchronous I/O in hot paths — blocking calls (file reads, HTTP) where async would apply
4. Missing index hints — filters on columns that are clearly unindexed based on context
5. Inefficient loops — O(n²) nested loops, repeated list scans that could use sets/dicts
6. Missing pagination — endpoints returning full collections without page size limits

Only flag code that was actually added or changed in this diff.
Skip test code, migrations, and one-time scripts.
If no performance issues exist, return an empty list."""

    result: PerformanceFindings = llm.invoke(prompt)
    print(f"[PerformanceAgent] found {len(result.findings)} performance issues")

    return {"performance_findings": [f.model_dump() for f in result.findings]}
