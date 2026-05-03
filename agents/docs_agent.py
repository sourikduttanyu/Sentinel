from models.state import PRReviewState


def docs_node(state: PRReviewState) -> dict:
    print("[DocsAgent] stub — received diff length:", len(state.get("diff", "")))
    return {"docs_findings": []}
