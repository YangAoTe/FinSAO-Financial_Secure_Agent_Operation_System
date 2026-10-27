from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, RootModel

from agent_tools.client import BankingHttpClient
from agent_tools.contracts import BaseBankingTool, ExecutionContext
from banking_core.app.domain.enums import Currency
from banking_core.app.domain.money import MoneyDecimal


class NoInput(BaseModel):
    pass


class SavingsPotCreateInput(BaseModel):
    name: str
    target_amount: MoneyDecimal
    currency: Currency = Currency.CNY
    target_date: date
    idempotency_key: str


class SavingsContributionInput(BaseModel):
    pot_id: UUID
    amount: MoneyDecimal
    note: str | None = None
    idempotency_key: str


class SavingsPotOutput(BaseModel):
    id: UUID
    name: str
    target_amount: Decimal
    saved_amount: Decimal
    currency: Currency
    target_date: date
    status: str
    allocation_mode: str
    created_at: datetime
    updated_at: datetime


class SavingsPotListOutput(BaseModel):
    items: list[SavingsPotOutput]


class SavingsContributionOutput(BaseModel):
    id: UUID
    pot_id: UUID
    amount: Decimal
    note: str | None
    created_at: datetime


class ListSavingsPotsTool(BaseBankingTool[NoInput, SavingsPotListOutput]):
    name = "list_savings_pots"
    description = "List virtual savings goals"
    action = "savings.list"
    risk_policy = "GREEN"
    input_model = NoInput
    output_model = SavingsPotListOutput

    def __init__(self, client: BankingHttpClient) -> None:
        self.client = client

    async def execute(self, input_data: NoInput, context: ExecutionContext) -> SavingsPotListOutput:
        del input_data
        result = await self.client.request(
            "GET", "/savings-pots", context, RootModel[list[dict[str, Any]]]
        )
        return SavingsPotListOutput.model_validate({"items": result.root})


class CreateSavingsPotTool(BaseBankingTool[SavingsPotCreateInput, SavingsPotOutput]):
    name = "create_savings_pot"
    description = "Create a virtual savings goal; no account funds are moved"
    action = "savings.create"
    risk_policy = "GREEN"
    input_model = SavingsPotCreateInput
    output_model = SavingsPotOutput

    def __init__(self, client: BankingHttpClient) -> None:
        self.client = client

    async def execute(
        self, input_data: SavingsPotCreateInput, context: ExecutionContext
    ) -> SavingsPotOutput:
        return await self.client.request(
            "POST",
            "/savings-pots",
            context,
            SavingsPotOutput,
            json=input_data.model_dump(mode="json"),
            mutation=True,
        )


class ContributeSavingsPotTool(
    BaseBankingTool[SavingsContributionInput, SavingsContributionOutput]
):
    name = "contribute_savings_pot"
    description = "Record a virtual allocation toward a savings goal; no funds are moved"
    action = "savings.contribute"
    risk_policy = "GREEN"
    input_model = SavingsContributionInput
    output_model = SavingsContributionOutput

    def __init__(self, client: BankingHttpClient) -> None:
        self.client = client

    async def execute(
        self, input_data: SavingsContributionInput, context: ExecutionContext
    ) -> SavingsContributionOutput:
        values = input_data.model_dump(mode="json")
        pot_id = values.pop("pot_id")
        return await self.client.request(
            "POST",
            f"/savings-pots/{pot_id}/contributions",
            context,
            SavingsContributionOutput,
            json=values,
            mutation=True,
        )


def savings_tools(client: BankingHttpClient) -> list[BaseBankingTool[Any, Any]]:
    return [
        ListSavingsPotsTool(client),
        CreateSavingsPotTool(client),
        ContributeSavingsPotTool(client),
    ]
