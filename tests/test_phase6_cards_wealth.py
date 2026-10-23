from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from agent_tools.client import BankingHttpClient, StaticServiceAuthenticator
from agent_tools.registry import ToolRegistry
from agent_tools.tools import register_default_tools
from banking_core.app.main import app
from banking_core.app.services.cards_wealth import WealthService
from banking_core.app.services.errors import ConflictError


class WriteSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        pass


def test_risk_questionnaire_is_deterministic() -> None:
    session = WriteSession()
    service = WealthService(cast(Session, cast(Any, session)))
    assert (
        service.assess(cast(Any, "00000000-0000-0000-0000-000000000001"), [1] * 5).risk_tier
        == "GREEN"
    )


def test_product_comparison_rejects_duplicate_ids() -> None:
    service = WealthService(cast(Session, cast(Any, WriteSession())))
    product_id = uuid4()
    with pytest.raises(ConflictError, match="duplicates"):
        service.compare_products([product_id, product_id])
    assert (
        service.assess(cast(Any, "00000000-0000-0000-0000-000000000001"), [5] * 5).risk_tier
        == "RED"
    )


def test_phase6_routes_are_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/cards/{card_id}/report-lost" in paths
    assert "/wealth/orders/{order_id}/commit" in paths
    assert "/wealth/orders/{order_id}" in paths
    assert "/wealth/redemptions" in paths
    assert "/wealth/recommendations" in paths


def test_phase6_tools_are_registered_without_authorization_arguments() -> None:
    client = BankingHttpClient("http://banking", StaticServiceAuthenticator("test"))
    registry = ToolRegistry()
    register_default_tools(registry, client)
    names = {item["name"] for item in registry.list_allowed()}
    assert {
        "report_card_lost",
        "commit_wealth_subscription",
        "commit_wealth_redemption",
        "assess_risk_profile",
        "unfreeze_card",
        "get_card_status",
        "get_wealth_order_status",
        "get_wealth_recommendations",
    } <= names
    assert "authorization" not in str(registry.export_input_schema("report_card_lost")).lower()
    assert (
        "authorization" not in str(registry.export_input_schema("commit_wealth_redemption")).lower()
    )
