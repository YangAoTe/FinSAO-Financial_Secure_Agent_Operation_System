from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.orm import Session

from banking_core.app.domain.enums import RiskTier
from banking_core.app.security.approvals import MockMfaProvider
from banking_core.app.security.models import PolicyStatus
from banking_core.app.security.policy import PolicyEngine


class ScalarSession:
    def __init__(self, value: Decimal) -> None:
        self.value = value

    def scalar(self, statement: object) -> Decimal:
        return self.value


def engine_with_daily_total(total: str) -> PolicyEngine:
    return PolicyEngine(cast(Session, cast(Any, ScalarSession(Decimal(total)))))


def test_green_read_is_automatically_allowed() -> None:
    decision = engine_with_daily_total("0").evaluate("balance.query", uuid4(), {}, {})
    assert decision.risk_tier == RiskTier.GREEN
    assert decision.status == PolicyStatus.ALLOWED


def test_transfer_threshold_uses_cumulative_daily_amount() -> None:
    yellow = engine_with_daily_total("800.00").evaluate("transfer.commit", uuid4(), {}, {})
    red = engine_with_daily_total("1500.00").evaluate("transfer.commit", uuid4(), {}, {})
    split = engine_with_daily_total("1300.00").evaluate("transfer.commit", uuid4(), {}, {})
    assert yellow.status == PolicyStatus.REQUIRES_CONFIRMATION
    assert red.status == PolicyStatus.REQUIRES_MFA
    assert split.status == PolicyStatus.REQUIRES_MFA


def test_unknown_action_fails_closed() -> None:
    decision = engine_with_daily_total("0").evaluate("unknown", uuid4(), {}, {})
    assert decision.status == PolicyStatus.DENIED


def test_mock_mfa_hash_is_salted_and_deterministic() -> None:
    assert MockMfaProvider._hash("123456", "salt-a") == MockMfaProvider._hash("123456", "salt-a")
    assert MockMfaProvider._hash("123456", "salt-a") != MockMfaProvider._hash("123456", "salt-b")
