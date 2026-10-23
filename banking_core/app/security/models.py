from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from banking_core.app.domain.enums import Currency, RiskTier


class PolicyStatus(StrEnum):
    ALLOWED = "ALLOWED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    REQUIRES_MFA = "REQUIRES_MFA"
    DENIED = "DENIED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class PolicyDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    action: str
    risk_tier: RiskTier
    status: PolicyStatus
    reason: str


class AuthorizationRequest(BaseModel):
    actor_id: UUID
    operation_id: UUID
    operation_type: str
    target_account_id: UUID | None = None
    recipient_id: UUID | None = None
    amount: Decimal | None = None
    currency: Currency | None = None
    payload: dict[str, Any]


class ApprovalRecord(BaseModel):
    id: UUID
    request: AuthorizationRequest
    payload_hash: str
    risk_tier: RiskTier
    status: ApprovalStatus
    expires_at: datetime


class AuthorizationGrant(BaseModel):
    id: UUID
    approval_id: UUID
    operation_id: UUID
    actor_id: UUID
    expires_at: datetime
    consumed_at: datetime | None = None


class SafetyLockState(BaseModel):
    actor_id: UUID
    locked_until: datetime | None
    failure_count: int
