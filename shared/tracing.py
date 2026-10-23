from contextvars import ContextVar, Token
from uuid import UUID, uuid4

_request_trace_id: ContextVar[UUID | None] = ContextVar("request_trace_id", default=None)


def bind_trace_id(trace_id: UUID) -> Token[UUID | None]:
    return _request_trace_id.set(trace_id)


def reset_trace_id(token: Token[UUID | None]) -> None:
    _request_trace_id.reset(token)


def current_trace_id() -> str:
    """Return the trusted request trace, or a safe trace for non-HTTP callers."""
    return str(_request_trace_id.get() or uuid4())
