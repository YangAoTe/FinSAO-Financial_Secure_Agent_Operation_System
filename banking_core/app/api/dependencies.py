from collections.abc import Generator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from banking_core.app.config import get_settings
from banking_core.app.persistence.database import get_session_factory
from banking_core.app.security.approvals import DatabaseTransferAuthorizationVerifier
from banking_core.app.security.transfer_authorization import TransferAuthorizationVerifier


def get_db_session() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session


def get_current_user_id() -> UUID:
    """Server-configured Phase 2 identity stub; it accepts no client identity input."""
    settings = get_settings()
    user_id = settings.development_user_id
    if settings.app_env != "development" or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="identity not configured"
        )
    return user_id


def get_transfer_verifier(
    session: Annotated[Session, Depends(get_db_session)],
) -> TransferAuthorizationVerifier:
    return DatabaseTransferAuthorizationVerifier(session)
