from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

import config  # noqa: F401 — triggers load_dotenv()
from models.state import PRReviewState
from tools.semgrep_tool import run_semgrep


class SecurityFinding(BaseModel):
    file: str
    line: int
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    suggestion: str


class SecurityFindings(BaseModel):
    findings: list[SecurityFinding]


_llm = ChatAnthropic(model="claude-haiku-4-5-20251001").with_structured_output(SecurityFindings)


def security_node(state: PRReviewState) -> dict:
    print("[SecurityAgent] running Semgrep...")
    raw_findings = run_semgrep(state.get("files_content", {}))
    print(f"[SecurityAgent] Semgrep found {len(raw_findings)} raw findings")

    diff = state.get("diff", "")
    semgrep_summary = (
        "\n".join(
            f"- {f['file']}:{f['line']} [{f['severity']}] {f['message']} (rule: {f['rule_id']})"
            for f in raw_findings
        )
        if raw_findings
        else "No findings from Semgrep."
    )

    prompt = f"""You are a security code reviewer. Analyze this PR diff and Semgrep findings.

SEMGREP FINDINGS:
{semgrep_summary}

PR DIFF:
{diff[:6000]}

Tasks:
1. Review the Semgrep findings — filter out false positives, keep real issues.
2. Identify any additional security issues visible in the diff that Semgrep missed.
3. For each real finding, provide: file, line number, severity (LOW/MEDIUM/HIGH/CRITICAL), clear description, and actionable suggestion.

Return only findings that are genuine security concerns. If none, return an empty list."""

    result: SecurityFindings = _llm.invoke(prompt)
    print(f"[SecurityAgent] Claude identified {len(result.findings)} security findings")

    return {"security_findings": [f.model_dump() for f in result.findings]}
