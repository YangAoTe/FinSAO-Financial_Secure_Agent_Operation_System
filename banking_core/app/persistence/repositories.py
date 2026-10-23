from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from banking_core.app.domain.entities import Account, Beneficiary, Transaction, User


class UserRepository(Protocol):
    def get(self, user_id: UUID) -> User | None: ...


class AccountRepository(Protocol):
    def get(self, account_id: UUID) -> Account | None: ...

    def list_for_user(self, user_id: UUID) -> Sequence[Account]: ...


class BeneficiaryRepository(Protocol):
    def list_for_user(self, user_id: UUID) -> Sequence[Beneficiary]: ...


class TransactionRepository(Protocol):
    def list_for_account(self, account_id: UUID) -> Sequence[Transaction]: ...
