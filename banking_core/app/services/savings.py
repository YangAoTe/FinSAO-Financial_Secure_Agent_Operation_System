from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from banking_core.app.domain.enums import Currency
from banking_core.app.persistence.models import (
    SavingsContributionModel,
    SavingsPotModel,
)
from banking_core.app.services.errors import ConflictError, ForbiddenError, NotFoundError


class SavingsPotService:
    """Virtual goal allocations; contributions never move account or ledger balances."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, user_id: UUID) -> list[SavingsPotModel]:
        return list(
            self.session.scalars(
                select(SavingsPotModel)
                .where(SavingsPotModel.user_id == user_id)
                .order_by(SavingsPotModel.created_at, SavingsPotModel.id)
            )
        )

    def get(self, pot_id: UUID, user_id: UUID) -> SavingsPotModel:
        pot = self.session.get(SavingsPotModel, pot_id)
        if pot is None:
            raise NotFoundError("savings pot not found")
        if pot.user_id != user_id:
            raise ForbiddenError("savings pot belongs to another user")
        return pot

    def create(
        self,
        user_id: UUID,
        *,
        name: str,
        target_amount: Decimal,
        currency: Currency,
        target_date: date,
        idempotency_key: str,
    ) -> SavingsPotModel:
        existing = self.session.scalar(
            select(SavingsPotModel).where(
                SavingsPotModel.user_id == user_id,
                SavingsPotModel.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.name != name
                or existing.target_amount != target_amount
                or existing.currency != currency
                or existing.target_date != target_date
            ):
                raise ConflictError("idempotency key reused with different savings pot")
            return existing
        pot = SavingsPotModel(
            id=uuid4(),
            user_id=user_id,
            name=name,
            target_amount=target_amount,
            saved_amount=Decimal("0.00"),
            currency=currency,
            target_date=target_date,
            status="ACTIVE",
            allocation_mode="VIRTUAL_ALLOCATION",
            idempotency_key=idempotency_key,
        )
        self.session.add(pot)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return self.create(
                user_id,
                name=name,
                target_amount=target_amount,
                currency=currency,
                target_date=target_date,
                idempotency_key=idempotency_key,
            )
        self.session.refresh(pot)
        return pot

    def update(
        self,
        pot_id: UUID,
        user_id: UUID,
        *,
        name: str | None,
        target_amount: Decimal | None,
        target_date: date | None,
    ) -> SavingsPotModel:
        pot = self.get(pot_id, user_id)
        if name is not None:
            pot.name = name
        if target_amount is not None:
            pot.target_amount = target_amount
        if target_date is not None:
            pot.target_date = target_date
        pot.status = "COMPLETED" if pot.saved_amount >= pot.target_amount else "ACTIVE"
        self.session.commit()
        self.session.refresh(pot)
        return pot

    def delete(self, pot_id: UUID, user_id: UUID) -> None:
        self.get(pot_id, user_id)
        self.session.execute(
            delete(SavingsContributionModel).where(SavingsContributionModel.pot_id == pot_id)
        )
        self.session.execute(delete(SavingsPotModel).where(SavingsPotModel.id == pot_id))
        self.session.commit()

    def list_contributions(self, pot_id: UUID, user_id: UUID) -> Sequence[SavingsContributionModel]:
        self.get(pot_id, user_id)
        return list(
            self.session.scalars(
                select(SavingsContributionModel)
                .where(SavingsContributionModel.pot_id == pot_id)
                .order_by(SavingsContributionModel.created_at, SavingsContributionModel.id)
            )
        )

    def contribute(
        self,
        pot_id: UUID,
        user_id: UUID,
        *,
        amount: Decimal,
        note: str | None,
        idempotency_key: str,
    ) -> SavingsContributionModel:
        existing = self.session.scalar(
            select(SavingsContributionModel).where(
                SavingsContributionModel.user_id == user_id,
                SavingsContributionModel.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.pot_id != pot_id or existing.amount != amount or existing.note != note:
                raise ConflictError("idempotency key reused with different contribution")
            return existing
        if self.session.in_transaction():
            self.session.rollback()
        with self.session.begin():
            pot = self.session.scalar(
                select(SavingsPotModel).where(SavingsPotModel.id == pot_id).with_for_update()
            )
            if pot is None:
                raise NotFoundError("savings pot not found")
            if pot.user_id != user_id:
                raise ForbiddenError("savings pot belongs to another user")
            item = SavingsContributionModel(
                id=uuid4(),
                pot_id=pot_id,
                user_id=user_id,
                amount=amount,
                note=note,
                idempotency_key=idempotency_key,
            )
            self.session.add(item)
            pot.saved_amount += amount
            pot.status = "COMPLETED" if pot.saved_amount >= pot.target_amount else "ACTIVE"
        self.session.refresh(item)
        return item
