from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from banking_core.app.config import get_settings
from banking_core.app.persistence.database import get_session_factory
from banking_core.app.persistence.models import AuditEventModel
from banking_core.app.services.errors import BankingError


async def banking_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, BankingError)
    _audit_failure(request, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    _audit_failure(request, "VALIDATION_ERROR")
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "request validation failed"},
    )


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    _audit_failure(request, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "HTTP_ERROR", "message": str(exc.detail)},
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del exc
    _audit_failure(request, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "internal banking service error"},
    )


def _audit_failure(request: Request, code: str) -> None:
    settings = get_settings()
    # With no authenticated development identity there is no actor to audit.
    # This also keeps the fail-closed identity path independent of DB health.
    if settings.development_user_id is None:
        return
    try:
        with get_session_factory()() as session, session.begin():
            session.add(
                AuditEventModel(
                    id=uuid4(),
                    actor_user_id=settings.development_user_id,
                    action=f"{request.method} {request.url.path}",
                    resource_type="http_request",
                    resource_id=None,
                    trace_id=str(getattr(request.state, "trace_id", uuid4())),
                    outcome="REJECTED",
                    details={"failure_code": code},
                )
            )
    except SQLAlchemyError:
        # Never replace the original deterministic error with an audit outage.
        return
