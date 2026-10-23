from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from banking_core.app.domain.enums import Currency
from banking_core.app.persistence.models import LedgerEntryModel
from banking_core.app.services.errors import ConflictError


class LedgerService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def post_transfer(
        self,
        *,
        transaction_id: UUID,
        source_account_id: UUID,
        destination_account_id: UUID,
        amount: Decimal,
        currency: Currency,
    ) -> tuple[LedgerEntryModel, LedgerEntryModel]:
        debit = LedgerEntryModel(
            id=uuid4(),
            transaction_id=transaction_id,
            account_id=destination_account_id,
            debit=amount,
            credit=Decimal("0.00"),
            currency=currency,
        )
        credit = LedgerEntryModel(
            id=uuid4(),
            transaction_id=transaction_id,
            account_id=source_account_id,
            debit=Decimal("0.00"),
            credit=amount,
            currency=currency,
        )
        self.session.add_all([debit, credit])
        return debit, credit

    def verify_transaction_balanced(self, transaction_id: UUID) -> None:
        debit, credit = self.session.execute(
            select(
                func.coalesce(func.sum(LedgerEntryModel.debit), 0),
                func.coalesce(func.sum(LedgerEntryModel.credit), 0),
            ).where(LedgerEntryModel.transaction_id == transaction_id)
        ).one()
        if Decimal(debit) != Decimal(credit):
            raise ConflictError("ledger transaction is not balanced")
