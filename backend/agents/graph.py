from langgraph.graph import END, START, StateGraph

from backend.agents.nodes import (
    citation_verifier_node,
    contradiction_detector_node,
    generator_node,
    grader_node,
    hallucination_checker_node,
    planner_node,
    retriever_node,
    web_search_node,
)
from backend.agents.state import AgentState


def _route_after_grader(state: AgentState) -> str:
    """Relevant chunks → contradiction check → generator. No chunks → web search."""
    if state["is_relevant"] and state["chunks"]:
        return "contradiction_detector"
    return "web_search"


def _route_after_web_search(state: AgentState) -> str:
    """Web results found → generator. Nothing found → end."""
    return "generator" if state["chunks"] else END


def build_graph():
    """Build and compile the full agentic RAG graph.

    Flow:
      planner → retriever → grader
                                ├─ relevant → contradiction_detector → generator → citation_verifier → hallucination_checker → END
                                └─ not relevant → web_search → generator → citation_verifier → hallucination_checker → END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("contradiction_detector", contradiction_detector_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("citation_verifier", citation_verifier_node)
    workflow.add_node("hallucination_checker", hallucination_checker_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "grader")
    workflow.add_conditional_edges("grader", _route_after_grader)
    workflow.add_edge("contradiction_detector", "generator")
    workflow.add_conditional_edges("web_search", _route_after_web_search)
    workflow.add_edge("generator", "citation_verifier")
    workflow.add_edge("citation_verifier", "hallucination_checker")
    workflow.add_edge("hallucination_checker", END)

    return workflow.compile()
