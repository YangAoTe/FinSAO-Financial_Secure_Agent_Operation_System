from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from banking_core.app.persistence.models import AccountModel, LedgerEntryModel, TransactionModel
from banking_core.app.services.errors import ForbiddenError, NotFoundError


@dataclass(frozen=True)
class TransactionFilters:
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 50
    offset: int = 0
    category: str | None = None
    merchant: str | None = None
    minimum_amount: Decimal | None = None
    maximum_amount: Decimal | None = None


class AccountService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_accounts(self, user_id: UUID) -> list[AccountModel]:
        return list(
            self.session.scalars(
                select(AccountModel)
                .where(AccountModel.user_id == user_id)
                .order_by(AccountModel.account_number)
            )
        )

    def get_account(self, account_id: UUID, user_id: UUID) -> AccountModel:
        account = self.session.get(AccountModel, account_id)
        if account is None or account.is_system:
            raise NotFoundError("account not found")
        if account.user_id != user_id:
            raise ForbiddenError("account belongs to another user")
        return account

    def get_balance(self, account_id: UUID, user_id: UUID) -> AccountModel:
        return self.get_account(account_id, user_id)

    def get_transactions(
        self, account_id: UUID, user_id: UUID, filters: TransactionFilters
    ) -> list[TransactionModel]:
        self.get_account(account_id, user_id)
        query = (
            select(TransactionModel)
            .join(LedgerEntryModel, LedgerEntryModel.transaction_id == TransactionModel.id)
            .where(LedgerEntryModel.account_id == account_id)
        )
        if filters.start is not None:
            query = query.where(TransactionModel.posted_at >= filters.start)
        if filters.end is not None:
            query = query.where(TransactionModel.posted_at < filters.end)
        if filters.category is not None:
            query = query.where(TransactionModel.category == filters.category)
        if filters.merchant is not None:
            query = query.where(TransactionModel.description.ilike(f"%{filters.merchant}%"))
        if filters.minimum_amount is not None:
            query = query.where(TransactionModel.amount >= filters.minimum_amount)
        if filters.maximum_amount is not None:
            query = query.where(TransactionModel.amount <= filters.maximum_amount)
        query = (
            query.order_by(TransactionModel.posted_at.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )
        return list(self.session.scalars(query))
