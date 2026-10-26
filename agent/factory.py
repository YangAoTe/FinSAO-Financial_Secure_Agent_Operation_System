"""Construct configured providers without exposing provider details to planners."""

from pydantic import SecretStr

from agent.config import AgentSettings
from agent.providers import (
    DeepSeekProvider,
    LocalModelProvider,
    ModelProvider,
    QwenProvider,
)


def build_model_provider(settings: AgentSettings) -> ModelProvider | None:
    if settings.model_provider == "offline":
        return None
    if settings.model_provider == "deepseek":
        return DeepSeekProvider(
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            timeout_seconds=settings.model_timeout_seconds,
            max_retries=settings.model_max_retries,
        )
    if settings.model_provider == "qwen":
        return QwenProvider(
            model=settings.qwen_model,
            base_url=settings.qwen_base_url,
            api_key=settings.qwen_api_key,
            timeout_seconds=settings.model_timeout_seconds,
            max_retries=settings.model_max_retries,
        )
    return LocalModelProvider(
        model=settings.local_model_name or "",
        base_url=settings.local_model_base_url,
        api_key=settings.local_model_api_key or SecretStr(""),
        timeout_seconds=settings.model_timeout_seconds,
        max_retries=settings.model_max_retries,
    )
