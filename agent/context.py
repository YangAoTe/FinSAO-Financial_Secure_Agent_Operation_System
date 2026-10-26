"""Conversation facts and slots with explicit provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from agent.routing import Intent, IntentResult


class FactSource(StrEnum):
    USER_EXPLICIT = "USER_EXPLICIT"
    TOOL_VERIFIED = "TOOL_VERIFIED"
    MODEL_INFERRED = "MODEL_INFERRED"


@dataclass(frozen=True, slots=True)
class SlotFact:
    name: str
    value: str
    source: FactSource


@dataclass(slots=True)
class SlotState:
    facts: dict[str, SlotFact] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


class SlotTracker:
    _AMOUNT = re.compile(r"(?<![\d.])(\d+(?:\.\d{1,2})?)\s*(?:元|块|rmb|cny)", re.IGNORECASE)
    _UUID = re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
    )

    def extract(self, text: str, intent: IntentResult) -> SlotState:
        facts: dict[str, SlotFact] = {}
        ids = self._UUID.findall(text)
        if intent.intent == Intent.TRANSFER:
            if "余额" in text:
                facts["include_balance"] = SlotFact(
                    "include_balance", "true", FactSource.USER_EXPLICIT
                )
            if ids:
                facts["source_account_id"] = SlotFact(
                    "source_account_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
                )
            if len(ids) > 1:
                facts["destination_account_id"] = SlotFact(
                    "destination_account_id", str(UUID(ids[1])), FactSource.USER_EXPLICIT
                )
            amount_match = self._AMOUNT.search(text)
            if amount_match:
                try:
                    amount = Decimal(amount_match.group(1)).quantize(Decimal("0.01"))
                    if amount > 0:
                        facts["amount"] = SlotFact(
                            "amount", format(amount, "f"), FactSource.USER_EXPLICIT
                        )
                except InvalidOperation:
                    pass
            currency = "CNY" if re.search(r"元|块|rmb|cny", text, re.IGNORECASE) else None
            if currency:
                facts["currency"] = SlotFact("currency", currency, FactSource.USER_EXPLICIT)
        elif intent.intent in {Intent.GET_BALANCE, Intent.GET_TRANSACTIONS} and ids:
            facts["account_id"] = SlotFact(
                "account_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
            )
        missing = [slot for slot in intent.required_slots if slot not in facts]
        return SlotState(facts=facts, missing=missing)
