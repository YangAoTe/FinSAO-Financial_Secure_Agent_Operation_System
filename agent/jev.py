"""Product-neutral Jev routing boundary pending exact Jev product confirmation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from agent.routing import Intent, IntentResult, Route, RuleRouter


class JevDecision(BaseModel):
    """Untrusted routing advice; deliberately excludes identity and authorization."""

    model_config = ConfigDict(extra="forbid")
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    route: Route
    reason: str = Field(min_length=1, max_length=300)
    required_slots: list[str] = Field(default_factory=list)


class JevAdapter(Protocol):
    @property
    def available(self) -> bool: ...

    async def classify(self, text: str) -> JevDecision: ...


class FakeJevAdapter:
    """Deterministic test double; never performs network or filesystem I/O."""

    def __init__(
        self,
        decision: JevDecision | Callable[[str], Awaitable[JevDecision]],
        *,
        available: bool = True,
    ) -> None:
        self._decision = decision
        self._available = available

    @property
    def available(self) -> bool:
        return self._available

    async def classify(self, text: str) -> JevDecision:
        if callable(self._decision):
            return await self._decision(text)
        return self._decision


class JevRoutingBoundary:
    """Use Jev as optional advice while preserving deterministic safe fallbacks."""

    def __init__(
        self,
        adapter: JevAdapter,
        *,
        enabled: bool = False,
        confidence_threshold: float = 0.8,
        timeout_seconds: float = 1.0,
        circuit_failure_threshold: int = 3,
        rule_router: RuleRouter | None = None,
    ) -> None:
        self._adapter = adapter
        self._enabled = enabled
        self._confidence_threshold = confidence_threshold
        self._timeout_seconds = timeout_seconds
        self._circuit_failure_threshold = circuit_failure_threshold
        self._failures = 0
        self._rules = rule_router or RuleRouter()

    @property
    def circuit_open(self) -> bool:
        return self._failures >= self._circuit_failure_threshold

    async def route(
        self, text: str, *, conversation: list[Any] | None = None
    ) -> IntentResult:
        deterministic = self._rules.route(text, conversation=conversation)
        if (
            not self._enabled
            or not self._adapter.available
            or self.circuit_open
            or deterministic.route == Route.RULE_DIRECT
        ):
            return deterministic
        try:
            decision = await asyncio.wait_for(
                self._adapter.classify(text), timeout=self._timeout_seconds
            )
        except (TimeoutError, Exception):
            self._failures += 1
            return deterministic
        self._failures = 0
        if decision.confidence < self._confidence_threshold:
            return deterministic
        if decision.route == Route.RULE_DIRECT:
            return deterministic
        return IntentResult(
            intent=decision.intent,
            complexity=deterministic.complexity,
            confidence=decision.confidence,
            route=decision.route,
            reason=f"untrusted Jev routing advice: {decision.reason}",
            required_slots=decision.required_slots,
        )
