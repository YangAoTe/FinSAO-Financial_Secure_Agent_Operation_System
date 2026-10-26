"""Strict v1 schema for offline banking-Agent evaluation samples."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TRUSTED_ONLY_FIELDS = {
    "user_id",
    "risk_tier",
    "approval_id",
    "authorization_ref",
    "mfa_code",
}


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class ExpectedToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str = Field(pattern=r"^call_[a-z0-9_]+$")
    tool_name: str
    key_arguments: dict[str, str | int | bool] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_trusted_fields(self) -> ExpectedToolCall:
        forbidden = TRUSTED_ONLY_FIELDS.intersection(self.key_arguments)
        if forbidden:
            raise ValueError(f"trusted-only arguments are forbidden: {sorted(forbidden)}")
        return self


class DatasetSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["v1"] = "v1"
    dataset_version: Literal["1.0.0"] = "1.0.0"
    sample_id: str = Field(pattern=r"^zh_[a-z0-9_]+$")
    cluster_id: str = Field(pattern=r"^cluster_[a-z0-9_]+$")
    split: Literal["train", "dev", "test"]
    locale: Literal["zh-CN"] = "zh-CN"
    conversation: list[ConversationMessage] = Field(min_length=1, max_length=8)
    scenario: Literal[
        "ACCOUNTS",
        "TRANSFER",
        "ANALYTICS",
        "SUBSCRIPTIONS",
        "CARDS",
        "WEALTH",
        "SAFETY",
        "OUT_OF_SCOPE",
    ]
    intent: str
    complexity: Literal[1, 2, 3, 4, 5]
    available_context: dict[str, str | int | bool] = Field(default_factory=dict)
    expected_plan: list[str]
    expected_tool_calls: list[ExpectedToolCall]
    expected_risk_tier: Literal["GREEN", "YELLOW", "RED", "NOT_APPLICABLE"]
    requires_clarification: bool
    safety_expectation: Literal[
        "ALLOW_READ",
        "DRAFT_ONLY",
        "REQUIRE_CONFIRMATION",
        "REQUIRE_MFA",
        "REFUSE_AND_EXPLAIN",
        "CLARIFY_OR_DEFER",
    ]
    tags: list[str] = Field(min_length=1)
    source: Literal["manual_seed", "deterministic_expansion"]
    review_status: Literal["pending_second_review", "reviewed"]

    @model_validator(mode="after")
    def validate_dependencies(self) -> DatasetSample:
        seen: set[str] = set()
        for call in self.expected_tool_calls:
            if not set(call.depends_on).issubset(seen):
                raise ValueError("tool dependencies must reference earlier calls")
            seen.add(call.call_id)
        return self
