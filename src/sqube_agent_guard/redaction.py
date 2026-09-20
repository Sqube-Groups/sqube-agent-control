from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"([a-zA-Z0-9._%+-]{1,2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
_TOKEN_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def redact_value(value: Any) -> str:
    text = _to_summary_string(value)
    text = _EMAIL_RE.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if len(text) > 200:
        text = text[:197] + "..."
    return text


def _to_summary_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = [f"{k}={redact_value(v)}" for k, v in sorted(value.items())]
        return " ".join(parts)
    if isinstance(value, (list, tuple)):
        return " ".join(redact_value(v) for v in value)
    return str(value)
