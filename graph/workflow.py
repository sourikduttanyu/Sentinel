from langgraph.graph import StateGraph, START, END

from agents.docs_agent import docs_node
from agents.security_agent import security_node
from agents.supervisor_agent import supervisor_node
from models.state import PRReviewState


def build_graph():
    builder = StateGraph(PRReviewState)

    builder.add_node("security", security_node)
    builder.add_node("docs", docs_node)
    builder.add_node("supervisor", supervisor_node)

    # Parallel fan-out: both agents start immediately
    builder.add_edge(START, "security")
    builder.add_edge(START, "docs")

    # Both feed into supervisor
    builder.add_edge("security", "supervisor")
    builder.add_edge("docs", "supervisor")

    builder.add_edge("supervisor", END)

    return builder.compile()


graph = build_graph()
