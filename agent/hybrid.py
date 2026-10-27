"""Configurable LLM-only or rule-first routing with deterministic safety boundaries."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from agent.context import FactSource, SlotState
from agent.contracts import (
    AgentRequest,
    ArgumentSourceKind,
    ConversationMessage,
    ConversationRole,
    TaskPlan,
    TrustLabel,
)
from agent.planning import BaselinePlanner
from agent.providers import ModelProvider, ProviderError
from agent.routing import REQUIRED_SLOTS_BY_INTENT, Intent, IntentResult, Route, RuleRouter

logger = logging.getLogger(__name__)


class LlmIntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    reply: str | None = Field(default=None, max_length=1_000)
    proposed_slots: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("proposed_slots")
    @classmethod
    def reject_trusted_slots(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        forbidden = {
            "user_id",
            "authenticated_user_id",
            "authorization_ref",
            "authorization_reference",
            "mfa_code",
            "risk_tier",
            "approved",
        }
        if forbidden.intersection(value):
            raise ValueError("trusted fields are forbidden in inferred slots")
        return value


class HybridRouter:
    """Route with either rule-first fallback or an LLM-only experiment mode."""

    def __init__(
        self,
        rules: RuleRouter,
        provider: ModelProvider | None,
        *,
        confidence_threshold: float = 0.65,
        routing_mode: str = "hybrid",
        today: Callable[[], date] = date.today,
    ) -> None:
        self._rules = rules
        self._provider = provider
        self._confidence_threshold = confidence_threshold
        self._routing_mode = routing_mode
        self._today = today

    async def route(
        self, text: str, *, conversation: list[Any] | None = None
    ) -> IntentResult:
        deterministic = self._rules.route(text, conversation=conversation)
        if self._routing_mode == "hybrid" and deterministic.route != Route.SAFE_FALLBACK:
            return deterministic
        if "instruction marker" in deterministic.reason:
            return deterministic
        if self._provider is None or not self._provider.available:
            return self._unavailable_fallback(deterministic)
        supported = ", ".join(intent.value for intent in Intent if intent != Intent.UNKNOWN)
        today = self._today().isoformat()
        messages = [
            ConversationMessage(
                role=ConversationRole.SYSTEM,
                trust=TrustLabel.SYSTEM_POLICY,
                content=(
                    "你是银行助手的结构化意图与候选参数提取器。只输出一个 JSON 对象，"
                    "字段必须严格为："
                    '{"intent":"枚举值","confidence":0到1,"reply":null或字符串,'
                    '"proposed_slots":{"字段名":"候选值"}}。'
                    "不要输出分析、Markdown 或额外字段。不得声称金融操作成功，"
                    "不得生成身份、授权、验证码或风险等级。普通问候使用 GENERAL_CHAT；"
                    "普通问候的 reply 给出简短自然回复，银行任务的 reply 使用 null；"
                    "从用户当前消息和连续澄清上下文中提取候选参数。金额使用两位小数字符串，"
                    "币种默认 CNY；相对日期可以根据今天换算，但只能作为 proposed_slots，"
                    "后端会要求用户确认后才执行。创建预算使用 CREATE_BUDGET，而不是"
                    "LIST_BUDGETS；month_date 使用月份第一天 YYYY-MM-01。"
                    "对于预算或储蓄目标，可根据用户明确说明的用途提出简短、可读的自定义"
                    "category/name，例如‘给妈妈过生日’可提出‘妈妈生日’；这仍只是待确认候选。"
                    "不得猜测 UUID、账户、银行卡、联系人或理财产品标识；用户没有明确提供"
                    "这些标识时应省略对应 slot。"
                    f"今天是 {today}。"
                    f"支持的 intent: {supported}。"
                ),
            ),
            *(conversation or [])[-10:],
            ConversationMessage(role=ConversationRole.USER, content=text),
        ]
        try:
            generated = await self._provider.generate_structured(
                messages=messages,
                output_model=LlmIntentDecision,
                temperature=0,
                max_tokens=512,
            )
        except ProviderError as exc:
            logger.warning(
                "LLM intent fallback failed provider=%s code=%s request_id=%s",
                exc.provider,
                exc.code,
                exc.request_id,
            )
            return self._unavailable_fallback(deterministic)
        decision = generated.output
        if decision.confidence < self._confidence_threshold or decision.intent == Intent.UNKNOWN:
            return self._unavailable_fallback(deterministic)
        required_slots = list(REQUIRED_SLOTS_BY_INTENT.get(decision.intent, ()))
        proposed_slots = {
            name: value
            for name, value in decision.proposed_slots.items()
            if name in required_slots and value is not None and value != ""
        }
        return IntentResult(
            intent=decision.intent,
            complexity=1 if decision.intent == Intent.GENERAL_CHAT else 3,
            confidence=decision.confidence,
            route=(Route.RULE_DIRECT if decision.intent == Intent.GENERAL_CHAT else Route.PLANNER),
            reason=f"llm:{generated.provider}/{generated.model}",
            required_slots=required_slots,
            proposed_slots=proposed_slots,
            reply=decision.reply,
        )

    def _unavailable_fallback(self, deterministic: IntentResult) -> IntentResult:
        if self._routing_mode == "hybrid":
            return deterministic
        return IntentResult(
            intent=Intent.UNKNOWN,
            complexity=2,
            confidence=0,
            route=Route.SAFE_FALLBACK,
            reason="llm-only routing unavailable or below confidence threshold",
        )


class HybridPlanner:
    """Generate a candidate DAG with the LLM, then leave execution to PlanVerifier."""

    def __init__(self, baseline: BaselinePlanner, provider: ModelProvider | None) -> None:
        self._baseline = baseline
        self._provider = provider

    async def create(
        self,
        intent: IntentResult,
        slots: SlotState,
        *,
        system_idempotency_key: str | None = None,
        request: AgentRequest | None = None,
        allowed_tools: list[dict[str, object]] | None = None,
    ) -> TaskPlan:
        if not intent.reason.startswith("llm:") or self._provider is None or request is None:
            return self._baseline.create(
                intent,
                slots,
                system_idempotency_key=system_idempotency_key,
            )
        tool_json = json.dumps(allowed_tools or [], ensure_ascii=False, default=str)
        fact_json = json.dumps(
            {
                name: {"value": fact.value, "source": fact.source.value}
                for name, fact in slots.facts.items()
            },
            ensure_ascii=False,
        )
        messages = [
            ConversationMessage(
                role=ConversationRole.SYSTEM,
                trust=TrustLabel.SYSTEM_POLICY,
                content=(
                    "为银行请求生成严格 TaskPlan JSON。只能使用提供的工具；不得添加身份、"
                    "授权、MFA 或风险字段。每个参数都必须有 argument_sources。没有明确事实的"
                    "参数标记 MODEL_INFERRED，它会被安全验证器拒绝并触发澄清。工具："
                    f"{tool_json}\n可信槽位：{fact_json}"
                ),
            ),
            ConversationMessage(role=ConversationRole.USER, content=request.message),
        ]
        try:
            generated = await self._provider.generate_structured(
                messages=messages,
                output_model=TaskPlan,
                request_id=request.request_id,
                temperature=0,
                max_tokens=2_048,
            )
        except ProviderError as exc:
            logger.warning(
                "LLM plan fallback failed provider=%s code=%s request_id=%s",
                exc.provider,
                exc.code,
                exc.request_id,
            )
            return self._baseline.create(
                intent,
                slots,
                system_idempotency_key=system_idempotency_key,
            )
        return self._server_bind_sources(generated.output, slots, system_idempotency_key)

    @staticmethod
    def _server_bind_sources(
        plan: TaskPlan, slots: SlotState, system_idempotency_key: str | None
    ) -> TaskPlan:
        raw = plan.model_dump(mode="python")
        for step in raw["steps"]:
            call = step.get("tool_call")
            if call is None:
                continue
            sources: dict[str, dict[str, str]] = {}
            for name, value in call["arguments"].items():
                fact = slots.facts.get(name)
                if name == "idempotency_key" and system_idempotency_key:
                    call["arguments"][name] = system_idempotency_key
                    sources[name] = {
                        "kind": ArgumentSourceKind.SYSTEM_CONSTANT.value,
                        "reference": "trusted task id binding",
                    }
                elif fact is not None and str(value) == fact.value:
                    kind = {
                        FactSource.USER_EXPLICIT: ArgumentSourceKind.USER_EXPLICIT,
                        FactSource.TOOL_VERIFIED: ArgumentSourceKind.TOOL_VERIFIED,
                        FactSource.SYSTEM_CONSTANT: ArgumentSourceKind.SYSTEM_CONSTANT,
                        FactSource.MODEL_INFERRED: ArgumentSourceKind.MODEL_INFERRED,
                    }[fact.source]
                    sources[name] = {
                        "kind": kind.value,
                        "reference": f"slot:{name}",
                    }
                else:
                    sources[name] = {
                        "kind": ArgumentSourceKind.MODEL_INFERRED.value,
                        "reference": "untrusted model output",
                    }
            step["argument_sources"] = sources
        return TaskPlan.model_validate(raw)
