import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from agent_tools.client import BankingClientError, UnknownMutationOutcome
from agent_tools.contracts import ExecutionContext, ToolResult, ToolResultStatus
from agent_tools.registry import ToolRegistry

AuditSink = Callable[[ExecutionContext, str, ToolResultStatus, str | None], None]


def logging_audit_sink(
    context: ExecutionContext, name: str, status: ToolResultStatus, code: str | None
) -> None:
    logging.getLogger("agent_tools.audit").info(
        "tool_call",
        extra={
            "actor_id": str(context.authenticated_user_id),
            "trace_id": str(context.trace_id),
            "tool_name": name,
            "result_status": status.value,
            "error_code": code,
        },
    )


class ToolGateway:
    def __init__(self, registry: ToolRegistry, audit_sink: AuditSink | None = None) -> None:
        self.registry = registry
        self.audit_sink = audit_sink or logging_audit_sink

    async def execute(
        self, *, tool_name: str, arguments: dict[str, Any], context: ExecutionContext
    ) -> ToolResult[Any]:
        tool = self.registry.get(tool_name)
        if tool is None:
            return self._result(
                context,
                tool_name,
                ToolResultStatus.VALIDATION_ERROR,
                "UNKNOWN_TOOL",
                "unknown tool",
            )
        if not isinstance(context, ExecutionContext):
            return self._result(
                context,
                tool_name,
                ToolResultStatus.DENIED,
                "UNTRUSTED_CONTEXT",
                "trusted context required",
            )
        try:
            typed_input = tool.input_model.model_validate(arguments)
        except ValidationError:
            return self._result(
                context,
                tool_name,
                ToolResultStatus.VALIDATION_ERROR,
                "INVALID_ARGUMENTS",
                "tool arguments are invalid",
            )
        try:
            raw_output = await tool.execute(typed_input, context)
            output = tool.output_model.model_validate(raw_output)
            output_status = str(getattr(output, "status", ""))
            result_status = (
                ToolResultStatus.WAITING_APPROVAL
                if output_status
                in {
                    "PENDING_AUTHORIZATION",
                    "TransferStatus.PENDING_AUTHORIZATION",
                }
                else ToolResultStatus.SUCCESS
            )
            result: ToolResult[Any] = ToolResult(status=result_status, data=output)
        except ValidationError:
            result = ToolResult(
                status=ToolResultStatus.EXECUTION_ERROR,
                error_code="INVALID_OUTPUT",
                message="tool produced invalid output",
            )
        except UnknownMutationOutcome as exc:
            result = ToolResult(
                status=ToolResultStatus.EXECUTION_ERROR, error_code=exc.code, message=exc.message
            )
        except BankingClientError as exc:
            status = (
                ToolResultStatus.DENIED
                if exc.status_code in {401, 403}
                else ToolResultStatus.EXECUTION_ERROR
            )
            if exc.code == "AUTHORIZATION_REQUIRED":
                status = ToolResultStatus.WAITING_APPROVAL
            elif exc.code == "MFA_REQUIRED":
                status = ToolResultStatus.MFA_REQUIRED
            result = ToolResult(status=status, error_code=exc.code, message=exc.message)
        except Exception:
            result = ToolResult(
                status=ToolResultStatus.EXECUTION_ERROR,
                error_code="EXECUTION_ERROR",
                message="tool execution failed",
            )
        self.audit_sink(context, tool_name, result.status, result.error_code)
        return result

    def _result(
        self,
        context: ExecutionContext,
        name: str,
        status: ToolResultStatus,
        code: str,
        message: str,
    ) -> ToolResult[Any]:
        self.audit_sink(context, name, status, code)
        return ToolResult(status=status, error_code=code, message=message)
