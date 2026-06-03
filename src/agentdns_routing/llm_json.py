from __future__ import annotations

import json


JSON_MODE_RETRY_TOKENS = (
    "response_format",
    "json_object",
    "unexpected keyword",
    "unknown parameter",
    "not supported",
    "unsupported",
    "extra inputs are not permitted",
)


def load_json_object(text: str, *, empty_message: str = "Empty LLM response") -> dict:
    stripped = text.strip()
    if not stripped:
        raise ValueError(empty_message)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def should_retry_without_json_mode(exc: Exception) -> bool:
    message = str(exc).lower()
    return isinstance(exc, TypeError) or any(token in message for token in JSON_MODE_RETRY_TOKENS)
