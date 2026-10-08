"""AI Model Connection Configuration & Protected Secret Store (P5).

Provides durable, revision-controlled configuration for the outbound AI model
connection, with:
- Server-side egress URL & SSRF validation (HTTPS mandatory for external hosts;
  loopback HTTP allowed only for local development).
- Protected secret storage using AES-256-GCM under the coordinator identity key.
- Safe serialization (read requests NEVER return the secret key or its fragments).
- Dialect-aware synthetic outbound probe with zero PII/OTP/phone exposure.
- Optimistic locking with revision checking.
- Clean lifecycle and connection reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import socket
import sqlite3
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx

from ...errors import BridgeError

_KEY_DERIVATION_SALT = b"eitaa-bridge/ai-connection/secret-key/v1"
_AAD = b"ai-connection-v1"
_NONCE_BYTES = 12
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class AiConnectionError(BridgeError):
    component = "ai_connection"
    code = "ai_connection_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        safe_context: dict[str, Any] | None = None,
        debug_file: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message, safe_context=safe_context, debug_file=debug_file, code=code)
        self.status_code = status_code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class AiConnectionSettings:
    enabled: bool
    provider_dialect: str
    endpoint: str
    model_id: str
    display_name: str
    timeout_seconds: float
    max_input_length: int
    max_output_tokens: int
    concurrency_limit: int
    key_configured: bool
    connection_status: str
    revision: int
    updated_at: str

    def to_safe_dict(self) -> dict[str, Any]:
        """Safe presentation dictionary without secret key."""
        return {
            "enabled": self.enabled,
            "provider_dialect": self.provider_dialect,
            "endpoint": self.endpoint,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "timeout_seconds": self.timeout_seconds,
            "max_input_length": self.max_input_length,
            "max_output_tokens": self.max_output_tokens,
            "concurrency_limit": self.concurrency_limit,
            "key_configured": self.key_configured,
            "connection_status": self.connection_status,
            "revision": self.revision,
            "updated_at": self.updated_at,
        }


def validate_egress_endpoint(url: str) -> str:
    """Validate server-side egress URL against SSRF, plaintext HTTP, and bad schemes."""
    clean = str(url or "").strip()
    if not clean:
        raise AiConnectionError(
            "Endpoint URL cannot be empty.",
            code="ai_endpoint_empty",
            status_code=400,
        )

    try:
        parts = urlsplit(clean)
    except Exception as exc:
        raise AiConnectionError(
            "Endpoint URL is malformed.",
            code="ai_endpoint_malformed",
            status_code=400,
        ) from exc

    if parts.scheme not in ("https", "http"):
        raise AiConnectionError(
            "Endpoint scheme must be https or http.",
            code="ai_endpoint_scheme_invalid",
            status_code=400,
        )

    if parts.username or parts.password:
        raise AiConnectionError(
            "Credentials in URL are strictly forbidden.",
            code="ai_endpoint_credentials_forbidden",
            status_code=400,
        )

    hostname = (parts.hostname or "").strip().lower()
    if not hostname:
        raise AiConnectionError(
            "Endpoint hostname is missing.",
            code="ai_endpoint_hostname_missing",
            status_code=400,
        )

    # Loopback exception for internal testing/development
    is_loopback = hostname in _LOOPBACK_HOSTS
    if not is_loopback:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                is_loopback = True
            elif ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
                raise AiConnectionError(
                    "Private, link-local, or reserved IP addresses are forbidden for external endpoints.",
                    code="ai_endpoint_private_ip_forbidden",
                    status_code=400,
                )
        except ValueError:
            # Domain name (e.g. api.openai.com)
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for entry in addr_info:
                    sockaddr = entry[4]
                    ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if (
                        resolved_ip.is_private
                        or resolved_ip.is_loopback
                        or resolved_ip.is_link_local
                        or resolved_ip.is_reserved
                        or resolved_ip.is_unspecified
                    ):
                        raise AiConnectionError(
                            "Private, link-local, loopback, or reserved IP addresses are forbidden for external endpoints.",
                            code="ai_endpoint_private_ip_forbidden",
                            status_code=400,
                        )
            except (socket.gaierror, socket.herror, OSError):
                # Offline environment or DNS failure
                pass

    # External endpoints must strictly use HTTPS
    if parts.scheme == "http" and not is_loopback:
        raise AiConnectionError(
            "External agent endpoints must use HTTPS.",
            code="ai_endpoint_https_required",
            status_code=400,
        )

    return clean


class AiConnectionStore:
    """Persistent, encrypted store for AI connection settings."""

    def __init__(
        self,
        database: Any,
        protector: Any = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._db = database
        self._protector = protector
        self._clock = clock or _now_iso
        self._cached_cipher_key: bytes | None = None
        self._init_schema()

    def _get_encryption_key(self) -> bytes:
        if self._cached_cipher_key is not None:
            return self._cached_cipher_key

        if self._protector and hasattr(self._protector, "hmac_hex"):
            derived = hmac.new(
                self._protector.hmac_hex(b"ai_key").encode("ascii"),
                _KEY_DERIVATION_SALT,
                hashlib.sha256,
            ).digest()
        else:
            raise AiConnectionError(
                "Valid protector with hmac_hex is required to derive AI encryption key. Insecure fallback salt has been removed.",
                code="ai_protector_unavailable",
                status_code=503,
            )

        self._cached_cipher_key = derived
        return derived

    def _encrypt_secret(self, secret: str) -> bytes:
        key = self._get_encryption_key()
        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = AESGCM(key).encrypt(nonce, secret.encode("utf-8"), _AAD)
        return nonce + ciphertext

    def _decrypt_secret(self, payload: bytes | None) -> str | None:
        if not payload or len(payload) <= _NONCE_BYTES:
            return None
        key = self._get_encryption_key()
        nonce = payload[:_NONCE_BYTES]
        ciphertext = payload[_NONCE_BYTES:]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, _AAD).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise AiConnectionError(
                "Failed to decrypt stored AI secret key.",
                code="ai_secret_decrypt_failed",
            ) from exc

    def _init_schema(self) -> None:
        with self._db._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_connection_settings (
                    id TEXT PRIMARY KEY DEFAULT 'primary',
                    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
                    provider_dialect TEXT NOT NULL DEFAULT 'openai_compatible',
                    endpoint TEXT NOT NULL DEFAULT '',
                    model_id TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL DEFAULT '',
                    timeout_seconds REAL NOT NULL DEFAULT 30.0,
                    max_input_length INTEGER NOT NULL DEFAULT 4096,
                    max_output_tokens INTEGER NOT NULL DEFAULT 1000,
                    concurrency_limit INTEGER NOT NULL DEFAULT 5,
                    secret_key_ciphertext BLOB,
                    revision INTEGER NOT NULL DEFAULT 1,
                    connection_status TEXT NOT NULL DEFAULT 'unconfigured',
                    updated_at TEXT NOT NULL
                );
                """
            )
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM ai_connection_settings WHERE id = 'primary'")
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO ai_connection_settings(
                        id, enabled, provider_dialect, endpoint, model_id, display_name,
                        timeout_seconds, max_input_length, max_output_tokens, concurrency_limit,
                        secret_key_ciphertext, revision, connection_status, updated_at
                    ) VALUES (
                        'primary', 0, 'openai_compatible', '', '', '',
                        30.0, 4096, 1000, 5, NULL, 1, 'unconfigured', ?
                    )
                    """,
                    (self._clock(),),
                )
            connection.commit()

    def get_settings(self) -> AiConnectionSettings:
        with self._db._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM ai_connection_settings WHERE id = 'primary'")
            row = cursor.fetchone()
            if not row:
                raise AiConnectionError("Settings row not found", code="ai_settings_missing")

            ciphertext = row["secret_key_ciphertext"]
            key_configured = ciphertext is not None and len(ciphertext) > _NONCE_BYTES

            return AiConnectionSettings(
                enabled=bool(row["enabled"]),
                provider_dialect=str(row["provider_dialect"]),
                endpoint=str(row["endpoint"]),
                model_id=str(row["model_id"]),
                display_name=str(row["display_name"]),
                timeout_seconds=float(row["timeout_seconds"]),
                max_input_length=int(row["max_input_length"]),
                max_output_tokens=int(row["max_output_tokens"]),
                concurrency_limit=int(row["concurrency_limit"]),
                key_configured=key_configured,
                connection_status=str(row["connection_status"]),
                revision=int(row["revision"]),
                updated_at=str(row["updated_at"]),
            )

    def get_secret_key(self) -> str | None:
        """Internal only: Decrypt and return plaintext secret key."""
        with self._db._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT secret_key_ciphertext FROM ai_connection_settings WHERE id = 'primary'")
            row = cursor.fetchone()
            if not row or not row["secret_key_ciphertext"]:
                return None
            return self._decrypt_secret(row["secret_key_ciphertext"])

    def update_settings(
        self,
        *,
        enabled: bool | None = None,
        provider_dialect: str | None = None,
        endpoint: str | None = None,
        model_id: str | None = None,
        display_name: str | None = None,
        timeout_seconds: float | None = None,
        max_input_length: int | None = None,
        max_output_tokens: int | None = None,
        concurrency_limit: int | None = None,
        secret_key: str | None = None,
        expected_revision: int | None = None,
        connection_status: str | None = None,
    ) -> AiConnectionSettings:
        with self._db._connect() as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM ai_connection_settings WHERE id = 'primary'")
            row = cursor.fetchone()
            if not row:
                raise AiConnectionError("Settings row not found", code="ai_settings_missing")

            current_rev = int(row["revision"])
            if expected_revision is not None and expected_revision != current_rev:
                raise AiConnectionError(
                    f"Stale revision: expected {expected_revision}, current is {current_rev}",
                    code="stale_revision",
                    status_code=409,
                )

            if secret_key is not None and secret_key != "":
                if not self._protector or not hasattr(self._protector, "hmac_hex"):
                    raise AiConnectionError(
                        "Valid protector with hmac_hex is required to store secret keys. Insecure fallback salt has been removed.",
                        code="ai_protector_unavailable",
                        status_code=503,
                    )

            new_enabled = bool(row["enabled"]) if enabled is None else bool(enabled)
            new_dialect = str(row["provider_dialect"]) if provider_dialect is None else str(provider_dialect).strip()
            new_endpoint = str(row["endpoint"]) if endpoint is None else str(endpoint).strip()
            new_model = str(row["model_id"]) if model_id is None else str(model_id).strip()
            new_display = str(row["display_name"]) if display_name is None else str(display_name).strip()
            new_timeout = float(row["timeout_seconds"]) if timeout_seconds is None else float(timeout_seconds)
            new_input_len = int(row["max_input_length"]) if max_input_length is None else int(max_input_length)
            new_output_tok = int(row["max_output_tokens"]) if max_output_tokens is None else int(max_output_tokens)
            new_concur = int(row["concurrency_limit"]) if concurrency_limit is None else int(concurrency_limit)
            new_status = str(row["connection_status"]) if connection_status is None else str(connection_status)

            # Validation
            if new_endpoint:
                new_endpoint = validate_egress_endpoint(new_endpoint)

            if not (1.0 <= new_timeout <= 120.0):
                raise AiConnectionError(
                    "Timeout must be between 1.0 and 120.0 seconds.",
                    code="ai_timeout_invalid",
                    status_code=400,
                )

            if not (100 <= new_input_len <= 32768):
                raise AiConnectionError(
                    "Max input length must be between 100 and 32768 characters.",
                    code="ai_max_input_invalid",
                    status_code=400,
                )

            if not (50 <= new_output_tok <= 8192):
                raise AiConnectionError(
                    "Max output tokens must be between 50 and 8192.",
                    code="ai_max_output_invalid",
                    status_code=400,
                )

            if not (1 <= new_concur <= 50):
                raise AiConnectionError(
                    "Concurrency limit must be between 1 and 50.",
                    code="ai_concurrency_invalid",
                    status_code=400,
                )

            # Secret key lifecycle
            new_ciphertext = row["secret_key_ciphertext"]
            if secret_key is not None:
                if secret_key == "":
                    # Explicit clear
                    new_ciphertext = None
                else:
                    stripped_key = secret_key.strip()
                    if stripped_key.startswith("***") or stripped_key.endswith("***") or stripped_key == "[REDACTED]":
                        raise AiConnectionError(
                            "Masked placeholder cannot be saved as secret key.",
                            code="ai_secret_placeholder_invalid",
                            status_code=400,
                        )
                    new_ciphertext = self._encrypt_secret(stripped_key)

            new_rev = current_rev + 1
            now_str = self._clock()

            # Determine connection_status if not explicitly given
            if connection_status is None:
                has_key = new_ciphertext is not None and len(new_ciphertext) > _NONCE_BYTES
                if new_endpoint and new_model and has_key:
                    new_status = "configured"
                else:
                    new_status = "unconfigured"

            cursor.execute(
                """
                UPDATE ai_connection_settings
                SET enabled = ?,
                    provider_dialect = ?,
                    endpoint = ?,
                    model_id = ?,
                    display_name = ?,
                    timeout_seconds = ?,
                    max_input_length = ?,
                    max_output_tokens = ?,
                    concurrency_limit = ?,
                    secret_key_ciphertext = ?,
                    revision = ?,
                    connection_status = ?,
                    updated_at = ?
                WHERE id = 'primary'
                """,
                (
                    1 if new_enabled else 0,
                    new_dialect,
                    new_endpoint,
                    new_model,
                    new_display,
                    new_timeout,
                    new_input_len,
                    new_output_tok,
                    new_concur,
                    new_ciphertext,
                    new_rev,
                    new_status,
                    now_str,
                ),
            )
            connection.commit()

            key_configured = new_ciphertext is not None and len(new_ciphertext) > _NONCE_BYTES
            return AiConnectionSettings(
                enabled=new_enabled,
                provider_dialect=new_dialect,
                endpoint=new_endpoint,
                model_id=new_model,
                display_name=new_display,
                timeout_seconds=new_timeout,
                max_input_length=new_input_len,
                max_output_tokens=new_output_tok,
                concurrency_limit=new_concur,
                key_configured=key_configured,
                connection_status=new_status,
                revision=new_rev,
                updated_at=now_str,
            )

    async def probe(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        custom_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Execute a minimal, dialect-conforming synthetic probe without PII or user context."""
        settings = self.get_settings()
        if not settings.endpoint or not settings.model_id:
            return {
                "ok": False,
                "reachable": False,
                "status_code": None,
                "error": "ai_endpoint_or_model_not_configured",
                "latency_ms": None,
            }

        secret_key = self.get_secret_key()
        headers = {"Content-Type": "application/json"}
        if secret_key:
            headers["Authorization"] = f"Bearer {secret_key}"

        # Minimal synthetic payload matching dialect
        if settings.provider_dialect == "openai_compatible":
            payload = {
                "model": settings.model_id,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
        else:
            payload = {
                "model": settings.model_id,
                "prompt": "ping",
                "max_tokens": 5,
            }

        probe_timeout = min(settings.timeout_seconds, 10.0)
        start_time = time.perf_counter()

        client_cm = None
        if custom_client is not None:
            client = custom_client
        else:
            client = httpx.AsyncClient(
                transport=transport,
                timeout=probe_timeout,
                follow_redirects=False,
            )
            client_cm = client

        try:
            async with client if client_cm else nullcontext_async(client):
                resp = await client.post(
                    settings.endpoint,
                    json=payload,
                    headers=headers,
                )
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                reachable = resp.status_code in (200, 201, 204)
                status_code = resp.status_code
                error_msg = None if reachable else f"http_status_{status_code}"

                # Update status
                new_status = "reachable" if reachable else "unreachable"
                self.update_settings(connection_status=new_status)

                return {
                    "ok": reachable,
                    "reachable": reachable,
                    "status_code": status_code,
                    "error": error_msg,
                    "latency_ms": elapsed_ms,
                }
        except httpx.TimeoutException:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            self.update_settings(connection_status="unreachable")
            return {
                "ok": False,
                "reachable": False,
                "status_code": None,
                "error": "connection_timeout",
                "latency_ms": elapsed_ms,
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            self.update_settings(connection_status="unreachable")
            return {
                "ok": False,
                "reachable": False,
                "status_code": None,
                "error": type(exc).__name__,
                "latency_ms": elapsed_ms,
            }


class nullcontext_async:
    """Async context manager wrapper for an existing client."""

    def __init__(self, resource: Any):
        self.resource = resource

    async def __aenter__(self) -> Any:
        return self.resource

    async def __aexit__(self, *args: Any) -> None:
        pass
