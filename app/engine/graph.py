"""
LangGraph workflow definition.

Flow:
  START
    └─► fetch_schema
          └─► generate_sql
                └─► security_guard ──── (blocked / clarification) ──► format_answer
                                   └─── (passed) ──► execute_sql ──► format_answer
                                                                          └─► END
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.engine.nodes import (
    node_execute_sql,
    node_fetch_schema,
    node_format_answer,
    node_generate_sql,
    node_security_guard,
)
from app.engine.state import AgentState

logger = logging.getLogger(__name__)


def _route_after_security(state: AgentState) -> str:
    """
    Conditional edge: after the security-guard node decide what to do next.
    - If the query passed → execute it.
    - Otherwise (blocked or clarification needed) → jump straight to formatting.
    """
    if state.get("security_passed"):
        return "execute_sql"
    return "format_answer"


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("fetch_schema",   node_fetch_schema)
    builder.add_node("generate_sql",   node_generate_sql)
    builder.add_node("security_guard", node_security_guard)
    builder.add_node("execute_sql",    node_execute_sql)
    builder.add_node("format_answer",  node_format_answer)

    # ── Edges ─────────────────────────────────────────────────────────────────
    builder.add_edge(START,            "fetch_schema")
    builder.add_edge("fetch_schema",   "generate_sql")
    builder.add_edge("generate_sql",   "security_guard")

    builder.add_conditional_edges(
        "security_guard",
        _route_after_security,
        {
            "execute_sql":   "execute_sql",
            "format_answer": "format_answer",
        },
    )

    builder.add_edge("execute_sql",  "format_answer")
    builder.add_edge("format_answer", END)

    return builder


# Compiled graph (singleton) – imported by the FastAPI layer
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("Compiling LangGraph workflow …")
        _compiled_graph = build_graph().compile()
    return _compiled_graph
