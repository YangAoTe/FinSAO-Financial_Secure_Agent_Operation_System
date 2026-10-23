from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from pydantic import BaseModel

from agent_tools.client import (
    BankingHttpClient,
    StaticServiceAuthenticator,
    UnknownMutationOutcome,
)
from agent_tools.contracts import BaseBankingTool, ExecutionContext, ToolResultStatus
from agent_tools.gateway import ToolGateway
from agent_tools.registry import ToolRegistry
from agent_tools.tools import CommitTransferTool, GetBalanceTool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


class EchoTool(BaseBankingTool[EchoInput, EchoOutput]):
    name = "echo"
    description = "echo"
    action = "read"
    risk_policy = "GREEN"
    input_model = EchoInput
    output_model = EchoOutput

    async def execute(self, input_data: EchoInput, context: ExecutionContext) -> EchoOutput:
        del context
        return EchoOutput(text=input_data.text)


class PendingOutput(BaseModel):
    status: str


class PendingTool(BaseBankingTool[EchoInput, PendingOutput]):
    name = "pending"
    description = "pending"
    action = "write"
    risk_policy = "YELLOW"
    input_model = EchoInput
    output_model = PendingOutput

    async def execute(self, input_data: EchoInput, context: ExecutionContext) -> PendingOutput:
        del input_data, context
        return PendingOutput(status="PENDING_AUTHORIZATION")


def context(authorization: str | None = None) -> ExecutionContext:
    return ExecutionContext(uuid4(), uuid4(), uuid4(), uuid4(), authorization)


def test_registry_rejects_duplicates_and_exports_schema() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(EchoTool())
    assert registry.export_input_schema("echo")["properties"] == {
        "text": {"title": "Text", "type": "string"}
    }


@pytest.mark.asyncio
async def test_gateway_validates_input_and_unknown_tools() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    gateway = ToolGateway(registry)
    invalid = await gateway.execute(tool_name="echo", arguments={}, context=context())
    unknown = await gateway.execute(tool_name="missing", arguments={}, context=context())
    assert invalid.status == ToolResultStatus.VALIDATION_ERROR
    assert unknown.error_code == "UNKNOWN_TOOL"


@pytest.mark.asyncio
async def test_pending_operation_has_distinct_result_status() -> None:
    registry = ToolRegistry()
    registry.register(PendingTool())
    result = await ToolGateway(registry).execute(
        tool_name="pending", arguments={"text": "x"}, context=context()
    )
    assert result.status == ToolResultStatus.WAITING_APPROVAL


@pytest.mark.asyncio
async def test_http_tool_validates_typed_output() -> None:
    account_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-trace-id"]
        return httpx.Response(
            200, json={"account_id": str(account_id), "balance": "12.34", "currency": "CNY"}
        )

    client = BankingHttpClient(
        "http://banking",
        StaticServiceAuthenticator("test"),
        transport=httpx.MockTransport(handler),
    )
    registry = ToolRegistry()
    registry.register(GetBalanceTool(client))
    result = await ToolGateway(registry).execute(
        tool_name="get_balance", arguments={"account_id": str(account_id)}, context=context()
    )
    await client.close()
    assert result.status == ToolResultStatus.SUCCESS
    assert result.data is not None and result.data.balance == Decimal("12.34")


def test_commit_schema_does_not_expose_authorization() -> None:
    client = BankingHttpClient("http://banking", StaticServiceAuthenticator("test"))
    schema = CommitTransferTool(client).input_model.model_json_schema()
    assert "authorization" not in str(schema).lower()


@pytest.mark.asyncio
async def test_timeout_after_committed_mutation_is_reconciled_by_status() -> None:
    operation_id = uuid4()
    committed = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal committed
        if request.method == "POST":
            committed = True
            raise httpx.ReadTimeout("response lost", request=request)
        return httpx.Response(
            200,
            json={"id": str(operation_id), "status": "COMPLETED" if committed else "DRAFT"},
        )

    class StatusOutput(BaseModel):
        id: str
        status: str

    client = BankingHttpClient(
        "http://banking",
        StaticServiceAuthenticator("test"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(UnknownMutationOutcome):
        await client.request(
            "POST",
            f"/operations/{operation_id}/commit",
            context(),
            StatusOutput,
            mutation=True,
            idempotency_key="stable-key",
        )
    recovered = await client.request("GET", f"/operations/{operation_id}", context(), StatusOutput)
    await client.close()
    assert recovered.status == "COMPLETED"
