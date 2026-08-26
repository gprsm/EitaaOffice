from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from typing import Any

SECRET_KEYS = {
    "token", "eitaa_token", "imei", "password", "application_password",
    "app_password", "secret", "authorization", "authorization_header",
    "cookie", "username", "phone_code", "phone_code_hash", "access_hash",
    "auth_key", "server_salt", "session_id", "session_token", "csrf_token",
    "otp", "one_time_password", "set-cookie", "set_cookie", "api_key",
    "client_secret",
}
CONTENT_KEYS = {
    "text", "message", "caption", "body", "content", "excerpt", "title",
    "payload", "packed_data", "raw_request", "raw_response", "response_body", "alt_text",
    "request_body", "bytes", "description", "message_text", "private_message",
}
PHONE_KEYS = {
    "display_hint",
    "phone",
    "phone_hint",
    "phone_number",
    "phone_numbers",
    "phones",
    "recipient_phone",
}
_CANONICAL_PHONE = re.compile(
    r"(?<![0-9])(?:\+[1-9][0-9]{7,14}|00[1-9][0-9]{7,14}|09[0-9]{9})(?![0-9])"
)
_BEARER_VALUE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
    re.IGNORECASE,
)
_PROVIDER_TOKEN_VALUE = re.compile(
    r"(?<![A-Za-z0-9])[0-9]{1,20}:[A-Za-z0-9_-]{20,}(?![A-Za-z0-9])"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mask_phone(value: str) -> str:
    prefix = "+" if value.strip().startswith("+") else ""
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) <= 6:
        return prefix + "***"
    return prefix + digits[:3] + "*" * max(4, len(digits) - 7) + digits[-4:]


def _redact_inline_private_values(value: str) -> str:
    selected = _BEARER_VALUE.sub("Bearer [redacted]", value)
    selected = _PROVIDER_TOKEN_VALUE.sub("[redacted-token]", selected)
    return _CANONICAL_PHONE.sub(
        lambda match: mask_phone(match.group(0)),
        selected,
    )


def _summarize_bytes(value: bytes | bytearray | memoryview) -> dict[str, object]:
    data = bytes(value)
    return {"type": type(value).__name__, "length": len(data), "sha256": _sha256(data), "content_stored": False}


def redact(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    normalized = (key or "").lower()
    if normalized in SECRET_KEYS:
        if isinstance(value, str):
            return {"redacted": True, "present": bool(value), "length": len(value)}
        return {"redacted": True, "present": value is not None}
    if normalized in PHONE_KEYS:
        if isinstance(value, str):
            return mask_phone(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [mask_phone(str(item)) for item in value]
        return {"redacted": True, "present": value is not None}
    if normalized in CONTENT_KEYS:
        if isinstance(value, (bytes, bytearray, memoryview)):
            return _summarize_bytes(value)
        if isinstance(value, str):
            return {"redacted": True, "present": bool(value), "length": len(value), "sha256": _sha256(value.encode("utf-8"))}
        return {"redacted": True, "present": value is not None}
    if depth > 10:
        return {"truncated": True, "reason": "maximum_depth"}
    if isinstance(value, str):
        return _redact_inline_private_values(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return {"path_present": True, "name_length": len(value.name), "suffix": value.suffix.lower()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _summarize_bytes(value)
    if isinstance(value, Mapping):
        return {str(k): redact(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item, depth=depth + 1) for item in value]
    safe_summary = getattr(value, "safe_summary", None)
    if callable(safe_summary):
        return redact(safe_summary(), depth=depth + 1)
    return {"type": type(value).__name__, "repr_stored": False}
