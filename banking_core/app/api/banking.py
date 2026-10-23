from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from banking_core.app.api.dependencies import (
    get_current_user_id,
    get_db_session,
    get_transfer_verifier,
)
from banking_core.app.schemas.banking import (
    AccountResponse,
    BalanceResponse,
    BeneficiaryResolutionResponse,
    BeneficiaryResponse,
    CommitTransferRequest,
    TransactionPage,
    TransferDraftRequest,
    TransferDraftResponse,
    TransferReceipt,
)
from banking_core.app.security.transfer_authorization import TransferAuthorizationVerifier
from banking_core.app.services.accounts import AccountService, TransactionFilters
from banking_core.app.services.beneficiaries import BeneficiaryService
from banking_core.app.services.transfers import TransferService

router = APIRouter()
Db = Annotated[Session, Depends(get_db_session)]
Actor = Annotated[UUID, Depends(get_current_user_id)]
Verifier = Annotated[TransferAuthorizationVerifier, Depends(get_transfer_verifier)]


@router.get("/accounts", response_model=list[AccountResponse], tags=["accounts"])
def get_accounts(session: Db, actor_id: Actor) -> list[AccountResponse]:
    return [
        AccountResponse.model_validate(item)
        for item in AccountService(session).get_accounts(actor_id)
    ]


@router.get("/accounts/{account_id}/balance", response_model=BalanceResponse, tags=["accounts"])
def get_balance(account_id: UUID, session: Db, actor_id: Actor) -> BalanceResponse:
    account = AccountService(session).get_balance(account_id, actor_id)
    return BalanceResponse(
        account_id=account.id, balance=account.balance, currency=account.currency
    )


@router.get(
    "/accounts/{account_id}/transactions", response_model=TransactionPage, tags=["accounts"]
)
def get_transactions(
    account_id: UUID,
    session: Db,
    actor_id: Actor,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    category: str | None = None,
    merchant: str | None = None,
    minimum_amount: Decimal | None = None,
    maximum_amount: Decimal | None = None,
) -> TransactionPage:
    items = AccountService(session).get_transactions(
        account_id,
        actor_id,
        TransactionFilters(
            start=start,
            end=end,
            limit=limit,
            offset=offset,
            category=category,
            merchant=merchant,
            minimum_amount=minimum_amount,
            maximum_amount=maximum_amount,
        ),
    )
    return TransactionPage(items=items, limit=limit, offset=offset)


@router.get("/beneficiaries", response_model=list[BeneficiaryResponse], tags=["beneficiaries"])
def list_beneficiaries(session: Db, actor_id: Actor) -> list[BeneficiaryResponse]:
    return [
        BeneficiaryResponse.model_validate(item)
        for item in BeneficiaryService(session).list_beneficiaries(actor_id)
    ]


@router.get(
    "/beneficiaries/resolve", response_model=BeneficiaryResolutionResponse, tags=["beneficiaries"]
)
def resolve_beneficiary(query: str, session: Db, actor_id: Actor) -> BeneficiaryResolutionResponse:
    result = BeneficiaryService(session).resolve_beneficiary(actor_id, query)
    return BeneficiaryResolutionResponse(status=result.status, matches=list(result.matches))


@router.post("/transfers/drafts", response_model=TransferDraftResponse, tags=["transfers"])
def create_transfer_draft(
    request: TransferDraftRequest,
    session: Db,
    actor_id: Actor,
    verifier: Verifier,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)],
) -> TransferDraftResponse:
    draft = TransferService(session, verifier).create_transfer_draft(
        user_id=actor_id,
        source_account_id=request.source_account_id,
        destination_account_id=request.destination_account_id,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=idempotency_key,
    )
    return TransferDraftResponse.model_validate(draft)


@router.get(
    "/transfers/drafts/{draft_id}", response_model=TransferDraftResponse, tags=["transfers"]
)
def get_transfer_draft(
    draft_id: UUID, session: Db, actor_id: Actor, verifier: Verifier
) -> TransferDraftResponse:
    return TransferDraftResponse.model_validate(
        TransferService(session, verifier).get_transfer_draft(draft_id, actor_id)
    )


@router.post("/transfers/{draft_id}/commit", response_model=TransferReceipt, tags=["transfers"])
def commit_transfer(
    draft_id: UUID,
    request: CommitTransferRequest,
    session: Db,
    actor_id: Actor,
    verifier: Verifier,
) -> TransferReceipt:
    transaction = TransferService(session, verifier).commit_transfer(
        draft_id, actor_id, request.authorization_ref
    )
    return TransferReceipt(
        transaction_id=transaction.id,
        reference=transaction.reference,
        status=transaction.status,
        amount=transaction.amount,
        currency=transaction.currency,
    )


@router.get("/transfers/{transfer_id}", response_model=TransferDraftResponse, tags=["transfers"])
def get_transfer_status(
    transfer_id: UUID,
    session: Db,
    actor_id: Actor,
    verifier: Verifier,
) -> TransferDraftResponse:
    return TransferDraftResponse.model_validate(
        TransferService(session, verifier).get_transfer_status(transfer_id, actor_id)
    )
