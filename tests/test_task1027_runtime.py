from __future__ import annotations

from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from agent.capabilities import CapabilityBroker
from agent.context import SlotTracker
from agent.contracts import AgentRequest, AgentResponseStatus, TaskPlan
from agent.graph import build_runtime_agent_graph
from agent.hybrid import HybridPlanner, HybridRouter
from agent.planning import BaselinePlanner, PlanVerifier
from agent.providers import FakeModelProvider
from agent.routing import Intent, IntentResult, Route, RuleRouter
from agent.service import AgentService
from agent_tools.contracts import ExecutionContext, ToolResult, ToolResultStatus
from agent_tools.registry import ToolRegistry
from agent_tools.tools import register_default_tools
from banking_core.app.main import app


class FixtureOutput(BaseModel):
    value: str


class StatusOutput(BaseModel):
    status: str


class CapturingGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(
        self, *, tool_name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult[Any]:
        del arguments, context
        self.calls.append(tool_name)
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            data=FixtureOutput(value="verified-core-result"),
        )


class ReconciliationGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(
        self, *, tool_name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult[Any]:
        del arguments
        self.calls.append(tool_name)
        if tool_name == "freeze_card" and context.authorization_reference is None:
            return ToolResult(status=ToolResultStatus.WAITING_APPROVAL)
        if tool_name == "freeze_card":
            return ToolResult(
                status=ToolResultStatus.EXECUTION_ERROR,
                error_code="UNKNOWN_OUTCOME",
            )
        if tool_name == "get_card_status":
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data=StatusOutput(status="FROZEN"),
            )
        raise AssertionError(tool_name)


def build_service() -> tuple[AgentService, CapturingGateway]:
    registry = ToolRegistry()
    register_default_tools(registry, Mock())
    gateway = CapturingGateway()
    service = AgentService(
        router=RuleRouter(),
        slots=SlotTracker(),
        planner=BaselinePlanner(),
        verifier=PlanVerifier(registry),
        capabilities=CapabilityBroker(registry),
        gateway=gateway,
    )
    return service, gateway


@pytest.mark.asyncio
async def test_llm_fallback_handles_general_chat_without_tool_execution() -> None:
    router = HybridRouter(
        RuleRouter(),
        FakeModelProvider(
            {"intent": "GENERAL_CHAT", "confidence": 0.99, "reply": "你好，我能帮你。"}
        ),
    )
    result = await router.route("hello")
    assert result.intent == Intent.GENERAL_CHAT
    assert result.reply == "你好，我能帮你。"


@pytest.mark.asyncio
async def test_llm_candidate_dag_is_still_verified() -> None:
    candidate = TaskPlan.model_validate(
        {
            "goal": "查看银行卡",
            "steps": [
                {
                    "step_id": "list_cards",
                    "purpose": "读取银行卡",
                    "tool_call": {"tool_name": "list_cards", "arguments": {}},
                    "argument_sources": {},
                }
            ],
        }
    )
    planner = HybridPlanner(BaselinePlanner(), FakeModelProvider(candidate))
    intent = IntentResult(
        intent=Intent.LIST_CARDS,
        complexity=2,
        confidence=0.9,
        route=Route.PLANNER,
        reason="llm:fake/test",
    )
    plan = await planner.create(
        intent,
        SlotTracker().extract("请展示卡片", intent),
        request=AgentRequest(session_id=uuid4(), message="请展示卡片"),
        allowed_tools=[],
    )
    registry = ToolRegistry()
    register_default_tools(registry, Mock())
    verified = PlanVerifier(registry).verify(plan, {"cards.list"})
    assert verified.ordered_step_ids == ("list_cards",)


@pytest.mark.asyncio
async def test_online_langgraph_runs_verified_card_tool() -> None:
    service, gateway = build_service()
    graph = build_runtime_agent_graph(service, gateway, MemorySaver())
    session_id, task_id, user_id, trace_id = uuid4(), uuid4(), uuid4(), uuid4()
    request = AgentRequest(session_id=session_id, message="查看我的银行卡")
    state = await graph.ainvoke(
        {
            "task_id": str(task_id),
            "session_id": str(session_id),
            "trace_id": str(trace_id),
            "request_text": request.message,
            "request": request.model_dump(mode="json"),
            "context": {
                "authenticated_user_id": str(user_id),
                "session_id": str(session_id),
                "task_id": str(task_id),
                "trace_id": str(trace_id),
            },
        },
        {"configurable": {"thread_id": str(task_id)}},
    )
    assert state["status"] == "COMPLETED"
    assert state["response"]["status"] == AgentResponseStatus.COMPLETED
    assert gateway.calls == ["list_cards"]


@pytest.mark.asyncio
async def test_online_langgraph_reconciles_unknown_mutation_outcome() -> None:
    registry = ToolRegistry()
    register_default_tools(registry, Mock())
    gateway = ReconciliationGateway()
    service = AgentService(
        router=RuleRouter(),
        slots=SlotTracker(),
        planner=BaselinePlanner(),
        verifier=PlanVerifier(registry),
        capabilities=CapabilityBroker(registry),
        gateway=gateway,
    )
    graph = build_runtime_agent_graph(service, gateway, MemorySaver())
    task_id, session_id, user_id, trace_id, card_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    config = {"configurable": {"thread_id": str(task_id)}}
    request = AgentRequest(session_id=session_id, message=f"冻结银行卡 {card_id}")
    waiting = await graph.ainvoke(
        {
            "task_id": str(task_id),
            "session_id": str(session_id),
            "trace_id": str(trace_id),
            "request_text": request.message,
            "request": request.model_dump(mode="json"),
            "context": {
                "authenticated_user_id": str(user_id),
                "session_id": str(session_id),
                "task_id": str(task_id),
                "trace_id": str(trace_id),
            },
        },
        config,
    )
    assert waiting["status"] == "WAITING_APPROVAL"

    completed = await graph.ainvoke(
        Command(resume={"authorization_reference": "grant-fixture"}), config
    )
    assert completed["status"] == "COMPLETED"
    assert completed["response"]["status"] == "COMPLETED"
    assert completed["response"]["result"]["status"] == "FROZEN"
    assert gateway.calls == ["freeze_card", "freeze_card", "get_card_status"]


def test_savings_api_and_tools_are_exposed() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/savings-pots" in paths
    assert "/savings-pots/{pot_id}/contributions" in paths
    registry = ToolRegistry()
    register_default_tools(registry, Mock())
    names = {item["name"] for item in registry.list_allowed()}
    assert {"list_savings_pots", "create_savings_pot", "contribute_savings_pot"} <= names
