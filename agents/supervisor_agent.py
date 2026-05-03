from models.state import PRReviewState


def supervisor_node(state: PRReviewState) -> dict:
    print("[SupervisorAgent] stub — security:", len(state.get("security_findings", [])),
          "docs:", len(state.get("docs_findings", [])))
    return {"supervisor_summary": "stub summary"}
