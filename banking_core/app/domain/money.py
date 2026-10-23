from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from banking_core.app.domain.enums import Currency

MONEY_QUANTUM = Decimal("0.01")
MAX_MONEY = Decimal("9999999999999999.99")


def quantize_money(value: Decimal) -> Decimal:
    try:
        result = value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise ValueError("invalid monetary amount") from exc
    if not result.is_finite() or abs(result) > MAX_MONEY:
        raise ValueError("monetary amount is outside supported range")
    return result


def parse_money(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("binary floating-point money is not accepted")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid monetary amount") from exc
    return quantize_money(decimal_value)


MoneyDecimal = Annotated[Decimal, BeforeValidator(parse_money)]


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: Currency

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: Any) -> Decimal:
        return parse_money(value)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)
