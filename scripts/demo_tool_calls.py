"""Phase 4 tool demo against a running Banking Core.

Set DEMO_SOURCE_ACCOUNT_ID and DEMO_DESTINATION_ACCOUNT_ID after seeding. The
server supplies identity through DEVELOPMENT_USER_ID; no model argument can do so.
"""

import asyncio
import os
from uuid import UUID, uuid4

import httpx

from agent_tools import ExecutionContext, ToolGateway, ToolRegistry
from agent_tools.client import BankingHttpClient, StaticServiceAuthenticator
from agent_tools.tools import register_default_tools


async def main() -> None:
    base_url = os.getenv("BANKING_BASE_URL", "http://localhost:8000")
    source = UUID(os.environ["DEMO_SOURCE_ACCOUNT_ID"])
    destination = UUID(os.environ["DEMO_DESTINATION_ACCOUNT_ID"])
    user = UUID(os.environ["DEVELOPMENT_USER_ID"])
    client = BankingHttpClient(base_url, StaticServiceAuthenticator("demo-only"))
    registry = ToolRegistry()
    register_default_tools(registry, client)
    gateway = ToolGateway(registry)
    context = ExecutionContext(user, uuid4(), uuid4(), uuid4())
    balance = await gateway.execute(
        tool_name="get_balance", arguments={"account_id": str(source)}, context=context
    )
    print("balance:", balance.model_dump(mode="json"))
    draft_result = await gateway.execute(
        tool_name="create_transfer_draft",
        arguments={
            "source_account_id": str(source),
            "destination_account_id": str(destination),
            "amount": "800.00",
            "currency": "CNY",
            "idempotency_key": "phase4-demo",
        },
        context=context,
    )
    print("draft:", draft_result.model_dump(mode="json"))
    if draft_result.data is None:
        await client.close()
        return
    async with httpx.AsyncClient(base_url=base_url) as approval_client:
        approval = (
            await approval_client.post(
                "/security/approvals", json={"operation_id": str(draft_result.data.id)}
            )
        ).json()
        grant = (
            await approval_client.post(
                f"/security/approvals/{approval['id']}/decision", json={"accepted": True}
            )
        ).json()
    authorized = ExecutionContext(
        user, context.session_id, context.task_id, context.trace_id, grant["authorization_ref"]
    )
    receipt = await gateway.execute(
        tool_name="commit_transfer",
        arguments={"draft_id": str(draft_result.data.id)},
        context=authorized,
    )
    print("receipt:", receipt.model_dump(mode="json"))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
