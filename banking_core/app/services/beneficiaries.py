from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from banking_core.app.persistence.models import BeneficiaryModel


@dataclass(frozen=True)
class BeneficiaryResolution:
    status: str
    matches: tuple[BeneficiaryModel, ...]


class BeneficiaryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_beneficiaries(self, user_id: UUID) -> list[BeneficiaryModel]:
        return list(
            self.session.scalars(
                select(BeneficiaryModel)
                .where(BeneficiaryModel.user_id == user_id)
                .order_by(BeneficiaryModel.name)
            )
        )

    def resolve_beneficiary(self, user_id: UUID, query: str) -> BeneficiaryResolution:
        normalized = query.strip().lower()
        matches = tuple(
            self.session.scalars(
                select(BeneficiaryModel).where(
                    BeneficiaryModel.user_id == user_id,
                    or_(
                        func.lower(BeneficiaryModel.name) == normalized,
                        func.lower(BeneficiaryModel.nickname) == normalized,
                    ),
                )
            )
        )
        status = "NOT_FOUND" if not matches else "RESOLVED" if len(matches) == 1 else "AMBIGUOUS"
        return BeneficiaryResolution(status=status, matches=matches)
