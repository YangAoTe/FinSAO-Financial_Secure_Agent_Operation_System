from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from banking_core.app.domain.entities import Account, Budget, LedgerEntry, Transaction
from banking_core.app.domain.enums import AccountStatus, Currency, TransactionStatus
from banking_core.app.domain.money import Money


def test_money_uses_decimal_and_bankers_rounding() -> None:
    money = Money(amount="10.125", currency=Currency.CNY)
    assert money.amount == Decimal("10.12")
    assert isinstance(money.amount, Decimal)


def test_money_rejects_binary_float() -> None:
    with pytest.raises(ValidationError, match="binary floating-point"):
        Money(amount=0.1, currency=Currency.CNY)


def test_money_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        Money(amount="10.00", currency="GBP")


def test_customer_account_requires_owner() -> None:
    with pytest.raises(ValidationError, match="customer accounts must"):
        Account(
            id=uuid4(),
            user_id=None,
            account_number="DEMO000001",
            name="Checking",
            currency=Currency.CNY,
            status=AccountStatus.ACTIVE,
            balance="1.00",
        )


def test_transaction_amount_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="must be positive"):
        Transaction(
            id=uuid4(),
            reference="test",
            status=TransactionStatus.COMPLETED,
            amount="0.00",
            currency=Currency.CNY,
            description="invalid",
            posted_at=None,
        )


def test_all_domain_money_fields_reject_float() -> None:
    with pytest.raises(ValidationError, match="binary floating-point"):
        Budget(
            id=uuid4(),
            user_id=uuid4(),
            category="HOUSEHOLD",
            month=datetime.now(UTC).date(),
            limit_amount=10.1,
            currency=Currency.CNY,
        )


def test_ledger_entry_has_exactly_one_positive_side() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        LedgerEntry(
            id=uuid4(),
            transaction_id=uuid4(),
            account_id=uuid4(),
            debit=Decimal("1.00"),
            credit=Decimal("1.00"),
            currency=Currency.CNY,
            created_at=datetime.now(UTC),
        )
