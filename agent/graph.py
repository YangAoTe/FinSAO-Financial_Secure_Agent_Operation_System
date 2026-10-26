"""LangGraph control-flow skeleton with interrupt/resume and PostgreSQL checkpoints."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class AgentState(TypedDict, total=False):
    task_id: str
    session_id: str
    trace_id: str
    request_text: str
    intent: str
    plan: dict[str, Any]
    step_status: dict[str, str]
    result_reference: dict[str, Any]
    needs_approval: bool
    approval_preview: dict[str, Any]
    authorization_reference: str
    status: str
    error_code: str
    retry_count: int


def _ingest(state: AgentState) -> AgentState:
    return {"status": "INGESTED", "retry_count": state.get("retry_count", 0)}


def _route(_: AgentState) -> AgentState:
    return {"status": "ROUTED"}


def _plan(state: AgentState) -> AgentState:
    return {"status": "PLANNED", "plan": state.get("plan", {})}


def _validate(_: AgentState) -> AgentState:
    return {"status": "VALIDATED"}


def _execute(state: AgentState) -> AgentState:
    return {
        "status": "WAITING_APPROVAL" if state.get("needs_approval") else "EXECUTED",
        "step_status": state.get("step_status", {}),
    }


def _after_execute(state: AgentState) -> str:
    return "authorize" if state.get("needs_approval") else "reconcile"


def _authorize(state: AgentState) -> AgentState:
    resumed = interrupt(
        {
            "kind": "BANKING_APPROVAL",
            "task_id": state["task_id"],
            "preview": state.get("approval_preview", {}),
        }
    )
    if not isinstance(resumed, dict) or not resumed.get("authorization_reference"):
        return {"status": "FAILED", "error_code": "INVALID_RESUME"}
    return {
        "status": "AUTHORIZED",
        "authorization_reference": str(resumed["authorization_reference"]),
    }


def _reconcile(_: AgentState) -> AgentState:
    return {"status": "RECONCILED"}


def _respond(_: AgentState) -> AgentState:
    return {"status": "COMPLETED"}


def build_agent_graph(checkpointer: BaseCheckpointSaver[Any] | None = None):  # type: ignore[no-untyped-def]
    graph = StateGraph(AgentState)
    graph.add_node("ingest", _ingest)
    graph.add_node("route", _route)  # type: ignore[arg-type]
    graph.add_node("plan", _plan)
    graph.add_node("validate", _validate)  # type: ignore[arg-type]
    graph.add_node("execute", _execute)
    graph.add_node("authorize", _authorize)
    graph.add_node("reconcile", _reconcile)  # type: ignore[arg-type]
    graph.add_node("respond", _respond)  # type: ignore[arg-type]
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "route")
    graph.add_edge("route", "plan")
    graph.add_edge("plan", "validate")
    graph.add_edge("validate", "execute")
    graph.add_conditional_edges(
        "execute", _after_execute, {"authorize": "authorize", "reconcile": "reconcile"}
    )
    graph.add_edge("authorize", "reconcile")
    graph.add_edge("reconcile", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer, name="finpilot-agent-v1")


@contextmanager
def postgres_agent_graph(connection_string: str) -> Iterator[Any]:
    with PostgresSaver.from_conn_string(connection_string) as saver:
        saver.setup()
        yield build_agent_graph(saver)
