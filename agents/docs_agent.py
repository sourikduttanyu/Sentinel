from pydantic import BaseModel

from agents.llm_factory import get_llm
from models.state import PRReviewState


class DocsFinding(BaseModel):
    file: str
    function: str
    issue: str  # MISSING_DOCSTRING, STALE_DOCSTRING, MISSING_PARAM_DOCS
    description: str
    suggestion: str


class DocsFindings(BaseModel):
    findings: list[DocsFinding]


def docs_node(state: PRReviewState) -> dict:
    print("[DocsAgent] analyzing diff for documentation issues...")

    diff = state.get("diff", "")
    files_content = state.get("files_content", {})

    if not diff.strip():
        return {"docs_findings": []}

    llm = get_llm(DocsFindings)

    files_summary = "\n\n".join(
        f"=== {path} ===\n{content[:3000]}"
        for path, content in files_content.items()
        if path.endswith((".py", ".js", ".ts", ".jsx", ".tsx"))
    )

    prompt = f"""You are a documentation reviewer. Analyze this PR diff for documentation issues.

PR DIFF:
{diff[:4000]}

FULL FILE CONTENTS (code files only):
{files_summary[:4000] if files_summary else "No code files changed."}

Find functions, methods, or classes that are:
1. Added or modified in this diff AND have missing docstrings
2. Have docstrings that are outdated (parameters/return values changed but docs weren't updated)
3. Have docstrings missing parameter or return value documentation

Only flag functions that were actually added or changed in this diff.
Skip test functions, private helpers with obvious names, and one-liners.
If documentation is adequate or no code was changed, return an empty list."""

    result: DocsFindings = llm.invoke(prompt)
    print(f"[DocsAgent] found {len(result.findings)} documentation issues")

    return {"docs_findings": [f.model_dump() for f in result.findings]}
