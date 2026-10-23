from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from banking_core.app.api.analytics import router as analytics_router
from banking_core.app.api.banking import router as banking_router
from banking_core.app.api.cards_wealth import router as cards_wealth_router
from banking_core.app.api.errors import (
    banking_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from banking_core.app.api.health import router as health_router
from banking_core.app.api.security import router as security_router
from banking_core.app.schemas.banking import ErrorResponse
from banking_core.app.services.errors import BankingError
from shared.tracing import bind_trace_id, reset_trace_id

app = FastAPI(
    title="Mock Banking Core",
    version="0.1.0",
    description="Deterministic banking backend foundation.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid banking operation"},
        401: {"model": ErrorResponse, "description": "Identity unavailable"},
        403: {"model": ErrorResponse, "description": "Forbidden or authorization required"},
        404: {"model": ErrorResponse, "description": "Resource not found"},
        409: {"model": ErrorResponse, "description": "State or idempotency conflict"},
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        500: {"model": ErrorResponse, "description": "Internal banking service error"},
    },
)
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(banking_router)
app.include_router(cards_wealth_router)
app.include_router(security_router)
app.add_exception_handler(BankingError, banking_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    supplied = request.headers.get("X-Trace-Id")
    try:
        trace_id = UUID(supplied) if supplied else uuid4()
    except ValueError:
        trace_id = uuid4()
    request.state.trace_id = trace_id
    token = bind_trace_id(trace_id)
    try:
        response = await call_next(request)
    finally:
        reset_trace_id(token)
    response.headers["X-Trace-Id"] = str(trace_id)
    return response
