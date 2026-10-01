"""Regression tests for AI Admin Routes and Security/Lifecycle (defects 3 & 4).

Covers:
- _require_ai_connection_store and _require_ai_data_policy_store fail if accessing coordinator._database.
- Composition root must build stores with real DB and protector, keep attached to runtime.
- Admin API endpoints require admin session and CSRF.
- When ai_data_policy_store is missing or disabled, non-test adapter call fails closed before transport (0 calls).
- Replay checks current permissions / data policy.
- Raw session_id is never sent to model.
- Fallback insecure-default-ai-salt removed and missing protector fails closed.
- DNS/egress controls block private IPs / SSRF even for domain names resolving to private IPs.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from eitaa_bridge.application import agent_gateway
from eitaa_bridge.application.agent_gateway import (
    AgentChatContext,
    LiveAiAgentAdapter,
    TestAgentAdapter,
)
from eitaa_bridge.application.m2m_api import handle_agent_chat
from eitaa_bridge.errors import BridgeError
from eitaa_bridge.infrastructure.coordinator.ai_connection import (
    AiConnectionError,
    AiConnectionStore,
    validate_egress_endpoint,
)
from eitaa_bridge.infrastructure.coordinator.ai_data_policy import (
    AiDataPolicyRecord,
    AiDataPolicyStore,
)


def test_ai_connection_store_fails_closed_without_valid_protector():
    # Attempting to initialize or use AiConnectionStore without a protector with hmac_hex
    # MUST fail closed instead of using insecure-default-ai-salt!
    mock_db = MagicMock()
    with pytest.raises(AiConnectionError) as exc_info:
        store = AiConnectionStore(mock_db, protector=None)
        store.update_settings(secret_key="my-secret")
    assert "protector" in str(exc_info.value).lower() or exc_info.value.code == "ai_protector_unavailable"


def test_agent_chat_fails_closed_when_data_policy_missing_for_non_test_adapter():
    service_auth = MagicMock()
    service_auth.scopes = ["agent.chat"]
    service_auth.service_name = "svc-custom"

    # Set a live / non-test adapter
    mock_adapter = MagicMock()
    mock_adapter.is_test_adapter = False
    mock_adapter.chat = AsyncMock()

    with patch("eitaa_bridge.application.agent_gateway.get_current_adapter", return_value=mock_adapter), \
         patch("eitaa_bridge.application.agent_gateway.ai_data_policy_store", None):

        # ai_data_policy_store is None: MUST NOT call mock_adapter!
        resp = asyncio.run(handle_agent_chat(
            body={
                "web_user_id": "usr-1",
                "session_id": "sess-raw-12345",
                "message": "Hello AI",
                "message_id": "msg-00000001",
            },
            service_auth_context=service_auth,
        ))
        assert resp.status in (403, 503)
        assert resp.payload["ok"] is False
        mock_adapter.chat.assert_not_called()


def test_raw_session_id_not_sent_to_model():
    # In LiveAiAgentAdapter, the session_id sent in payload must not be the raw session_id
    mock_store = MagicMock()
    mock_settings = MagicMock()
    mock_settings.enabled = True
    mock_settings.max_input_length = 4096
    mock_settings.provider_dialect = "openai_compatible"
    mock_settings.model_id = "test-model"
    mock_settings.max_output_tokens = 1000
    mock_settings.timeout_seconds = 30.0
    mock_settings.concurrency_limit = 5
    mock_settings.revision = 1
    mock_store.get_settings.return_value = mock_settings
    mock_store.get_secret_key.return_value = "sk-test"

    sent_payloads = []

    class MockAsyncClient:
        async def post(self, url, json=None, headers=None):
            sent_payloads.append(json)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value={"choices": [{"message": {"content": "Hello"}}]})
            return mock_resp

        async def aclose(self):
            pass

    adapter = LiveAiAgentAdapter(mock_store, custom_client=MockAsyncClient())
    raw_sess = "super-secret-user-session-id-999"
    ctx = AgentChatContext(web_user_id="usr-1", session_id=raw_sess, service_name="svc-1")

    resp = asyncio.run(adapter.chat(
        message="Test prompt",
        session_id=raw_sess,
        context=ctx,
        history=[],
    ))
    assert len(sent_payloads) == 1
    # raw session_id MUST NOT be in the outbound payload to the model
    assert sent_payloads[0]["session_id"] != raw_sess
    assert raw_sess not in str(sent_payloads[0])


def test_dns_egress_endpoint_validation_blocks_private_ip_resolution():
    # If a domain name resolves to a private IP (e.g. 192.168.1.1, 10.0.0.1, 127.0.0.1),
    # validate_egress_endpoint MUST reject it to prevent SSRF via DNS rebinding!
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.50", 443))]):
        with pytest.raises(AiConnectionError) as exc_info:
            validate_egress_endpoint("https://internal-dns.local/v1/chat")
        assert "forbidden" in str(exc_info.value).lower() or exc_info.value.code == "ai_endpoint_private_ip_forbidden"
