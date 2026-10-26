"""Single-turn safe Agent service; durable approval/resume belongs to P3."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import uuid4

from agent.capabilities import CapabilityBroker
from agent.context import SlotTracker
from agent.contracts import (
    AgentError,
    AgentRequest,
    AgentResponse,
    AgentResponseStatus,
    TrustedAgentContext,
)
from agent.planning import BaselinePlanner, PlanValidationError, PlanVerifier
from agent.routing import Route, RuleRouter
from agent_tools.contracts import ExecutionContext, ToolResult, ToolResultStatus


class Gateway(Protocol):
    async def execute(
        self, *, tool_name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult[Any]: ...


class AgentService:
    def __init__(
        self,
        *,
        router: RuleRouter,
        slots: SlotTracker,
        planner: BaselinePlanner,
        verifier: PlanVerifier,
        capabilities: CapabilityBroker,
        gateway: Gateway,
    ) -> None:
        self._router = router
        self._slots = slots
        self._planner = planner
        self._verifier = verifier
        self._capabilities = capabilities
        self._gateway = gateway

    async def handle(
        self, request: AgentRequest, context: TrustedAgentContext
    ) -> AgentResponse:
        intent = self._router.route(request.message)
        if intent.route == Route.SAFE_FALLBACK:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.NEEDS_CLARIFICATION,
                message="当前请求超出已验证能力，请改为账户、余额、流水或转账草稿请求。",
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
            plan = self._planner.create(
                intent, slot_state, system_idempotency_key=str(context.task_id)
            )
            actions = self._capabilities.allowed_actions(context=context, intent=intent.intent)
            verified = self._verifier.verify(plan, actions)
        except PlanValidationError as exc:
            return AgentResponse(
                request_id=request.request_id,
                session_id=request.session_id,
                task_id=context.task_id,
                status=AgentResponseStatus.FAILED,
                message="计划未通过确定性安全校验。",
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
                "操作结果来自 Banking Core。"
                if response_status == AgentResponseStatus.COMPLETED
                else "草稿已创建，必须完成审批后才能提交。"
                if response_status == AgentResponseStatus.WAITING_APPROVAL
                else "Banking Core 未确认操作成功。"
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
