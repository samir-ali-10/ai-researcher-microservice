from langgraph.graph import END, START, StateGraph

from app.agent.nodes import researcher_node, retriever_node, route_after_retrieve, writer_node
from app.agent.state import ResearchState
from app.schemas import ResearchReport


def build_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("retriever", retriever_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)

    graph.add_edge(START, "retriever")
    graph.add_conditional_edges(
        "retriever",
        route_after_retrieve,
        {
            "researcher": "researcher",
            "writer": "writer",
        },
    )
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", END)
    return graph.compile()


def run_research(query: str) -> ResearchReport:
    app = build_research_graph()
    final_state = app.invoke({"query": query})
    report = final_state["final_report"]
    if isinstance(report, ResearchReport):
        return report
    return ResearchReport.model_validate(report)
