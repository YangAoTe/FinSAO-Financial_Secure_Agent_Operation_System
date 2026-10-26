"""Explicit live provider smoke test; never run from the default pytest suite."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from agent.config import AgentSettings
from agent.contracts import ConversationMessage, ConversationRole, TrustLabel
from agent.providers import DeepSeekProvider, ProviderError, QwenProvider

ROOT = Path(__file__).resolve().parents[1]
plt: Any = import_module("matplotlib.pyplot")
pd: Any = import_module("pandas")
sns: Any = import_module("seaborn")


class SmokeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]


async def _run() -> None:
    settings = AgentSettings()
    providers = [
        DeepSeekProvider(
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            timeout_seconds=settings.model_timeout_seconds,
            max_retries=settings.model_max_retries,
        ),
        QwenProvider(
            model=settings.qwen_model,
            base_url=settings.qwen_base_url,
            api_key=settings.qwen_api_key,
            timeout_seconds=settings.model_timeout_seconds,
            max_retries=settings.model_max_retries,
        ),
    ]
    records: list[dict[str, object]] = []
    message = ConversationMessage(
        role=ConversationRole.USER,
        content='Return only this JSON object: {"status":"ok"}',
        trust=TrustLabel.USER_INPUT,
    )
    for provider in providers:
        if not provider.available:
            records.append(
                {
                    "provider": provider.name,
                    "model": provider.model,
                    "status": "NOT_RUN_UNAVAILABLE",
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "latency_ms": None,
                    "error_code": None,
                }
            )
            await provider.close()
            continue
        try:
            result = await provider.generate_structured(
                messages=[message], output_model=SmokeAnswer, max_tokens=32
            )
            records.append(
                {
                    "provider": provider.name,
                    "model": provider.model,
                    "status": "SUCCESS",
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "total_tokens": result.usage.total_tokens,
                    "latency_ms": result.latency_ms,
                    "error_code": None,
                }
            )
        except ProviderError as exc:
            records.append(
                {
                    "provider": provider.name,
                    "model": provider.model,
                    "status": "FAILED",
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "latency_ms": None,
                    "error_code": exc.code.value,
                }
            )
        finally:
            await provider.close()
    output = {
        "run_at_utc": datetime.now(UTC).isoformat(),
        "purpose": "connectivity_only_not_model_comparison",
        "records": records,
    }
    target = ROOT / "evaluation" / "reports" / "p1_provider_smoke.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    successful = [record for record in records if record["status"] == "SUCCESS"]
    if successful:
        frame = pd.DataFrame(successful)
        figure, axes = plt.subplots(1, 2, figsize=(9, 4))
        sns.barplot(data=frame, x="provider", y="total_tokens", ax=axes[0], color="#4c72b0")
        axes[0].set_title("Connectivity smoke tokens")
        axes[0].set_ylabel("Provider-reported tokens")
        sns.barplot(data=frame, x="provider", y="latency_ms", ax=axes[1], color="#55a868")
        axes[1].set_title("Connectivity smoke latency")
        axes[1].set_ylabel("Milliseconds")
        figure.tight_layout()
        figure.savefig(ROOT / "evaluation" / "figures" / "p1_provider_smoke.png", dpi=180)
        plt.close(figure)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_run())
