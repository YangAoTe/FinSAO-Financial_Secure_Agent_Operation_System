"""Persisted Phase 7 scenarios through the public ToolGateway.

Requires a migrated/seeded PostgreSQL database and a running API configured with
DEVELOPMENT_USER_ID equal to the deterministic Lin demo user.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID, uuid4

from agent_tools import ExecutionContext, ToolGateway, ToolRegistry
from agent_tools.client import BankingHttpClient, StaticServiceAuthenticator
from agent_tools.contracts import ToolResult
from agent_tools.tools import register_default_tools
from banking_core.app.persistence.database import get_session_factory
from banking_core.app.security.approvals import ApprovalService, MockMfaProvider
from scripts.seed_demo_data import stable_id


def data(result: ToolResult[Any]) -> dict[str, Any]:
    value = result.model_dump(mode="json")["data"]
    if not isinstance(value, dict):
        raise RuntimeError(f"tool failed: {result.model_dump(mode='json')}")
    return value


def approve(operation_id: str, user_id: UUID, *, mfa: bool) -> str:
    with get_session_factory()() as session:
        approval = ApprovalService(session).create_for_operation(
            stable_uuid(operation_id), stable_uuid(str(user_id))
        )
        approval_id = approval.id
    with get_session_factory()() as session:
        if mfa:
            challenge, code = MockMfaProvider(session).create_challenge(
                approval_id, stable_uuid(str(user_id))
            )
            grant = MockMfaProvider(session).verify(challenge.id, stable_uuid(str(user_id)), code)
            return str(grant.id)
        confirmed = ApprovalService(session).decide(approval_id, stable_uuid(str(user_id)), True)
        if confirmed is None:
            raise RuntimeError("approval was rejected")
        return str(confirmed.id)


def stable_uuid(value: str) -> UUID:
    return UUID(value)


async def main() -> None:
    user_id = stable_id("user:lin")
    source_id = stable_id("account:lin:checking")
    destination_id = stable_id("account:chen:checking")
    budget_id = stable_id("budget:lin:2026-03")
    subscription_id = stable_id("subscription:lin")
    base_url = os.getenv("BANKING_BASE_URL", "http://localhost:8000")
    client = BankingHttpClient(base_url, StaticServiceAuthenticator("demo-service"), timeout=10)
    registry = ToolRegistry()
    register_default_tools(registry, client)
    gateway = ToolGateway(registry)
    base_context = ExecutionContext(user_id, uuid4(), uuid4(), uuid4())

    print("Scenario A - Green")
    print(
        (
            await gateway.execute(
                tool_name="get_balance",
                arguments={"account_id": str(source_id)},
                context=base_context,
            )
        ).model_dump(mode="json")
    )
    print(
        (
            await gateway.execute(
                tool_name="analyze_spending",
                arguments={"year": 2026, "month": 3},
                context=base_context,
            )
        ).model_dump(mode="json")
    )

    async def transfer(amount: str, label: str) -> None:
        draft_result = await gateway.execute(
            tool_name="create_transfer_draft",
            arguments={
                "source_account_id": str(source_id),
                "destination_account_id": str(destination_id),
                "amount": amount,
                "currency": "CNY",
                "idempotency_key": f"e2e-{label}-{uuid4()}",
            },
            context=base_context,
        )
        draft = data(draft_result)
        authorization = approve(draft["id"], user_id, mfa=label == "red")
        authorized = ExecutionContext(
            user_id,
            base_context.session_id,
            base_context.task_id,
            base_context.trace_id,
            authorization,
        )
        receipt = await gateway.execute(
            tool_name="commit_transfer", arguments={"draft_id": draft["id"]}, context=authorized
        )
        print(receipt.model_dump(mode="json"))

    print("Scenario B - Yellow CNY 800")
    await transfer("800.00", "yellow")
    print("Scenario C - Red CNY 1,500 with simulated MFA")
    await transfer("1500.00", "red")

    print("Scenario D - budget, subscriptions, authorized cancellation")
    subscription_result: ToolResult[Any] | None = None
    for name, arguments in [
        ("get_budget_status", {"resource_id": str(budget_id)}),
        ("detect_recurring_payments", {}),
        ("list_subscriptions", {}),
    ]:
        result = await gateway.execute(tool_name=name, arguments=arguments, context=base_context)
        print(result.model_dump(mode="json"))
        if name == "list_subscriptions":
            subscription_result = result
    subscriptions = data(subscription_result) if subscription_result is not None else {"items": []}
    active = any(
        item["id"] == str(subscription_id) and item["active"]
        for item in subscriptions.get("items", [])
    )
    if active:
        cancel_ref = approve(str(subscription_id), user_id, mfa=False)
        cancel_context = ExecutionContext(
            user_id,
            base_context.session_id,
            base_context.task_id,
            base_context.trace_id,
            cancel_ref,
        )
        print(
            (
                await gateway.execute(
                    tool_name="cancel_subscription",
                    arguments={"resource_id": str(subscription_id)},
                    context=cancel_context,
                )
            ).model_dump(mode="json")
        )
    else:
        print({"subscription_id": str(subscription_id), "status": "ALREADY_CANCELLED"})
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
