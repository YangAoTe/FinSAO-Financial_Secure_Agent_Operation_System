from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from banking_core.app.domain.enums import (
    AccountStatus,
    CardStatus,
    Currency,
    RiskTier,
    TransactionStatus,
    TransferStatus,
)
from banking_core.app.domain.money import MoneyDecimal, quantize_money


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class User(DomainModel):
    id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    risk_tier: RiskTier
    created_at: datetime


class Account(DomainModel):
    id: UUID
    user_id: UUID | None
    account_number: str = Field(min_length=6, max_length=34)
    name: str = Field(min_length=1, max_length=120)
    currency: Currency
    status: AccountStatus
    balance: MoneyDecimal
    is_system: bool = False

    @field_validator("balance", mode="before")
    @classmethod
    def money_precision(cls, value: Any) -> Decimal:
        if isinstance(value, float):
            raise ValueError("binary floating-point money is not accepted")
        return quantize_money(Decimal(str(value)))

    @model_validator(mode="after")
    def user_or_system(self) -> "Account":
        if self.is_system == (self.user_id is not None):
            raise ValueError("system accounts must not have a user; customer accounts must")
        if not self.is_system and self.balance < 0:
            raise ValueError("customer account balance cannot be negative")
        return self


class Beneficiary(DomainModel):
    id: UUID
    user_id: UUID
    name: str = Field(min_length=1, max_length=120)
    destination_account_id: UUID
    nickname: str | None = Field(default=None, max_length=80)


class Transaction(DomainModel):
    id: UUID
    reference: str = Field(min_length=1, max_length=80)
    status: TransactionStatus
    amount: MoneyDecimal
    currency: Currency
    description: str
    posted_at: datetime | None

    @field_validator("amount", mode="before")
    @classmethod
    def positive_amount(cls, value: Any) -> Decimal:
        amount = quantize_money(Decimal(str(value)))
        if amount <= 0:
            raise ValueError("transaction amount must be positive")
        return amount


class LedgerEntry(DomainModel):
    id: UUID
    transaction_id: UUID
    account_id: UUID
    debit: MoneyDecimal = Decimal("0.00")
    credit: MoneyDecimal = Decimal("0.00")
    currency: Currency
    created_at: datetime

    @model_validator(mode="after")
    def exactly_one_side(self) -> "LedgerEntry":
        debit = quantize_money(self.debit)
        credit = quantize_money(self.credit)
        if (debit > 0) == (credit > 0):
            raise ValueError("exactly one of debit or credit must be positive")
        return self


class TransferDraft(DomainModel):
    id: UUID
    user_id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: MoneyDecimal
    currency: Currency
    status: TransferStatus
    idempotency_key: str | None = None
    expires_at: datetime

    @field_validator("amount", mode="before")
    @classmethod
    def positive_amount(cls, value: Any) -> Decimal:
        amount = quantize_money(Decimal(str(value)))
        if amount <= 0:
            raise ValueError("transfer amount must be positive")
        return amount


class Budget(DomainModel):
    id: UUID
    user_id: UUID
    category: str
    month: date
    limit_amount: MoneyDecimal
    currency: Currency

    @field_validator("limit_amount")
    @classmethod
    def positive_limit(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("budget limit must be positive")
        return value


class Subscription(DomainModel):
    id: UUID
    user_id: UUID
    merchant_name: str
    amount: MoneyDecimal
    currency: Currency
    next_billing_date: date
    active: bool

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("subscription amount must be positive")
        return value


class Card(DomainModel):
    id: UUID
    account_id: UUID
    label: str
    last_four: str = Field(pattern=r"^\d{4}$")
    status: CardStatus
    spending_limit: MoneyDecimal

    @field_validator("spending_limit")
    @classmethod
    def positive_limit(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("card limit must be positive")
        return value


class WealthProduct(DomainModel):
    id: UUID
    code: str
    name: str
    product_type: str
    risk_tier: RiskTier
    minimum_amount: MoneyDecimal
    currency: Currency

    @field_validator("minimum_amount")
    @classmethod
    def positive_minimum(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("wealth minimum must be positive")
        return value


class AuditEvent(DomainModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    trace_id: str
    outcome: str
    details: dict[str, Any]
    occurred_at: datetime
