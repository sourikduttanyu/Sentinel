from models.state import PRReviewState


def security_node(state: PRReviewState) -> dict:
    print("[SecurityAgent] stub — received diff length:", len(state.get("diff", "")))
    return {"security_findings": []}
