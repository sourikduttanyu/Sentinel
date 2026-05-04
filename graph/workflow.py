import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from agents.docs_agent import docs_node
from agents.security_agent import security_node
from agents.supervisor_agent import supervisor_node
from models.state import PRReviewState
from tools.github_tool import get_installation_token, post_review_comment


def post_comment_node(state: PRReviewState) -> dict:
    repo = state["repo"]
    pr_number = state["pr_number"]
    summary = state.get("supervisor_summary", "")

    print(f"[PostComment] posting review to {repo}#{pr_number}")
    token = get_installation_token()
    post_review_comment(repo, pr_number, summary, token)
    print("[PostComment] comment posted successfully")
    return {"human_approved": True}


def build_graph(checkpointer):
    builder = StateGraph(PRReviewState)

    builder.add_node("security", security_node)
    builder.add_node("docs", docs_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("post_comment", post_comment_node)

    # Parallel fan-out
    builder.add_edge(START, "security")
    builder.add_edge(START, "docs")

    # Both agents → supervisor → post comment
    builder.add_edge("security", "supervisor")
    builder.add_edge("docs", "supervisor")
    builder.add_edge("supervisor", "post_comment")
    builder.add_edge("post_comment", END)

    # Pause before posting — human must approve via /approve/{run_id}
    return builder.compile(checkpointer=checkpointer, interrupt_before=["post_comment"])


_conn = sqlite3.connect("sentinel.db", check_same_thread=False)
checkpointer = SqliteSaver(_conn)
graph = build_graph(checkpointer)
