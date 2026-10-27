"""Rule-first routing with an optional structured LLM fallback."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ConfigDict, Field

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
from agent.routing import Intent, IntentResult, Route, RuleRouter

logger = logging.getLogger(__name__)


class LlmIntentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    reply: str | None = Field(default=None, max_length=1_000)


_REQUIRED_SLOTS: dict[Intent, list[str]] = {
    Intent.GET_BALANCE: ["account_id"],
    Intent.GET_TRANSACTIONS: ["account_id"],
    Intent.TRANSFER: ["source_account_id", "destination_account_id", "amount", "currency"],
    Intent.ANALYZE_SPENDING: ["year", "month"],
    Intent.GET_BUDGET_STATUS: ["resource_id"],
    Intent.CREATE_BUDGET: ["category", "month_date", "limit_amount", "currency"],
    Intent.UPDATE_BUDGET: ["budget_id", "limit_amount"],
    Intent.CANCEL_SUBSCRIPTION: ["resource_id"],
    Intent.GET_CARD: ["resource_id"],
    Intent.UPDATE_CARD_LIMIT: ["card_id", "spending_limit"],
    Intent.FREEZE_CARD: ["resource_id"],
    Intent.UNFREEZE_CARD: ["resource_id"],
    Intent.REPORT_CARD_LOST: ["resource_id"],
    Intent.COMPARE_WEALTH_PRODUCTS: ["product_ids"],
    Intent.ASSESS_RISK_PROFILE: ["answers"],
    Intent.SUBSCRIBE_WEALTH: ["account_id", "product_id", "amount"],
    Intent.REDEEM_WEALTH: ["account_id", "product_id", "amount"],
    Intent.CREATE_SAVINGS_POT: ["name", "target_amount", "target_date", "currency"],
    Intent.CONTRIBUTE_SAVINGS_POT: ["pot_id", "amount"],
}


class HybridRouter:
    """Use deterministic rules first and LLM classification only for unmatched text."""

    def __init__(
        self,
        rules: RuleRouter,
        provider: ModelProvider | None,
        *,
        confidence_threshold: float = 0.65,
    ) -> None:
        self._rules = rules
        self._provider = provider
        self._confidence_threshold = confidence_threshold

    async def route(self, text: str) -> IntentResult:
        deterministic = self._rules.route(text)
        if deterministic.route != Route.SAFE_FALLBACK:
            return deterministic
        if "instruction marker" in deterministic.reason:
            return deterministic
        if self._provider is None or not self._provider.available:
            return deterministic
        supported = ", ".join(intent.value for intent in Intent if intent != Intent.UNKNOWN)
        messages = [
            ConversationMessage(
                role=ConversationRole.SYSTEM,
                trust=TrustLabel.SYSTEM_POLICY,
                content=(
                    "你是银行助手的意图分类器。只输出一个 JSON 对象，字段必须严格为："
                    '{"intent":"枚举值","confidence":0到1,"reply":null或字符串}。'
                    "不要输出分析、Markdown 或额外字段。不得声称金融操作成功，"
                    "不得生成身份、授权、验证码、账户或金额。普通问候使用 GENERAL_CHAT；"
                    "普通问候的 reply 给出简短自然回复，银行任务的 reply 使用 null；"
                    f"支持的 intent: {supported}。"
                ),
            ),
            ConversationMessage(role=ConversationRole.USER, content=text),
        ]
        try:
            generated = await self._provider.generate_structured(
                messages=messages,
                output_model=LlmIntentDecision,
                temperature=0,
                max_tokens=256,
            )
        except ProviderError as exc:
            logger.warning(
                "LLM intent fallback failed provider=%s code=%s request_id=%s",
                exc.provider,
                exc.code,
                exc.request_id,
            )
            return deterministic
        decision = generated.output
        if decision.confidence < self._confidence_threshold or decision.intent == Intent.UNKNOWN:
            return deterministic
        return IntentResult(
            intent=decision.intent,
            complexity=1 if decision.intent == Intent.GENERAL_CHAT else 3,
            confidence=decision.confidence,
            route=(Route.RULE_DIRECT if decision.intent == Intent.GENERAL_CHAT else Route.PLANNER),
            reason=f"llm:{generated.provider}/{generated.model}",
            required_slots=_REQUIRED_SLOTS.get(decision.intent, []),
            reply=decision.reply,
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
            *request.conversation[-10:],
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
