"""Provider-neutral structured generation with OpenAI-compatible adapters."""

from __future__ import annotations

import asyncio
import json
import logging
from enum import StrEnum
from time import perf_counter
from typing import Generic, Protocol, TypeVar, cast
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from agent.contracts import ConversationMessage

logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ProviderErrorCode(StrEnum):
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "PROVIDER_TIMEOUT"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    UPSTREAM = "PROVIDER_UPSTREAM_ERROR"
    INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"


class ProviderError(RuntimeError):
    def __init__(
        self,
        *,
        code: ProviderErrorCode,
        provider: str,
        request_id: UUID,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(f"{provider} request {request_id} failed: {code}")
        self.code = code
        self.provider = provider
        self.request_id = request_id
        self.retryable = retryable
        self.status_code = status_code


class ProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ProviderResult(BaseModel, Generic[OutputT]):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str
    request_id: UUID
    output: OutputT
    usage: ProviderUsage
    latency_ms: int


class ModelProvider(Protocol):
    name: str
    model: str

    @property
    def available(self) -> bool: ...

    async def generate_structured(
        self,
        *,
        messages: list[ConversationMessage],
        output_model: type[OutputT],
        request_id: UUID | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1_024,
    ) -> ProviderResult[OutputT]: ...

    async def close(self) -> None: ...


class FakeModelProvider:
    """Deterministic offline provider for contract tests and local development."""

    name = "fake"
    model = "deterministic-fixture"

    def __init__(self, output: BaseModel | dict[str, object]) -> None:
        self._output = output

    @property
    def available(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def generate_structured(
        self,
        *,
        messages: list[ConversationMessage],
        output_model: type[OutputT],
        request_id: UUID | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1_024,
    ) -> ProviderResult[OutputT]:
        del messages, temperature, max_tokens
        raw = (
            self._output.model_dump(mode="json")
            if isinstance(self._output, BaseModel)
            else self._output
        )
        output = output_model.model_validate(cast(object, raw))
        return ProviderResult(
            provider=self.name,
            model=self.model,
            request_id=request_id or uuid4(),
            output=output,
            usage=ProviderUsage(),
            latency_ms=0,
        )


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: SecretStr | None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._max_retries = max_retries
        self._owns_client = client is None
        headers = {"Content-Type": "application/json"}
        if api_key is not None and api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"
        self._headers = headers
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_seconds
        )

    @property
    def available(self) -> bool:
        return bool(self.model and self._api_key and self._api_key.get_secret_value())

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate_structured(
        self,
        *,
        messages: list[ConversationMessage],
        output_model: type[OutputT],
        request_id: UUID | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1_024,
    ) -> ProviderResult[OutputT]:
        current_request_id = request_id or uuid4()
        if not self.available:
            raise ProviderError(
                code=ProviderErrorCode.UNAVAILABLE,
                provider=self.name,
                request_id=current_request_id,
                retryable=False,
            )
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role.value, "content": message.content} for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": self._response_format(output_model),
        }
        started = perf_counter()
        response = await self._post_with_retry(payload, current_request_id)
        latency_ms = round((perf_counter() - started) * 1_000)
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            raw_output = content if isinstance(content, dict) else json.loads(content)
            output = output_model.model_validate(raw_output)
            raw_usage = body.get("usage") or {}
            usage = ProviderUsage(
                input_tokens=raw_usage.get("prompt_tokens"),
                output_tokens=raw_usage.get("completion_tokens"),
                total_tokens=raw_usage.get("total_tokens"),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
            raise ProviderError(
                code=ProviderErrorCode.INVALID_RESPONSE,
                provider=self.name,
                request_id=current_request_id,
                retryable=False,
                status_code=response.status_code,
            ) from None
        logger.info(
            "model request completed provider=%s model=%s request_id=%s",
            self.name,
            self.model,
            current_request_id,
        )
        return ProviderResult(
            provider=self.name,
            model=self.model,
            request_id=current_request_id,
            output=output,
            usage=usage,
            latency_ms=latency_ms,
        )

    def _response_format(self, output_model: type[BaseModel]) -> dict[str, object]:
        del output_model
        return {"type": "json_object"}

    async def _post_with_retry(
        self, payload: dict[str, object], request_id: UUID
    ) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers={**self._headers, "X-Request-Id": str(request_id)},
                )
            except httpx.TimeoutException:
                if attempt < self._max_retries:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                raise ProviderError(
                    code=ProviderErrorCode.TIMEOUT,
                    provider=self.name,
                    request_id=request_id,
                    retryable=True,
                ) from None
            except httpx.TransportError:
                if attempt < self._max_retries:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                raise ProviderError(
                    code=ProviderErrorCode.UPSTREAM,
                    provider=self.name,
                    request_id=request_id,
                    retryable=True,
                ) from None
            if response.status_code < 400:
                return response
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                await asyncio.sleep(0.2 * (2**attempt))
                continue
            code = (
                ProviderErrorCode.RATE_LIMITED
                if response.status_code == 429
                else ProviderErrorCode.UPSTREAM
            )
            raise ProviderError(
                code=code,
                provider=self.name,
                request_id=request_id,
                retryable=retryable,
                status_code=response.status_code,
            )
        raise AssertionError("retry loop must return or raise")


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"


class QwenProvider(OpenAICompatibleProvider):
    name = "qwen"


class LocalModelProvider(OpenAICompatibleProvider):
    name = "local"

    @property
    def available(self) -> bool:
        return bool(self.model)

    def _response_format(self, output_model: type[BaseModel]) -> dict[str, object]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_output",
                "strict": True,
                "schema": output_model.model_json_schema(),
            },
        }
