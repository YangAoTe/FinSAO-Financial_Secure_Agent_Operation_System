"""Opt-in proactive suggestions; this module never executes banking mutations."""

from __future__ import annotations

from datetime import datetime, time
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProactiveSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    event_kind: str
    enabled: bool
    quiet_start: time | None = None
    quiet_end: time | None = None
    minimum_interval_minutes: int
    last_emitted_at: datetime | None = None


class ProactiveStore(Protocol):
    def configure_proactive(
        self,
        *,
        user_id: UUID,
        event_kind: str,
        enabled: bool,
        quiet_start: time | None,
        quiet_end: time | None,
        minimum_interval_minutes: int,
    ) -> ProactiveSubscription: ...

    def reserve_proactive_delivery(
        self, *, user_id: UUID, event_kind: str, now: datetime
    ) -> bool: ...


class ProactiveSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_kind: str
    message: str
    automatic_financial_action: bool = False


class ProactiveConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    quiet_start: time | None = None
    quiet_end: time | None = None
    minimum_interval_minutes: int = Field(default=1440, ge=1, le=43_200)


class ProactiveEventEngine:
    def __init__(self, store: ProactiveStore) -> None:
        self._store = store

    def configure(
        self,
        *,
        user_id: UUID,
        event_kind: str,
        enabled: bool,
        quiet_start: time | None = None,
        quiet_end: time | None = None,
        minimum_interval_minutes: int = 1440,
    ) -> ProactiveSubscription:
        return self._store.configure_proactive(
            user_id=user_id,
            event_kind=event_kind,
            enabled=enabled,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
            minimum_interval_minutes=minimum_interval_minutes,
        )

    def suggest(
        self, *, user_id: UUID, event_kind: str, now: datetime
    ) -> ProactiveSuggestion | None:
        if not self._store.reserve_proactive_delivery(
            user_id=user_id, event_kind=event_kind, now=now
        ):
            return None
        messages = {
            "BUDGET_THRESHOLD": "预算接近上限。是否查看预算详情并调整计划？",
            "SUBSCRIPTION_RENEWAL": "检测到即将续费的订阅。是否查看并决定保留或取消？",
        }
        return ProactiveSuggestion(
            event_kind=event_kind,
            message=messages.get(event_kind, "检测到一条已订阅提醒，是否查看详情？"),
        )
