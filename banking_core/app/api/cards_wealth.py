from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from banking_core.app.api.dependencies import get_current_user_id, get_db_session
from banking_core.app.domain.enums import RiskTier
from banking_core.app.schemas.cards_wealth import (
    AuthorizedOperationRequest,
    CardLimitRequest,
    CardResponse,
    CompareProductsRequest,
    HoldingResponse,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    WealthOrderRequest,
    WealthOrderResponse,
    WealthProductResponse,
)
from banking_core.app.services.cards_wealth import CardService, WealthService

router = APIRouter()
Db = Annotated[Session, Depends(get_db_session)]
Actor = Annotated[UUID, Depends(get_current_user_id)]


@router.get("/cards", response_model=list[CardResponse], tags=["cards"])
def list_cards(session: Db, actor: Actor) -> list[CardResponse]:
    return [CardResponse.model_validate(item) for item in CardService(session).list(actor)]


@router.get("/cards/{card_id}", response_model=CardResponse, tags=["cards"])
def get_card(card_id: UUID, session: Db, actor: Actor) -> CardResponse:
    return CardResponse.model_validate(CardService(session).get(card_id, actor))


@router.patch("/cards/{card_id}/limit", response_model=CardResponse, tags=["cards"])
def update_card_limit(
    card_id: UUID, request: CardLimitRequest, session: Db, actor: Actor
) -> CardResponse:
    return CardResponse.model_validate(
        CardService(session).update_limit(
            card_id, actor, request.spending_limit, request.authorization_ref
        )
    )


@router.post("/cards/{card_id}/freeze", response_model=CardResponse, tags=["cards"])
def freeze_card(
    card_id: UUID, request: AuthorizedOperationRequest, session: Db, actor: Actor
) -> CardResponse:
    return CardResponse.model_validate(
        CardService(session).set_frozen(card_id, actor, True, request.authorization_ref)
    )


@router.post("/cards/{card_id}/unfreeze", response_model=CardResponse, tags=["cards"])
def unfreeze_card(
    card_id: UUID, request: AuthorizedOperationRequest, session: Db, actor: Actor
) -> CardResponse:
    return CardResponse.model_validate(
        CardService(session).set_frozen(card_id, actor, False, request.authorization_ref)
    )


@router.post("/cards/{card_id}/report-lost", response_model=CardResponse, tags=["cards"])
def report_card_lost(
    card_id: UUID, request: AuthorizedOperationRequest, session: Db, actor: Actor
) -> CardResponse:
    return CardResponse.model_validate(
        CardService(session).report_lost(card_id, actor, request.authorization_ref)
    )


@router.get("/wealth/products", response_model=list[WealthProductResponse], tags=["wealth"])
def list_wealth_products(
    session: Db,
    actor: Actor,
    product_type: str | None = None,
    risk_tier: RiskTier | None = None,
) -> list[WealthProductResponse]:
    del actor
    return [
        WealthProductResponse.model_validate(item)
        for item in WealthService(session).list_products(product_type, risk_tier)
    ]


@router.post(
    "/wealth/products/compare", response_model=list[WealthProductResponse], tags=["wealth"]
)
def compare_wealth_products(
    request: CompareProductsRequest, session: Db, actor: Actor
) -> list[WealthProductResponse]:
    del actor
    return [
        WealthProductResponse.model_validate(item)
        for item in WealthService(session).compare_products(request.product_ids)
    ]


@router.get("/wealth/recommendations", response_model=list[WealthProductResponse], tags=["wealth"])
def recommend_wealth_products(session: Db, actor: Actor) -> list[WealthProductResponse]:
    return [
        WealthProductResponse.model_validate(item)
        for item in WealthService(session).recommend_products(actor)
    ]


@router.post("/wealth/risk-assessment", response_model=RiskAssessmentResponse, tags=["wealth"])
def assess_risk(
    request: RiskAssessmentRequest, session: Db, actor: Actor
) -> RiskAssessmentResponse:
    return RiskAssessmentResponse.model_validate(
        WealthService(session).assess(actor, request.answers)
    )


@router.get("/wealth/holdings", response_model=list[HoldingResponse], tags=["wealth"])
def get_holdings(session: Db, actor: Actor) -> list[HoldingResponse]:
    return [HoldingResponse.model_validate(item) for item in WealthService(session).holdings(actor)]


@router.post("/wealth/orders", response_model=WealthOrderResponse, tags=["wealth"])
def create_wealth_order(
    request: WealthOrderRequest, session: Db, actor: Actor
) -> WealthOrderResponse:
    item = WealthService(session).create_order(
        actor,
        request.account_id,
        request.product_id,
        request.amount,
        request.idempotency_key,
    )
    return WealthOrderResponse.model_validate(item)


@router.post("/wealth/redemptions", response_model=WealthOrderResponse, tags=["wealth"])
def create_wealth_redemption(
    request: WealthOrderRequest, session: Db, actor: Actor
) -> WealthOrderResponse:
    item = WealthService(session).create_redemption_order(
        actor,
        request.account_id,
        request.product_id,
        request.amount,
        request.idempotency_key,
    )
    return WealthOrderResponse.model_validate(item)


@router.get("/wealth/orders/{order_id}", response_model=WealthOrderResponse, tags=["wealth"])
def get_wealth_order(order_id: UUID, session: Db, actor: Actor) -> WealthOrderResponse:
    return WealthOrderResponse.model_validate(WealthService(session).get_order(order_id, actor))


@router.post(
    "/wealth/orders/{order_id}/commit", response_model=WealthOrderResponse, tags=["wealth"]
)
def commit_wealth_order(
    order_id: UUID, request: AuthorizedOperationRequest, session: Db, actor: Actor
) -> WealthOrderResponse:
    return WealthOrderResponse.model_validate(
        WealthService(session).commit_order(order_id, actor, request.authorization_ref)
    )
