from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from banking_core.app.domain.enums import AccountStatus
from banking_core.app.persistence.models import AccountModel, BeneficiaryModel
from banking_core.app.services.errors import NotFoundError, ValidationError


@dataclass(frozen=True)
class BeneficiaryRecord:
    id: UUID
    name: str
    nickname: str | None
    destination_account_id: UUID
    destination_account_number: str


@dataclass(frozen=True)
class BeneficiaryResolution:
    status: str
    matches: tuple[BeneficiaryRecord, ...]


class BeneficiaryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _record(item: BeneficiaryModel, account_number: str) -> BeneficiaryRecord:
        return BeneficiaryRecord(
            id=item.id,
            name=item.name,
            nickname=item.nickname,
            destination_account_id=item.destination_account_id,
            destination_account_number=account_number,
        )

    def list_beneficiaries(self, user_id: UUID) -> list[BeneficiaryRecord]:
        rows = self.session.execute(
            select(BeneficiaryModel, AccountModel.account_number)
            .join(AccountModel, AccountModel.id == BeneficiaryModel.destination_account_id)
            .where(BeneficiaryModel.user_id == user_id)
            .order_by(BeneficiaryModel.name)
        )
        return [self._record(item, account_number) for item, account_number in rows]

    def resolve_beneficiary(self, user_id: UUID, query: str) -> BeneficiaryResolution:
        normalized = query.strip().lower()
        rows = self.session.execute(
            select(BeneficiaryModel, AccountModel.account_number)
            .join(AccountModel, AccountModel.id == BeneficiaryModel.destination_account_id)
            .where(
                BeneficiaryModel.user_id == user_id,
                or_(
                    func.lower(BeneficiaryModel.name) == normalized,
                    func.lower(BeneficiaryModel.nickname) == normalized,
                ),
            )
        )
        matches = tuple(self._record(item, account_number) for item, account_number in rows)
        status = "NOT_FOUND" if not matches else "RESOLVED" if len(matches) == 1 else "AMBIGUOUS"
        return BeneficiaryResolution(status=status, matches=matches)

    def save_beneficiary(
        self,
        user_id: UUID,
        *,
        name: str,
        account_number: str,
        nickname: str | None = None,
    ) -> BeneficiaryRecord:
        clean_name = name.strip()
        clean_number = account_number.strip()
        clean_nickname = nickname.strip() if nickname and nickname.strip() else None
        if not clean_name or not clean_number:
            raise ValidationError("beneficiary name and account number are required")
        destination = self.session.scalar(
            select(AccountModel).where(AccountModel.account_number == clean_number)
        )
        if destination is None:
            raise NotFoundError("destination account not found")
        if destination.status != AccountStatus.ACTIVE:
            raise ValidationError("destination account is not active")
        item = self.session.scalar(
            select(BeneficiaryModel).where(
                BeneficiaryModel.user_id == user_id,
                BeneficiaryModel.destination_account_id == destination.id,
            )
        )
        if item is None:
            item = BeneficiaryModel(
                user_id=user_id,
                name=clean_name,
                nickname=clean_nickname,
                destination_account_id=destination.id,
            )
            self.session.add(item)
        else:
            item.name = clean_name
            item.nickname = clean_nickname
        self.session.commit()
        self.session.refresh(item)
        return self._record(item, destination.account_number)
