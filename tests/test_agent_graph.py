from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graph import build_agent_graph


@pytest.mark.asyncio
async def test_graph_interrupts_and_resumes_from_checkpoint() -> None:
    graph = build_agent_graph(MemorySaver())
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = {
        "task_id": str(uuid4()),
        "session_id": str(uuid4()),
        "trace_id": str(uuid4()),
        "request_text": "转账 800 元",
        "needs_approval": True,
        "approval_preview": {"amount": "800.00", "currency": "CNY"},
    }
    interrupted = await graph.ainvoke(state, config)
    assert interrupted["status"] == "WAITING_APPROVAL"
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("authorize",)

    resumed = await graph.ainvoke(
        Command(resume={"authorization_reference": "grant-fixture"}), config
    )
    assert resumed["status"] == "COMPLETED"
    assert resumed["authorization_reference"] == "grant-fixture"


@pytest.mark.asyncio
async def test_green_graph_completes_without_interrupt() -> None:
    graph = build_agent_graph(MemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = await graph.ainvoke(
        {
            "task_id": str(uuid4()),
            "session_id": str(uuid4()),
            "trace_id": str(uuid4()),
            "request_text": "查看我的账户",
            "needs_approval": False,
        },
        config,
    )
    assert result["status"] == "COMPLETED"
