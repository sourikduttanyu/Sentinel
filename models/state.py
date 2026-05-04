from typing import TypedDict


class PRReviewState(TypedDict):
    pr_number: int
    repo: str
    diff: str
    files_changed: list[str]
    files_content: dict[str, str]  # filename -> full file content at PR head
    security_findings: list[dict]
    docs_findings: list[dict]
    performance_findings: list[dict]
    supervisor_summary: str
    human_approved: bool
    run_id: str
