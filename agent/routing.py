"""Deterministic intent contracts and a conservative rule-first router."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Intent(StrEnum):
    LIST_ACCOUNTS = "LIST_ACCOUNTS"
    GET_BALANCE = "GET_BALANCE"
    GET_TRANSACTIONS = "GET_TRANSACTIONS"
    TRANSFER = "TRANSFER"
    UNKNOWN = "UNKNOWN"


class Route(StrEnum):
    RULE_DIRECT = "RULE_DIRECT"
    PLANNER = "PLANNER"
    SAFE_FALLBACK = "SAFE_FALLBACK"


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    complexity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    route: Route
    reason: str
    required_slots: list[str] = Field(default_factory=list)


class RuleRouter:
    _INJECTION_MARKERS = (
        "忽略规则",
        "忽略之前",
        "system prompt",
        "隐藏工具",
        "绕过审批",
        "伪造授权",
    )

    def route(self, text: str) -> IntentResult:
        normalized = re.sub(r"\s+", "", text).lower()
        has_injection_marker = any(marker in normalized for marker in self._INJECTION_MARKERS)
        if any(word in normalized for word in ("转账", "转给", "汇款")) or re.search(
            r"转\d", normalized
        ):
            return IntentResult(
                intent=Intent.TRANSFER,
                complexity=3,
                confidence=0.9,
                route=Route.PLANNER,
                reason="write operations always require planning and deterministic verification",
                required_slots=[
                    "source_account_id",
                    "destination_account_id",
                    "amount",
                    "currency",
                ],
            )
        if not has_injection_marker and normalized in {"查看我的账户", "我的账户", "账户列表"}:
            return IntentResult(
                intent=Intent.LIST_ACCOUNTS,
                complexity=1,
                confidence=1.0,
                route=Route.RULE_DIRECT,
                reason="exact allowlisted Green account-list query",
            )
        if "余额" in normalized:
            return IntentResult(
                intent=Intent.GET_BALANCE,
                complexity=1,
                confidence=0.98 if not has_injection_marker else 0.4,
                route=Route.PLANNER if has_injection_marker else Route.RULE_DIRECT,
                reason=(
                    "untrusted instruction marker prevents direct routing"
                    if has_injection_marker
                    else "allowlisted Green balance query"
                ),
                required_slots=["account_id"],
            )
        if any(word in normalized for word in ("流水", "交易记录", "明细")):
            return IntentResult(
                intent=Intent.GET_TRANSACTIONS,
                complexity=1,
                confidence=0.9,
                route=Route.PLANNER if has_injection_marker else Route.RULE_DIRECT,
                reason="Green transaction query; account selection is still explicit",
                required_slots=["account_id"],
            )
        return IntentResult(
            intent=Intent.UNKNOWN,
            complexity=2,
            confidence=0.0,
            route=Route.SAFE_FALLBACK,
            reason="request is outside deterministic supported intents",
        )
