"""Conversation facts and slots with explicit provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from agent.routing import Intent, IntentResult


class FactSource(StrEnum):
    USER_EXPLICIT = "USER_EXPLICIT"
    TOOL_VERIFIED = "TOOL_VERIFIED"
    SYSTEM_CONSTANT = "SYSTEM_CONSTANT"
    MODEL_INFERRED = "MODEL_INFERRED"


@dataclass(frozen=True, slots=True)
class SlotFact:
    name: str
    value: Any
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
        amount_match = self._AMOUNT.search(text)
        amount: str | None = None
        if amount_match:
            try:
                parsed = Decimal(amount_match.group(1)).quantize(Decimal("0.01"))
                if parsed > 0:
                    amount = format(parsed, "f")
            except InvalidOperation:
                pass
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
            if amount:
                facts["amount"] = SlotFact("amount", amount, FactSource.USER_EXPLICIT)
            currency = "CNY" if re.search(r"元|块|rmb|cny", text, re.IGNORECASE) else None
            if currency:
                facts["currency"] = SlotFact("currency", currency, FactSource.USER_EXPLICIT)
            beneficiary = re.search(
                r"(?:给|向)\s*([A-Za-z\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff ]{0,39}?)"
                r"\s*(?:转账|汇款|转)",
                text,
                re.IGNORECASE,
            )
            if beneficiary:
                facts["beneficiary_query"] = SlotFact(
                    "beneficiary_query",
                    beneficiary.group(1).strip(),
                    FactSource.USER_EXPLICIT,
                )
        elif intent.intent in {Intent.GET_BALANCE, Intent.GET_TRANSACTIONS} and ids:
            facts["account_id"] = SlotFact(
                "account_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
            )
        elif intent.intent == Intent.ANALYZE_SPENDING:
            match = re.search(r"(20\d{2})[-年/](\d{1,2})", text)
            today = date.today()
            year, month = (
                (int(match.group(1)), int(match.group(2))) if match else (today.year, today.month)
            )
            source = FactSource.USER_EXPLICIT if match else FactSource.SYSTEM_CONSTANT
            facts["year"] = SlotFact("year", str(year), source)
            facts["month"] = SlotFact("month", str(month), source)
        elif (
            intent.intent
            in {
                Intent.GET_BUDGET_STATUS,
                Intent.CANCEL_SUBSCRIPTION,
                Intent.GET_CARD,
                Intent.FREEZE_CARD,
                Intent.UNFREEZE_CARD,
                Intent.REPORT_CARD_LOST,
            }
            and ids
        ):
            facts["resource_id"] = SlotFact(
                "resource_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
            )
        elif intent.intent == Intent.UPDATE_CARD_LIMIT:
            if ids:
                facts["card_id"] = SlotFact("card_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT)
            if amount:
                facts["spending_limit"] = SlotFact(
                    "spending_limit", amount, FactSource.USER_EXPLICIT
                )
        elif intent.intent == Intent.UPDATE_BUDGET:
            if ids:
                facts["budget_id"] = SlotFact(
                    "budget_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
                )
            if amount:
                facts["limit_amount"] = SlotFact("limit_amount", amount, FactSource.USER_EXPLICIT)
        elif intent.intent == Intent.CREATE_BUDGET:
            category = next(
                (
                    value
                    for word, value in {
                        "家居": "HOUSEHOLD",
                        "日用": "GROCERIES",
                        "交通": "TRANSPORT",
                        "娱乐": "ENTERTAINMENT",
                        "餐饮": "DINING",
                    }.items()
                    if word in text
                ),
                None,
            )
            custom_category = re.search(
                r"(?:类别|分类|category)\s*(?:是|为|[:：=])?\s*([^，,;\n]+)",
                text,
                re.IGNORECASE,
            )
            if category is None and custom_category:
                category = custom_category.group(1).strip()
            month_match = re.search(r"(20\d{2})[-年/](\d{1,2})", text)
            if category:
                facts["category"] = SlotFact("category", category, FactSource.USER_EXPLICIT)
            if month_match:
                month_value = f"{int(month_match.group(1)):04d}-{int(month_match.group(2)):02d}-01"
                facts["month_date"] = SlotFact("month_date", month_value, FactSource.USER_EXPLICIT)
            if amount:
                facts["limit_amount"] = SlotFact("limit_amount", amount, FactSource.USER_EXPLICIT)
            if re.search(r"元|块|rmb|cny", text, re.IGNORECASE):
                facts["currency"] = SlotFact("currency", "CNY", FactSource.USER_EXPLICIT)
        elif intent.intent == Intent.CREATE_SAVINGS_POT:
            name_match = re.search(
                r"(?:创建|新增|设置)(?:一个)?(.{1,30}?)(?:储蓄罐|储藏罐|储蓄目标)", text
            )
            date_match = re.search(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?", text)
            if name_match:
                facts["name"] = SlotFact(
                    "name", name_match.group(1).strip(), FactSource.USER_EXPLICIT
                )
            else:
                event_match = re.search(
                    r"(?:我)?(妈妈|母亲|爸爸|父亲|奶奶|爷爷|外婆|外公|孩子|女儿|儿子)"
                    r"(?:要|将要|快要)?(?:过)?生日",
                    text,
                )
                if event_match:
                    facts["name"] = SlotFact(
                        "name",
                        f"{event_match.group(1)}生日",
                        FactSource.MODEL_INFERRED,
                    )
            if amount:
                facts["target_amount"] = SlotFact("target_amount", amount, FactSource.USER_EXPLICIT)
            if date_match:
                facts["target_date"] = SlotFact(
                    "target_date",
                    f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-"
                    f"{int(date_match.group(3)):02d}",
                    FactSource.USER_EXPLICIT,
                )
            if re.search(r"元|块|rmb|cny", text, re.IGNORECASE):
                facts["currency"] = SlotFact("currency", "CNY", FactSource.USER_EXPLICIT)
        elif intent.intent == Intent.CONTRIBUTE_SAVINGS_POT:
            if ids:
                facts["pot_id"] = SlotFact("pot_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT)
            if amount:
                facts["amount"] = SlotFact("amount", amount, FactSource.USER_EXPLICIT)
        elif intent.intent == Intent.COMPARE_WEALTH_PRODUCTS and len(ids) >= 2:
            facts["product_ids"] = SlotFact(
                "product_ids", [str(UUID(value)) for value in ids], FactSource.USER_EXPLICIT
            )
        elif intent.intent == Intent.ASSESS_RISK_PROFILE:
            answers = [int(value) for value in re.findall(r"(?<!\d)([1-5])(?!\d)", text)]
            if len(answers) == 5:
                facts["answers"] = SlotFact("answers", answers, FactSource.USER_EXPLICIT)
        elif intent.intent in {Intent.SUBSCRIBE_WEALTH, Intent.REDEEM_WEALTH}:
            if ids:
                facts["account_id"] = SlotFact(
                    "account_id", str(UUID(ids[0])), FactSource.USER_EXPLICIT
                )
            if len(ids) > 1:
                facts["product_id"] = SlotFact(
                    "product_id", str(UUID(ids[1])), FactSource.USER_EXPLICIT
                )
            if amount:
                facts["amount"] = SlotFact("amount", amount, FactSource.USER_EXPLICIT)
        for name, value in intent.proposed_slots.items():
            if (
                name in intent.required_slots
                and name not in facts
                and value is not None
                and value != ""
            ):
                facts[name] = SlotFact(name, value, FactSource.MODEL_INFERRED)
        missing = [slot for slot in intent.required_slots if slot not in facts]
        return SlotState(facts=facts, missing=missing)
