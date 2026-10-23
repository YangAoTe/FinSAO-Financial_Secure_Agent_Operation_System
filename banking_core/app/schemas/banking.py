from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from banking_core.app.domain.enums import AccountStatus, Currency, TransactionStatus, TransferStatus
from banking_core.app.domain.money import MoneyDecimal


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountResponse(ApiModel):
    id: UUID
    account_number: str
    name: str
    currency: Currency
    status: AccountStatus


class BalanceResponse(ApiModel):
    account_id: UUID
    balance: Decimal
    currency: Currency


class TransactionResponse(ApiModel):
    id: UUID
    reference: str
    status: TransactionStatus
    amount: Decimal
    currency: Currency
    description: str
    category: str | None
    posted_at: datetime | None


class TransactionPage(ApiModel):
    items: list[TransactionResponse]
    limit: int
    offset: int


class BeneficiaryResponse(ApiModel):
    id: UUID
    name: str
    nickname: str | None
    destination_account_id: UUID


class BeneficiaryResolutionResponse(ApiModel):
    status: Literal["NOT_FOUND", "RESOLVED", "AMBIGUOUS"]
    matches: list[BeneficiaryResponse]


class TransferDraftRequest(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount: MoneyDecimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency


class TransferDraftResponse(ApiModel):
    id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    currency: Currency
    status: TransferStatus
    expires_at: datetime
    transaction_id: UUID | None


class CommitTransferRequest(BaseModel):
    authorization_ref: str = Field(min_length=1, max_length=200)


class TransferReceipt(ApiModel):
    transaction_id: UUID
    reference: str
    status: TransactionStatus
    amount: Decimal
    currency: Currency


class ErrorResponse(BaseModel):
    code: str
    message: str
