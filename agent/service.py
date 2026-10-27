"""Single-turn safe Agent service; durable approval/resume belongs to P3."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Protocol
from uuid import uuid4

from agent.capabilities import CapabilityBroker
from agent.context import SlotState, SlotTracker
from agent.contracts import (
    AgentError,
    AgentRequest,
    AgentResponse,
    AgentResponseStatus,
    TaskPlan,
    TrustedAgentContext,
)
from agent.planning import PlanValidationError, PlanVerifier
from agent.responses import SafeResponseGenerator
from agent.routing import Intent, IntentResult, Route
from agent_tools.contracts import ExecutionContext, ToolResult, ToolResultStatus


class Gateway(Protocol):
    async def execute(
        self, *, tool_name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult[Any]: ...


class Router(Protocol):
    def route(self, text: str) -> IntentResult | Awaitable[IntentResult]: ...


class Planner(Protocol):
    def create(
        self,
        intent: IntentResult,
        slots: SlotState,
        *,
        system_idempotency_key: str | None = None,
        request: AgentRequest | None = None,
        allowed_tools: list[dict[str, object]] | None = None,
    ) -> TaskPlan | Awaitable[TaskPlan]: ...


class AgentService:
    def __init__(
        self,
        *,
        router: Router,
        slots: SlotTracker,
        planner: Planner,
        verifier: PlanVerifier,
        capabilities: CapabilityBroker,
        gateway: Gateway,
        responses: SafeResponseGenerator | None = None,
    ) -> None:
        self._router = router
        self._slots = slots
        self._planner = planner
        self._verifier = verifier
        self._capabilities = capabilities
        self._gateway = gateway
        self._responses = responses or SafeResponseGenerator()

    async def handle(self, request: AgentRequest, context: TrustedAgentContext) -> AgentResponse:
        routed = self._router.route(request.message)
        intent = await routed if isinstance(routed, Awaitable) else routed
        if intent.intent == Intent.GENERAL_CHAT:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.COMPLETED,
                message=intent.reply or "你好，我可以帮助你处理银行账户与财务任务。",
            )
        if intent.route == Route.SAFE_FALLBACK:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.NEEDS_CLARIFICATION,
                message=(
                    intent.reply
                    or "当前请求无法安全识别，请明确说明账户、消费、预算、订阅、银行卡、"
                    "理财、储蓄罐或转账需求。"
                ),
            )
        slot_state = self._slots.extract(request.message, intent)
        if intent.route == Route.PLANNER and slot_state.missing:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.NEEDS_CLARIFICATION,
                message=f"请补充：{', '.join(slot_state.missing)}。",
            )
        if intent.route == Route.RULE_DIRECT and slot_state.missing:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.NEEDS_CLARIFICATION,
                message=f"请明确选择账户：{', '.join(slot_state.missing)}。",
            )
        try:
            actions = self._capabilities.allowed_actions(context=context, intent=intent.intent)
            planned = self._planner.create(
                intent,
                slot_state,
                system_idempotency_key=str(context.task_id),
                request=request,
                allowed_tools=self._capabilities.schemas(context=context, intent=intent.intent),
            )
            plan = await planned if isinstance(planned, Awaitable) else planned
            verified = self._verifier.verify(plan, actions)
        except PlanValidationError as exc:
            needs_input = exc.code in {"INFERRED_ARGUMENT", "MISSING_SLOTS"}
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=(
                    AgentResponseStatus.NEEDS_CLARIFICATION
                    if needs_input
                    else AgentResponseStatus.FAILED
                ),
                message=(
                    "计划包含未经用户确认的金融参数，请补充或明确相关信息。"
                    if needs_input
                    else "计划未通过确定性安全校验。"
                ),
                error=AgentError(code=exc.code, message=str(exc)),
            )
        execution_context = ExecutionContext(
            authenticated_user_id=context.authenticated_user_id,
            session_id=context.session_id,
            task_id=context.task_id,
            trace_id=context.trace_id,
            authorization_reference=context.authorization_reference,
        )
        last_result: ToolResult[Any] | None = None
        for step_id in verified.ordered_step_ids:
            step = next(item for item in plan.steps if item.step_id == step_id)
            if step.tool_call is None:
                continue
            last_result = await self._gateway.execute(
                tool_name=step.tool_call.tool_name,
                arguments=dict(step.tool_call.arguments),
                context=execution_context,
            )
            if last_result.status != ToolResultStatus.SUCCESS:
                break
        if last_result is None:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.FAILED,
                message="计划没有可执行步骤。",
                plan=plan,
                error=AgentError(code="NO_EXECUTABLE_STEP", message="empty execution"),
            )
        response_status = (
            AgentResponseStatus.COMPLETED
            if last_result.status == ToolResultStatus.SUCCESS
            else AgentResponseStatus.WAITING_APPROVAL
            if last_result.status
            in {ToolResultStatus.WAITING_APPROVAL, ToolResultStatus.MFA_REQUIRED}
            else AgentResponseStatus.FAILED
        )
        data = last_result.data.model_dump(mode="json") if last_result.data is not None else None
        return AgentResponse(
            request_id=request.request_id,
            session_id=request.session_id,
            task_id=context.task_id,
            status=response_status,
            message=(
                self._responses.compose(status=response_status, plan=plan, data=data)
            ),
            plan=plan,
            result=data,
            error=(
                None
                if response_status != AgentResponseStatus.FAILED
                else AgentError(
                    code=last_result.error_code or "TOOL_EXECUTION_FAILED",
                    message=last_result.message or "tool execution failed",
                )
            ),
        )


def new_trusted_context(user_id: Any, session_id: Any) -> TrustedAgentContext:
    """Development helper; production middleware must provide these trusted values."""
    return TrustedAgentContext(
        authenticated_user_id=user_id,
        session_id=session_id,
        task_id=uuid4(),
        trace_id=uuid4(),
    )
