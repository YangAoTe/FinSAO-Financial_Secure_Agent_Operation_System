from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from banking_core.app.config import get_settings
from banking_core.app.domain.enums import Currency, TransferStatus
from banking_core.app.main import app
from banking_core.app.persistence.models import TransferDraftModel
from banking_core.app.services.errors import ConflictError
from banking_core.app.services.transfers import transition


def draft(status: TransferStatus) -> TransferDraftModel:
    return TransferDraftModel(
        id=uuid4(),
        user_id=uuid4(),
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        amount=Decimal("10.00"),
        currency=Currency.CNY,
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def test_transfer_state_transition_policy() -> None:
    item = draft(TransferStatus.DRAFT)
    transition(item, TransferStatus.PENDING_AUTHORIZATION)
    assert item.status == TransferStatus.PENDING_AUTHORIZATION
    with pytest.raises(ConflictError):
        transition(item, TransferStatus.COMPLETED)


def test_runtime_identity_cannot_be_supplied_by_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/accounts", headers={"X-User-Id": str(uuid4())})
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()


def test_banking_core_rejects_direct_requests_without_service_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEVELOPMENT_USER_ID", str(uuid4()))
    monkeypatch.setenv("BANKING_SERVICE_TOKEN", "core-test-secret")
    get_settings.cache_clear()
    try:
        missing = TestClient(app).get("/accounts")
        forged = TestClient(app).get(
            "/accounts", headers={"Authorization": "Bearer wrong-secret"}
        )
        assert missing.status_code == 401
        assert forged.status_code == 401
    finally:
        get_settings.cache_clear()
