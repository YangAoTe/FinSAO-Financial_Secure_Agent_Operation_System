from typing import Protocol
from uuid import UUID

from banking_core.app.persistence.models import TransferDraftModel


class TransferAuthorizationVerifier(Protocol):
    def verify(self, draft: TransferDraftModel, actor_id: UUID, authorization_ref: str) -> bool: ...


class DenyAllTransferAuthorizationVerifier:
    def verify(self, draft: TransferDraftModel, actor_id: UUID, authorization_ref: str) -> bool:
        return False


class DevelopmentTransferAuthorizationVerifier:
    """Explicit test-only verifier; never wired into the runtime application."""

    def __init__(self, allowed: set[tuple[UUID, UUID, str]]) -> None:
        self.allowed = allowed

    def verify(self, draft: TransferDraftModel, actor_id: UUID, authorization_ref: str) -> bool:
        return (draft.id, actor_id, authorization_ref) in self.allowed
