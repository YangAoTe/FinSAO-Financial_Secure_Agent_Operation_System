"""Least-privilege tool disclosure based only on trusted stage and intent."""

from __future__ import annotations

from agent.contracts import TrustedAgentContext
from agent.routing import Intent
from agent_tools.registry import ToolRegistry


class CapabilityBroker:
    _ACTIONS: dict[Intent, set[str]] = {
        Intent.LIST_ACCOUNTS: {"accounts.list"},
        Intent.GET_BALANCE: {"accounts.list", "balance.query"},
        Intent.GET_TRANSACTIONS: {"accounts.list", "transactions.query"},
        Intent.TRANSFER: {
            "accounts.list",
            "balance.query",
            "beneficiaries.resolve",
            "transfer.draft",
            "transfer.status",
        },
        Intent.UNKNOWN: set(),
    }

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def allowed_actions(
        self, *, context: TrustedAgentContext, intent: Intent, stage: str = "planning"
    ) -> set[str]:
        del context
        actions = set(self._ACTIONS[intent])
        if stage != "authorized_execution":
            actions.discard("transfer.commit")
        return actions

    def schemas(
        self, *, context: TrustedAgentContext, intent: Intent, stage: str = "planning"
    ) -> list[dict[str, object]]:
        actions = self.allowed_actions(context=context, intent=intent, stage=stage)
        return self._registry.list_allowed(actions)
