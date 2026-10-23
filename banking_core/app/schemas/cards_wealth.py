from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from banking_core.app.domain.enums import CardStatus, Currency, RiskTier, WealthOrderType
from banking_core.app.domain.money import MoneyDecimal


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CardResponse(OrmResponse):
    id: UUID
    account_id: UUID
    label: str
    last_four: str
    status: CardStatus
    spending_limit: Decimal


class CardLimitRequest(BaseModel):
    spending_limit: MoneyDecimal = Field(gt=0, max_digits=18, decimal_places=2)
    authorization_ref: str = Field(min_length=1)


class AuthorizedOperationRequest(BaseModel):
    authorization_ref: str = Field(min_length=1)


class WealthProductResponse(OrmResponse):
    id: UUID
    code: str
    name: str
    product_type: str
    risk_tier: RiskTier
    minimum_amount: Decimal
    currency: Currency
    supports_redemption: bool


class CompareProductsRequest(BaseModel):
    product_ids: list[UUID] = Field(min_length=2, max_length=10)


class RiskAssessmentRequest(BaseModel):
    answers: list[int] = Field(min_length=5, max_length=5)


class RiskAssessmentResponse(OrmResponse):
    id: UUID
    score: int
    risk_tier: RiskTier


class HoldingResponse(OrmResponse):
    id: UUID
    product_id: UUID
    amount: Decimal
    currency: Currency


class WealthOrderRequest(BaseModel):
    account_id: UUID
    product_id: UUID
    amount: MoneyDecimal = Field(gt=0, max_digits=18, decimal_places=2)
    idempotency_key: str = Field(min_length=1, max_length=120)


class WealthOrderResponse(OrmResponse):
    id: UUID
    account_id: UUID
    product_id: UUID
    amount: Decimal
    currency: Currency
    status: str
    order_type: WealthOrderType
    transaction_id: UUID | None
