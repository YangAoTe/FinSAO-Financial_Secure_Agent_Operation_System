"""Reject authentication secrets before requests can reach an external model."""

from __future__ import annotations

import re


class SensitiveInputError(ValueError):
    pass


class SensitiveDataGuard:
    """Small deterministic guard for credentials that never belong in Agent chat."""

    _PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"(?:密码|口令|password)\s*(?:是|为|[:：=])?\s*\S{4,}", re.IGNORECASE),
        re.compile(r"(?:验证码|动态码|otp|mfa)\s*(?:是|为|[:：=])?\s*\d{4,8}", re.IGNORECASE),
        re.compile(r"(?:cvv|cvc|安全码)\s*(?:是|为|[:：=])?\s*\d{3,4}", re.IGNORECASE),
        re.compile(
            r"(?:卡号|银行卡号|card\s*number)\s*(?:是|为|[:：=])?\s*[\d -]{13,25}",
            re.IGNORECASE,
        ),
    )

    @classmethod
    def ensure_safe(cls, text: str) -> str:
        if any(pattern.search(text) for pattern in cls._PATTERNS):
            raise SensitiveInputError(
                "请勿在聊天中输入密码、验证码、CVV 或完整银行卡号；请使用独立安全验证界面。"
            )
        return text
