"""Tests for AI Connection Settings & Protected Secret Store (Phase 5).

Covers:
- P5-A01: Admin read, update, key lifecycle, safe serialization.
- P5-A02: Egress URL validation, SSRF protection, secret encryption.
- P5-A03: Revision control, optimistic locking, F-090/F-091 compatibility.
- P5-A04: Synthetic outbound probe without sensitive user data.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from eitaa_bridge.application.agent_gateway import (
    AgentChatContext,
    LiveAiAgentAdapter,
    TestAgentAdapter,
)
from eitaa_bridge.application.api import BridgeApplicationApi
from eitaa_bridge.errors import BridgeError
from eitaa_bridge.infrastructure.coordinator.ai_connection import (
    AiConnectionError,
    AiConnectionStore,
    validate_egress_endpoint,
)


class MockDatabase:
    def __init__(self):
        self._conn = sqlite3.connect(":memory:")

    def _connect(self):
        return self._conn


class MockProtector:
    def hmac_hex(self, data: bytes) -> str:
        import hashlib, hmac
        return hmac.new(b"test-protector-secret-key", data, hashlib.sha256).hexdigest()


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
def ai_store(mock_db):
    return AiConnectionStore(mock_db, protector=MockProtector())


def test_ai_store_initialization(ai_store):
    settings = ai_store.get_settings()
    assert settings.enabled is False
    assert settings.provider_dialect == "openai_compatible"
    assert settings.endpoint == ""
    assert settings.model_id == ""
    assert settings.key_configured is False
    assert settings.revision == 1
    assert settings.connection_status == "unconfigured"


def test_ai_store_update_and_safe_serialization(ai_store):
    updated = ai_store.update_settings(
        enabled=True,
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        display_name="OpenAI GPT-4o",
        timeout_seconds=45.0,
        max_input_length=8000,
        max_output_tokens=2000,
        concurrency_limit=10,
        secret_key="sk-real-secret-key-12345",
        expected_revision=1,
    )

    assert updated.enabled is True
    assert updated.endpoint == "https://api.openai.com/v1/chat/completions"
    assert updated.model_id == "gpt-4o"
    assert updated.key_configured is True
    assert updated.revision == 2
    assert updated.connection_status == "configured"

    # Verify safe dictionary NEVER leaks the secret key
    safe_dict = updated.to_safe_dict()
    assert "secret_key" not in safe_dict
    assert "secret_key_ciphertext" not in safe_dict
    assert safe_dict["key_configured"] is True

    # Internal get_secret_key decrypts correctly
    assert ai_store.get_secret_key() == "sk-real-secret-key-12345"


def test_ai_store_secret_rotation_and_clear(ai_store):
    ai_store.update_settings(
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        secret_key="initial-secret",
    )
    assert ai_store.get_settings().key_configured is True
    assert ai_store.get_secret_key() == "initial-secret"

    # Retain key when secret_key is None
    ai_store.update_settings(display_name="Updated Display", secret_key=None)
    assert ai_store.get_settings().key_configured is True
    assert ai_store.get_secret_key() == "initial-secret"

    # Rejection of masked placeholder
    with pytest.raises(AiConnectionError) as exc_info:
        ai_store.update_settings(secret_key="***")
    assert exc_info.value.code == "ai_secret_placeholder_invalid"

    # Clear key when secret_key is empty string
    ai_store.update_settings(secret_key="")
    assert ai_store.get_settings().key_configured is False
    assert ai_store.get_secret_key() is None


def test_ai_store_stale_revision_rejected(ai_store):
    ai_store.update_settings(
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        expected_revision=1,
    )
    # Revision is now 2; sending expected_revision=1 must fail
    with pytest.raises(AiConnectionError) as exc_info:
        ai_store.update_settings(
            display_name="Stale edit",
            expected_revision=1,
        )
    assert exc_info.value.code == "stale_revision"
    assert exc_info.value.status_code == 409


def test_egress_url_and_ssrf_validation():
    # Valid HTTPS external
    assert validate_egress_endpoint("https://api.openai.com/v1/chat/completions")

    # Valid loopback HTTP
    assert validate_egress_endpoint("http://127.0.0.1:8000/v1/chat/completions")
    assert validate_egress_endpoint("http://localhost:8000/v1/chat/completions")
    assert validate_egress_endpoint("http://[::1]:8000/v1/chat/completions")

    # Plain HTTP to external domain forbidden
    with pytest.raises(AiConnectionError) as exc:
        validate_egress_endpoint("http://api.openai.com/v1/chat/completions")
    assert exc.value.code == "ai_endpoint_https_required"

    # Credentials in URL forbidden
    with pytest.raises(AiConnectionError) as exc:
        validate_egress_endpoint("https://user:pass@api.openai.com/v1/chat/completions")
    assert exc.value.code == "ai_endpoint_credentials_forbidden"

    # Private IP addresses forbidden
    for ip in ["10.0.0.1", "192.168.1.10", "172.16.0.5", "169.254.169.254"]:
        with pytest.raises(AiConnectionError) as exc:
            validate_egress_endpoint(f"https://{ip}/v1/chat/completions")
        assert exc.value.code == "ai_endpoint_private_ip_forbidden"

    # Invalid scheme
    with pytest.raises(AiConnectionError) as exc:
        validate_egress_endpoint("ftp://example.com/v1/chat/completions")
    assert exc.value.code == "ai_endpoint_scheme_invalid"


def test_ai_store_numeric_bounds(ai_store):
    with pytest.raises(AiConnectionError) as exc:
        ai_store.update_settings(timeout_seconds=0.5)
    assert exc.value.code == "ai_timeout_invalid"

    with pytest.raises(AiConnectionError) as exc:
        ai_store.update_settings(max_input_length=50)
    assert exc.value.code == "ai_max_input_invalid"

    with pytest.raises(AiConnectionError) as exc:
        ai_store.update_settings(max_output_tokens=10)
    assert exc.value.code == "ai_max_output_invalid"

    with pytest.raises(AiConnectionError) as exc:
        ai_store.update_settings(concurrency_limit=0)
    assert exc.value.code == "ai_concurrency_invalid"


def test_synthetic_outbound_probe_unconfigured(ai_store):
    async def _run():
        result = await ai_store.probe()
        assert result["ok"] is False
        assert result["reachable"] is False
        assert result["error"] == "ai_endpoint_or_model_not_configured"
    asyncio.run(_run())


def test_synthetic_outbound_probe_success_with_fake_transport(ai_store):
    ai_store.update_settings(
        enabled=True,
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        secret_key="sk-test-secret",
    )

    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        # Verify zero user IDs, phone numbers, or OTP codes in outbound payload
        data = json.loads(request.read())
        assert data["model"] == "gpt-4o"
        assert data["messages"] == [{"role": "user", "content": "ping"}]
        assert request.headers["Authorization"] == "Bearer sk-test-secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "pong"}}]})

    transport = httpx.MockTransport(handler)

    async def _run():
        result = await ai_store.probe(transport=transport)
        assert result["ok"] is True
        assert result["reachable"] is True
        assert result["status_code"] == 200
        assert result["error"] is None
        assert result["latency_ms"] is not None

        # Verify status transitioned to reachable
        assert ai_store.get_settings().connection_status == "reachable"

    asyncio.run(_run())
    assert len(captured_requests) == 1


def test_synthetic_outbound_probe_failure_handling(ai_store):
    ai_store.update_settings(
        enabled=True,
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    transport = httpx.MockTransport(handler)

    async def _run():
        result = await ai_store.probe(transport=transport)
        assert result["ok"] is False
        assert result["reachable"] is False
        assert result["status_code"] == 502
        assert result["error"] == "http_status_502"
        assert ai_store.get_settings().connection_status == "unreachable"

    asyncio.run(_run())


def test_live_ai_agent_adapter_chat(ai_store):
    ai_store.update_settings(
        enabled=True,
        endpoint="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        secret_key="sk-chat-secret",
    )

    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hello from AI model"}}]})

    transport = httpx.MockTransport(handler)
    adapter = LiveAiAgentAdapter(ai_store, transport=transport)

    async def _run():
        ctx = AgentChatContext("u123", "sess1", "service_test")
        resp = await adapter.chat("Hello!", "sess1", ctx, history=[])
        assert resp.response == "Hello from AI model"
        assert resp.is_test_response is False
        assert await adapter.health() is True

    asyncio.run(_run())
    assert len(captured) == 1
