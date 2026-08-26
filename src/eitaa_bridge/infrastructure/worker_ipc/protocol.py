"""Signed JSON-line envelope contract for local provider worker processes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import re
import time
from typing import Any, Mapping
import uuid

from ...errors import WorkerIpcError
from .secret_file import WorkerIpcSecret

IPC_PROTOCOL_NAME = "eitaa-bridge-worker-ipc"
IPC_PROTOCOL_VERSION = 1
IPC_MAX_MESSAGE_BYTES = 1024 * 1024
IPC_MAX_FUTURE_DEADLINE_MS = 5 * 60 * 1000
_KINDS = frozenset({"request", "response"})
_METHOD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,3}$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "session",
        "sessionobject",
        "rawsession",
        "accesshash",
        "rawpeer",
        "peerobject",
        "rawmessage",
        "authorization",
        "cookie",
        "password",
        "otp",
        "token",
        "secret",
    }
)


def _canonical_uuid4(value: object, *, field: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise WorkerIpcError(
            "The worker IPC envelope identity is invalid.",
            safe_context={"field": field},
            code="ipc_envelope_invalid",
        ) from exc
    if parsed.version != 4 or str(parsed) != str(value):
        raise WorkerIpcError(
            "The worker IPC envelope identity is invalid.",
            safe_context={"field": field},
            code="ipc_envelope_invalid",
        )
    return str(parsed)


def _validate_payload(value: object, *, depth: int = 0) -> None:
    if depth > 16:
        raise WorkerIpcError(
            "The worker IPC payload is too deeply nested.",
            code="ipc_payload_invalid",
        )
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise WorkerIpcError(
            "The worker IPC payload contains a non-finite number.",
            code="ipc_payload_invalid",
        )
    if isinstance(value, list):
        if len(value) > 4096:
            raise WorkerIpcError(
                "The worker IPC payload collection is too large.",
                code="ipc_payload_invalid",
            )
        for item in value:
            _validate_payload(item, depth=depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > 1024:
            raise WorkerIpcError(
                "The worker IPC payload object is too large.",
                code="ipc_payload_invalid",
            )
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise WorkerIpcError(
                    "The worker IPC payload key is invalid.",
                    code="ipc_payload_invalid",
                )
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in _FORBIDDEN_PAYLOAD_KEYS:
                raise WorkerIpcError(
                    "Sensitive provider state cannot cross the worker IPC boundary.",
                    safe_context={"field": key},
                    code="ipc_payload_forbidden",
                )
            _validate_payload(item, depth=depth + 1)
        return
    raise WorkerIpcError(
        "The worker IPC payload type is invalid.",
        safe_context={"type": type(value).__name__},
        code="ipc_payload_invalid",
    )


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WorkerIpcError(
            "The worker IPC envelope cannot be encoded.",
            code="ipc_envelope_invalid",
        ) from exc
    if len(encoded) > IPC_MAX_MESSAGE_BYTES:
        raise WorkerIpcError(
            "The worker IPC envelope is too large.",
            code="ipc_message_too_large",
        )
    return encoded


@dataclass(frozen=True, slots=True)
class IpcEnvelope:
    kind: str
    correlation_id: str
    messenger_account_id: str
    provider: str
    method: str
    deadline_unix_ms: int
    nonce: str
    payload: Mapping[str, object]
    key_id: str
    signature: str

    @property
    def ok(self) -> bool:
        return not (
            self.kind == "response"
            and isinstance(self.payload.get("error"), Mapping)
        )


class WorkerIpcCodec:
    """Build and validate HMAC-authenticated envelopes for one account worker."""

    def __init__(self, secret: WorkerIpcSecret) -> None:
        self.secret = secret

    def request(
        self,
        method: str,
        payload: Mapping[str, object] | None = None,
        *,
        correlation_id: str | None = None,
        deadline_unix_ms: int | None = None,
        nonce: str | None = None,
    ) -> str:
        return self._encode(
            kind="request",
            correlation_id=correlation_id or str(uuid.uuid4()),
            method=method,
            deadline_unix_ms=(
                deadline_unix_ms
                if deadline_unix_ms is not None
                else int(time.time() * 1000) + 30_000
            ),
            nonce=nonce or uuid.uuid4().hex,
            payload=dict(payload or {}),
        )

    def response(
        self,
        request: IpcEnvelope,
        payload: Mapping[str, object] | None = None,
    ) -> str:
        return self._encode(
            kind="response",
            correlation_id=request.correlation_id,
            method=request.method,
            deadline_unix_ms=request.deadline_unix_ms,
            nonce=uuid.uuid4().hex,
            payload=dict(payload or {}),
        )

    def error_response(
        self,
        *,
        code: str,
        correlation_id: str | None = None,
        method: str = "worker.error",
        deadline_unix_ms: int | None = None,
    ) -> str:
        safe_code = str(code or "ipc_request_failed")
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", safe_code):
            safe_code = "ipc_request_failed"
        return self._encode(
            kind="response",
            correlation_id=correlation_id or str(uuid.uuid4()),
            method=method if _METHOD.fullmatch(method) else "worker.error",
            deadline_unix_ms=(
                deadline_unix_ms
                if deadline_unix_ms is not None
                else int(time.time() * 1000) + 30_000
            ),
            nonce=uuid.uuid4().hex,
            payload={"error": {"code": safe_code}},
        )

    def decode(
        self,
        raw: str | bytes,
        *,
        expected_kind: str | None = None,
        now_unix_ms: int | None = None,
    ) -> IpcEnvelope:
        if isinstance(raw, str):
            raw_bytes = raw.encode("utf-8")
        elif isinstance(raw, bytes):
            raw_bytes = raw
        else:
            raise WorkerIpcError(
                "The worker IPC message type is invalid.",
                code="ipc_envelope_invalid",
            )
        if not raw_bytes or len(raw_bytes) > IPC_MAX_MESSAGE_BYTES:
            raise WorkerIpcError(
                "The worker IPC message size is invalid.",
                code="ipc_message_too_large",
            )
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerIpcError(
                "The worker IPC message is not valid JSON.",
                code="ipc_envelope_invalid",
            ) from exc
        if not isinstance(payload, dict):
            raise WorkerIpcError(
                "The worker IPC envelope must be an object.",
                code="ipc_envelope_invalid",
            )
        required = {
            "protocol",
            "version",
            "kind",
            "correlation_id",
            "messenger_account_id",
            "provider",
            "method",
            "deadline_unix_ms",
            "nonce",
            "payload",
            "auth",
        }
        if set(payload) != required:
            raise WorkerIpcError(
                "The worker IPC envelope fields are invalid.",
                code="ipc_envelope_invalid",
            )
        if payload["protocol"] != IPC_PROTOCOL_NAME or payload["version"] != 1:
            raise WorkerIpcError(
                "The worker IPC protocol version is unsupported.",
                code="ipc_protocol_unsupported",
            )
        kind = str(payload["kind"])
        if kind not in _KINDS or (expected_kind is not None and kind != expected_kind):
            raise WorkerIpcError(
                "The worker IPC message kind is invalid.",
                code="ipc_kind_invalid",
            )
        correlation_id = _canonical_uuid4(
            payload["correlation_id"],
            field="correlation_id",
        )
        messenger_account_id = _canonical_uuid4(
            payload["messenger_account_id"],
            field="messenger_account_id",
        )
        provider = str(payload["provider"])
        method = str(payload["method"])
        nonce = str(payload["nonce"])
        deadline = payload["deadline_unix_ms"]
        if (
            not _PROVIDER.fullmatch(provider)
            or provider != self.secret.provider
            or messenger_account_id != self.secret.messenger_account_id
            or not _METHOD.fullmatch(method)
            or not _NONCE.fullmatch(nonce)
            or not isinstance(deadline, int)
            or isinstance(deadline, bool)
        ):
            raise WorkerIpcError(
                "The worker IPC envelope scope is invalid.",
                code="ipc_envelope_invalid",
            )
        current = now_unix_ms if now_unix_ms is not None else int(time.time() * 1000)
        if deadline < current:
            raise WorkerIpcError(
                "The worker IPC request deadline has expired.",
                code="ipc_deadline_expired",
            )
        if deadline > current + IPC_MAX_FUTURE_DEADLINE_MS:
            raise WorkerIpcError(
                "The worker IPC request deadline is too far in the future.",
                code="ipc_deadline_invalid",
            )
        auth = payload["auth"]
        if (
            not isinstance(auth, dict)
            or set(auth) != {"algorithm", "key_id", "signature"}
            or auth.get("algorithm") != "hmac-sha256"
            or auth.get("key_id") != self.secret.key_id
            or not isinstance(auth.get("signature"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(auth.get("signature")))
        ):
            raise WorkerIpcError(
                "The worker IPC authentication data is invalid.",
                code="ipc_authentication_failed",
            )
        unsigned = dict(payload)
        unsigned["auth"] = {
            "algorithm": "hmac-sha256",
            "key_id": self.secret.key_id,
        }
        expected = hmac.new(
            self.secret.secret,
            _canonical_json(unsigned),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, str(auth["signature"])):
            raise WorkerIpcError(
                "The worker IPC message authentication failed.",
                code="ipc_authentication_failed",
            )
        body = payload["payload"]
        if not isinstance(body, dict):
            raise WorkerIpcError(
                "The worker IPC payload must be an object.",
                code="ipc_payload_invalid",
            )
        _validate_payload(body)
        return IpcEnvelope(
            kind=kind,
            correlation_id=correlation_id,
            messenger_account_id=messenger_account_id,
            provider=provider,
            method=method,
            deadline_unix_ms=deadline,
            nonce=nonce,
            payload=body,
            key_id=self.secret.key_id,
            signature=str(auth["signature"]),
        )

    def _encode(
        self,
        *,
        kind: str,
        correlation_id: str,
        method: str,
        deadline_unix_ms: int,
        nonce: str,
        payload: Mapping[str, object],
    ) -> str:
        if kind not in _KINDS or not _METHOD.fullmatch(method):
            raise WorkerIpcError(
                "The worker IPC envelope cannot be constructed.",
                code="ipc_envelope_invalid",
            )
        selected_correlation = _canonical_uuid4(
            correlation_id,
            field="correlation_id",
        )
        if not _NONCE.fullmatch(nonce):
            raise WorkerIpcError(
                "The worker IPC nonce is invalid.",
                code="ipc_envelope_invalid",
            )
        if not isinstance(deadline_unix_ms, int) or isinstance(deadline_unix_ms, bool):
            raise WorkerIpcError(
                "The worker IPC deadline is invalid.",
                code="ipc_deadline_invalid",
            )
        _validate_payload(payload)
        unsigned: dict[str, object] = {
            "protocol": IPC_PROTOCOL_NAME,
            "version": IPC_PROTOCOL_VERSION,
            "kind": kind,
            "correlation_id": selected_correlation,
            "messenger_account_id": self.secret.messenger_account_id,
            "provider": self.secret.provider,
            "method": method,
            "deadline_unix_ms": deadline_unix_ms,
            "nonce": nonce,
            "payload": dict(payload),
            "auth": {
                "algorithm": "hmac-sha256",
                "key_id": self.secret.key_id,
            },
        }
        signature = hmac.new(
            self.secret.secret,
            _canonical_json(unsigned),
            hashlib.sha256,
        ).hexdigest()
        signed = dict(unsigned)
        signed["auth"] = {
            "algorithm": "hmac-sha256",
            "key_id": self.secret.key_id,
            "signature": signature,
        }
        return _canonical_json(signed).decode("utf-8")
